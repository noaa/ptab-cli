"""
ptab-cli: USPTO PTAB Trial proceedings CLI.

명령어 구조:
  ptab configure
  ptab proc   search | get | download
  ptab decision search | get | list | download
  ptab doc    search | get | list | download
  ptab appeal search | get | list | download
  ptab interference search | get | list | download
"""

import logging
import sys
from typing import Optional

import click

from ptab_cli import __version__
from ptab_cli import config as cfg
from ptab_cli import output as out
from ptab_cli import proceedings, decisions, documents, appeals, interferences

_FORMATS = ("table", "json", "csv")


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _common_search_options(f):
    """search 명령에 공통으로 붙는 옵션 데코레이터 묶음."""
    f = click.option("--q", "query", default=None, help="Lucene 쿼리 문자열.")(f)
    f = click.option("--from", "date_from", default=None, metavar="DATE", help="시작일 (YYYY-MM-DD).")(f)
    f = click.option("--to", "date_to", default=None, metavar="DATE", help="종료일 (YYYY-MM-DD).")(f)
    f = click.option("--limit", default=25, show_default=True, help="최대 결과 수.")(f)
    f = click.option("--offset", default=0, show_default=True, help="페이지 오프셋.")(f)
    f = click.option("--sort", default=None, help="정렬 필드 (예: 'filingDate desc').")(f)
    f = click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)(f)
    f = click.option("--out", "out_path", default=None, metavar="FILE", help="결과 저장 경로 (csv/json).")(f)
    f = click.option("--api-key", default=None, help="API 키 (설정 파일·환경변수보다 우선).")(f)
    return f


def _get_api_key(ctx_obj: dict, cli_key: Optional[str]) -> str:
    return cfg.require_api_key(cli_key or ctx_obj.get("api_key"))


def _get_timeout(ctx_obj: dict) -> int:
    return cfg.resolve_timeout(ctx_obj.get("timeout"))


def _build_query(base_q: Optional[str], *clauses: Optional[str]) -> Optional[str]:
    """여러 Lucene 절을 AND로 합쳐 하나의 q 문자열로 반환."""
    parts = [p for p in [base_q, *clauses] if p]
    return " AND ".join(parts) if parts else None


# ── main 그룹 ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="ptab")
@click.option("--verbose", "-v", is_flag=True, default=False, help="디버그 로그 출력 (stderr).")
@click.option("--timeout", default=None, type=int, help="요청 타임아웃 초.")
@click.pass_context
def main(ctx: click.Context, verbose: bool, timeout: Optional[int]) -> None:
    """USPTO PTAB Trial proceedings CLI.

    \b
    빠른 시작:
      ptab configure                         # API 키 저장
      ptab proc search --q "petitionerPartyName:Apple" --type IPR
      ptab proc get IPR2023-00001
      ptab decision list IPR2023-00001
      ptab doc list IPR2023-00001
    """
    ctx.ensure_object(dict)
    ctx.obj["timeout"] = timeout
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(stream=sys.stderr, level=level, format="%(levelname)s %(message)s")
    if ctx.invoked_subcommand is None:
        click.echo(f"ptab v{__version__}")
        click.echo(ctx.get_help())


# ── configure ─────────────────────────────────────────────────────────────────

@main.command()
@click.option("--show", is_flag=True, default=False, help="현재 설정만 표시하고 종료.")
def configure(show: bool) -> None:
    """API 키와 기본 설정을 저장합니다.

    \b
    설정 파일: ~/.ptab-cli.toml
    Enter 입력 시 기존 값 유지.
    """
    existing = cfg.load()
    auth_cfg = existing.get("auth", {})
    http_cfg = existing.get("http", {})

    click.echo("PTAB CLI — 설정")
    click.echo("─" * 40)
    click.echo(f"설정 파일: {cfg.CONFIG_PATH}")
    click.echo()

    if show:
        current_key = auth_cfg.get("api_key", "")
        current_timeout = http_cfg.get("timeout", 30)
        click.echo(f"  auth.api_key  = {cfg.mask_key(current_key)}")
        click.echo(f"  http.timeout  = {current_timeout}")
        return

    current_key = auth_cfg.get("api_key", "")
    current_timeout = http_cfg.get("timeout", 30)

    new_key = click.prompt(
        f"USPTO API 키 [{cfg.mask_key(current_key)}]",
        default="",
        show_default=False,
    ).strip()

    new_timeout_str = click.prompt(
        "요청 타임아웃(초)",
        default=str(current_timeout),
        show_default=True,
    ).strip()

    new_config: dict = {}

    final_key = new_key if new_key else current_key
    if final_key:
        new_config["auth"] = {"api_key": final_key}

    try:
        final_timeout = int(new_timeout_str) if new_timeout_str else current_timeout
    except ValueError:
        final_timeout = current_timeout

    new_config["http"] = {"timeout": final_timeout}

    if not new_config.get("auth"):
        click.echo("\n경고: API 키가 없습니다. 나중에 다시 실행하세요.", err=True)
        return

    cfg.save(new_config)
    click.echo(f"\n설정 저장: {cfg.CONFIG_PATH}")
    click.echo(f"  auth.api_key = {cfg.mask_key(final_key)}")
    click.echo(f"  http.timeout = {final_timeout}")


# ── proc 그룹 ─────────────────────────────────────────────────────────────────

@main.group()
def proc() -> None:
    """Trial 절차 검색·조회 (IPR/PGR/CBM)."""


@proc.command("search")
@_common_search_options
@click.option("--type", "proc_type", default=None,
              type=click.Choice(["IPR", "PGR", "CBM"], case_sensitive=True),
              help="절차 유형 필터: IPR | PGR | CBM.")
@click.option("--petitioner", default=None, help="청구인 이름 키워드 (petitionerPartyName).")
@click.option("--patent", default=None, help="특허번호 (예: US9876543).")
@click.option("--status", default=None, help="상태 카테고리 (예: Terminated, Pending).")
@click.pass_context
def proc_search(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    sort: Optional[str],
    fmt: str,
    out_path: Optional[str],
    api_key: Optional[str],
    proc_type: Optional[str],
    petitioner: Optional[str],
    patent: Optional[str],
    status: Optional[str],
) -> None:
    """Trial 절차를 검색합니다.

    \b
    예시:
      ptab proc search --petitioner Apple --type IPR --status Terminated
      ptab proc search --patent US9876543
      ptab proc search --from 2023-01-01 --to 2023-12-31 --limit 50
      ptab proc search --q "statusCategory:Terminated" --format csv --out result.csv
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"trialMetaData.petitionFilingDate:[{start} TO {end}]"

    type_clause = f"trialMetaData.trialTypeCode:{proc_type}" if proc_type else None
    petitioner_clause = f"regularPetitionerData.realPartyInInterestName:{petitioner}" if petitioner else None
    patent_clause = f"patentOwnerData.patentNumber:{patent}" if patent else None
    status_clause = f"trialMetaData.trialStatusCategory:{status}" if status else None
    final_q = _build_query(query, type_clause, petitioner_clause, patent_clause, status_clause, date_clause)

    data = proceedings.search_proceedings(
        api_key=key, q=final_q, sort=sort, offset=offset, limit=limit, timeout=timeout,
    )
    out.print_list(data, out.PROC_FIELDS, fmt=fmt, out_path=out_path)


@proc.command("get")
@click.argument("trial_number")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def proc_get(ctx: click.Context, trial_number: str, fmt: str, api_key: Optional[str]) -> None:
    """Trial 번호로 개별 절차를 조회합니다.

    \b
    예시:
      ptab proc get IPR2023-00001
      ptab proc get IPR2023-00001 --format json
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = proceedings.get_proceeding(api_key=key, trial_number=trial_number, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@proc.command("download")
@click.option("--q", "query", default=None)
@click.option("--from", "date_from", default=None, metavar="DATE")
@click.option("--to", "date_to", default=None, metavar="DATE")
@click.option("--type", "proc_type", default=None, type=click.Choice(["IPR", "PGR", "CBM"], case_sensitive=True))
@click.option("--out", "out_path", required=True, metavar="FILE", help="저장할 JSON 파일 경로.")
@click.option("--api-key", default=None)
@click.pass_context
def proc_download(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    proc_type: Optional[str],
    out_path: str,
    api_key: Optional[str],
) -> None:
    """절차 검색 결과를 JSON으로 다운로드합니다.

    \b
    예시:
      ptab proc download --q "petitionerPartyName:Samsung" --out samsung.json
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    type_clause = f"trialMetaData.trialTypeCode:{proc_type}" if proc_type else None
    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"trialMetaData.petitionFilingDate:[{start} TO {end}]"

    final_q = _build_query(query, type_clause, date_clause)

    saved = proceedings.download_proceedings_search(
        api_key=key, save_path=out_path, q=final_q, timeout=timeout,
    )
    click.echo(f"저장: {saved}")


# ── decision 그룹 ─────────────────────────────────────────────────────────────

@main.group()
def decision() -> None:
    """Trial 결정 검색·조회."""


@decision.command("search")
@_common_search_options
@click.option("--type", "dec_type", default=None, help="결정 유형 (예: 'Institution Decision').")
@click.option("--petitioner", default=None, help="청구인 이름 키워드.")
@click.option("--patent", default=None, help="특허번호 (예: US9876543).")
@click.pass_context
def decision_search(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    sort: Optional[str],
    fmt: str,
    out_path: Optional[str],
    api_key: Optional[str],
    dec_type: Optional[str],
    petitioner: Optional[str],
    patent: Optional[str],
) -> None:
    """Trial 결정을 검색합니다.

    \b
    예시:
      ptab decision search --type "Final Written Decision" --from 2024-01-01
      ptab decision search --petitioner Apple --format csv --out apple_decisions.csv
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    petitioner_clause = f"regularPetitionerData.realPartyInInterestName:{petitioner}" if petitioner else None
    patent_clause = f"patentOwnerData.patentNumber:{patent}" if patent else None
    type_clause = f"decisionData.trialOutcomeCategory:\"{dec_type}\"" if dec_type else None
    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"decisionData.decisionIssueDate:[{start} TO {end}]"

    final_q = _build_query(query, petitioner_clause, patent_clause, type_clause, date_clause)

    data = decisions.search_decisions(
        api_key=key, q=final_q, sort=sort, offset=offset, limit=limit, timeout=timeout,
    )
    out.print_list(data, out.DECISION_FIELDS, fmt=fmt, out_path=out_path)


@decision.command("get")
@click.argument("doc_id")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def decision_get(ctx: click.Context, doc_id: str, fmt: str, api_key: Optional[str]) -> None:
    """문서 ID로 개별 결정을 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = decisions.get_decision(api_key=key, document_identifier=doc_id, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@decision.command("list")
@click.argument("trial_number")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def decision_list(ctx: click.Context, trial_number: str, fmt: str, api_key: Optional[str]) -> None:
    """Trial 번호별 결정 목록을 조회합니다.

    \b
    예시:
      ptab decision list IPR2023-00001
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = decisions.get_decisions_by_trial(api_key=key, trial_number=trial_number, timeout=timeout)
    out.print_list(data, out.DECISION_FIELDS, fmt=fmt)


@decision.command("download")
@click.option("--q", "query", default=None)
@click.option("--out", "out_path", required=True, metavar="FILE")
@click.option("--api-key", default=None)
@click.pass_context
def decision_download(ctx: click.Context, query: Optional[str], out_path: str, api_key: Optional[str]) -> None:
    """결정 검색 결과를 JSON으로 다운로드합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = decisions.download_decisions_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"저장: {saved}")


# ── doc 그룹 ──────────────────────────────────────────────────────────────────

@main.group()
def doc() -> None:
    """Trial 문서 검색·조회."""


@doc.command("search")
@_common_search_options
@click.option("--type", "doc_type", default=None, help="문서 유형 (예: 'Petition').")
@click.pass_context
def doc_search(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    sort: Optional[str],
    fmt: str,
    out_path: Optional[str],
    api_key: Optional[str],
    doc_type: Optional[str],
) -> None:
    """Trial 문서를 검색합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    type_clause = f"documentData.documentTypeDescriptionText:\"{doc_type}\"" if doc_type else None
    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"documentData.documentFilingDate:[{start} TO {end}]"

    final_q = _build_query(query, type_clause, date_clause)

    data = documents.search_documents(
        api_key=key, q=final_q, sort=sort, offset=offset, limit=limit, timeout=timeout,
    )
    out.print_list(data, out.DOC_FIELDS, fmt=fmt, out_path=out_path)


@doc.command("get")
@click.argument("doc_id")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def doc_get(ctx: click.Context, doc_id: str, fmt: str, api_key: Optional[str]) -> None:
    """문서 ID로 개별 문서를 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = documents.get_document(api_key=key, document_identifier=doc_id, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@doc.command("list")
@click.argument("trial_number")
@click.option("--category", default=None, help="문서 카테고리 필터 (예: FINAL, DECISION, MOTION, Exhibit).")
@click.option("--party", default=None, help="제출 주체 필터 (BOARD, PETITIONER, PATENT OWNER).")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def doc_list(ctx: click.Context, trial_number: str, category: Optional[str], party: Optional[str], fmt: str, api_key: Optional[str]) -> None:
    """Trial 번호별 문서 목록을 조회합니다.

    \b
    예시:
      ptab doc list IPR2023-00001
      ptab doc list IPR2023-00001 --category FINAL
      ptab doc list IPR2023-00001 --party BOARD
      ptab doc list IPR2023-00001 --category FINAL --party BOARD
    """
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = documents.get_documents_by_trial(api_key=key, trial_number=trial_number, timeout=timeout)
    docs = data.get("patentTrialDocumentDataBag", [])
    if category:
        docs = [d for d in docs if d.get("documentData", {}).get("documentCategory", "").upper() == category.upper()]
    if party:
        docs = [d for d in docs if d.get("documentData", {}).get("filingPartyCategory", "").upper() == party.upper()]
    data["patentTrialDocumentDataBag"] = docs
    out.print_list(data, out.DOC_FIELDS, fmt=fmt)


@doc.command("download")
@click.option("--q", "query", default=None)
@click.option("--out", "out_path", required=True, metavar="FILE")
@click.option("--api-key", default=None)
@click.pass_context
def doc_download(ctx: click.Context, query: Optional[str], out_path: str, api_key: Optional[str]) -> None:
    """문서 검색 결과를 JSON으로 다운로드합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = documents.download_documents_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"저장: {saved}")


@doc.command("pdf")
@click.argument("doc_id")
@click.option("--out", "out_path", default=None, metavar="FILE", help="저장 경로 (기본값: {DOC_ID}.pdf).")
@click.option("--api-key", default=None)
@click.pass_context
def doc_pdf(ctx: click.Context, doc_id: str, out_path: Optional[str], api_key: Optional[str]) -> None:
    """문서 ID로 PDF 파일을 다운로드합니다.

    \b
    예시:
      ptab doc pdf 171200528
      ptab doc pdf 171200528 --out FWD_remand.pdf
    """
    key = _get_api_key(ctx.obj, api_key)
    save = out_path or f"{doc_id}.pdf"
    saved = documents.download_document_pdf(api_key=key, document_identifier=doc_id, save_path=save)
    click.echo(f"저장: {saved}")


# ── appeal 그룹 ───────────────────────────────────────────────────────────────

@main.group()
def appeal() -> None:
    """항소 결정 검색·조회."""


@appeal.command("search")
@_common_search_options
@click.pass_context
def appeal_search(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    sort: Optional[str],
    fmt: str,
    out_path: Optional[str],
    api_key: Optional[str],
) -> None:
    """항소 결정을 검색합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"decisionData.decisionIssueDate:[{start} TO {end}]"

    final_q = _build_query(query, date_clause)

    data = appeals.search_appeal_decisions(
        api_key=key, q=final_q, sort=sort, offset=offset, limit=limit, timeout=timeout,
    )
    out.print_list(data, out.APPEAL_FIELDS, fmt=fmt, out_path=out_path)


@appeal.command("get")
@click.argument("doc_id")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def appeal_get(ctx: click.Context, doc_id: str, fmt: str, api_key: Optional[str]) -> None:
    """문서 ID로 개별 항소 결정을 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = appeals.get_appeal_decision(api_key=key, document_identifier=doc_id, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@appeal.command("list")
@click.argument("appeal_number")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def appeal_list(ctx: click.Context, appeal_number: str, fmt: str, api_key: Optional[str]) -> None:
    """항소 번호별 결정 목록을 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = appeals.get_decisions_by_appeal(api_key=key, appeal_number=appeal_number, timeout=timeout)
    out.print_list(data, out.APPEAL_FIELDS, fmt=fmt)


@appeal.command("download")
@click.option("--q", "query", default=None)
@click.option("--out", "out_path", required=True, metavar="FILE")
@click.option("--api-key", default=None)
@click.pass_context
def appeal_download(ctx: click.Context, query: Optional[str], out_path: str, api_key: Optional[str]) -> None:
    """항소 결정 검색 결과를 JSON으로 다운로드합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = appeals.download_appeal_decisions_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"저장: {saved}")


# ── interference 그룹 ─────────────────────────────────────────────────────────

@main.group()
def interference() -> None:
    """저촉심사 결정 검색·조회."""


@interference.command("search")
@_common_search_options
@click.pass_context
def interference_search(
    ctx: click.Context,
    query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    sort: Optional[str],
    fmt: str,
    out_path: Optional[str],
    api_key: Optional[str],
) -> None:
    """저촉심사 결정을 검색합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)

    date_clause = None
    if date_from or date_to:
        start = date_from or "*"
        end = date_to or "*"
        date_clause = f"decisionData.decisionIssueDate:[{start} TO {end}]"

    final_q = _build_query(query, date_clause)

    data = interferences.search_interference_decisions(
        api_key=key, q=final_q, sort=sort, offset=offset, limit=limit, timeout=timeout,
    )
    out.print_list(data, out.INTERFERENCE_FIELDS, fmt=fmt, out_path=out_path)


@interference.command("get")
@click.argument("doc_id")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def interference_get(ctx: click.Context, doc_id: str, fmt: str, api_key: Optional[str]) -> None:
    """문서 ID로 개별 저촉심사 결정을 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = interferences.get_interference_decision(api_key=key, document_identifier=doc_id, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@interference.command("list")
@click.argument("interference_number")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def interference_list(ctx: click.Context, interference_number: str, fmt: str, api_key: Optional[str]) -> None:
    """저촉심사 번호별 결정 목록을 조회합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = interferences.get_decisions_by_interference(
        api_key=key, interference_number=interference_number, timeout=timeout,
    )
    out.print_list(data, out.INTERFERENCE_FIELDS, fmt=fmt)


@interference.command("download")
@click.option("--q", "query", default=None)
@click.option("--out", "out_path", required=True, metavar="FILE")
@click.option("--api-key", default=None)
@click.pass_context
def interference_download(ctx: click.Context, query: Optional[str], out_path: str, api_key: Optional[str]) -> None:
    """저촉심사 결정 검색 결과를 JSON으로 다운로드합니다."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = interferences.download_interference_decisions_search(
        api_key=key, save_path=out_path, q=query, timeout=timeout,
    )
    click.echo(f"저장: {saved}")
