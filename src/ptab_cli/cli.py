"""
ptab-cli: USPTO PTAB Trial proceedings CLI.

Command structure:
  ptab configure
  ptab proc   search | get | download
  ptab decision search | get | list | download
  ptab doc    search | get | list | download | pdf | parse
  ptab appeal search | get | list | download
  ptab interference search | get | list | download
"""

import logging
import sys
from typing import Optional

import click

from ptab_cli import (
    __version__,
    appeals,
    decisions,
    documents,
    interferences,
    pdf_parser,
    proceedings,
)
from ptab_cli import config as cfg
from ptab_cli import output as out

_FORMATS = ("table", "json", "csv")


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _common_search_options(f):
    """Common option decorator bundle for search commands."""
    f = click.option("--q", "query", default=None, help="Lucene query string.")(f)
    f = click.option("--from", "date_from", default=None, metavar="DATE", help="Start date (YYYY-MM-DD).")(f)
    f = click.option("--to", "date_to", default=None, metavar="DATE", help="End date (YYYY-MM-DD).")(f)
    f = click.option("--limit", default=25, show_default=True, help="Maximum number of results.")(f)
    f = click.option("--offset", default=0, show_default=True, help="Page offset.")(f)
    f = click.option("--sort", default=None, help="Sort field (e.g. 'filingDate desc').")(f)
    f = click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)(f)
    f = click.option("--out", "out_path", default=None, metavar="FILE", help="Output file path (csv/json).")(f)
    f = click.option("--api-key", default=None, help="API key (overrides config file and environment variable).")(f)
    return f


def _get_api_key(ctx_obj: dict, cli_key: Optional[str]) -> str:
    return cfg.require_api_key(cli_key or ctx_obj.get("api_key"))


def _get_timeout(ctx_obj: dict) -> int:
    return cfg.resolve_timeout(ctx_obj.get("timeout"))


def _build_query(base_q: Optional[str], *clauses: Optional[str]) -> Optional[str]:
    """Combine multiple Lucene clauses with AND into a single q string."""
    parts = [p for p in [base_q, *clauses] if p]
    return " AND ".join(parts) if parts else None


# ── main 그룹 ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="ptab")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging (stderr).")
@click.option("--timeout", default=None, type=int, help="Request timeout in seconds.")
@click.pass_context
def main(ctx: click.Context, verbose: bool, timeout: Optional[int]) -> None:
    """USPTO PTAB Trial proceedings CLI.

    \b
    Quick start:
      ptab configure                         # Save API key
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
@click.option("--show", is_flag=True, default=False, help="Show current settings and exit.")
def configure(show: bool) -> None:
    """Save API key and default settings.

    \b
    Config file: ~/.ptab-cli.toml
    Press Enter to keep existing values.
    """
    existing = cfg.load()
    auth_cfg = existing.get("auth", {})
    http_cfg = existing.get("http", {})

    click.echo("PTAB CLI — Configuration")
    click.echo("─" * 40)
    click.echo(f"Config file: {cfg.CONFIG_PATH}")
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
        f"USPTO API key [{cfg.mask_key(current_key)}]",
        default="",
        show_default=False,
    ).strip()

    new_timeout_str = click.prompt(
        "Request timeout (seconds)",
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
        click.echo("\nWarning: No API key provided. Run again to set one.", err=True)
        return

    cfg.save(new_config)
    click.echo(f"\nSaved: {cfg.CONFIG_PATH}")
    click.echo(f"  auth.api_key = {cfg.mask_key(final_key)}")
    click.echo(f"  http.timeout = {final_timeout}")


# ── proc 그룹 ─────────────────────────────────────────────────────────────────

@main.group()
def proc() -> None:
    """Search and retrieve trial proceedings (IPR/PGR/CBM)."""


@proc.command("search")
@_common_search_options
@click.option("--type", "proc_type", default=None,
              type=click.Choice(["IPR", "PGR", "CBM"], case_sensitive=True),
              help="Proceeding type filter: IPR | PGR | CBM.")
@click.option("--petitioner", default=None, help="Petitioner name keyword (petitionerPartyName).")
@click.option("--patent", default=None, help="Patent number (e.g. US9876543).")
@click.option("--status", default=None, help="Status category (e.g. Terminated, Pending).")
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
    """Search trial proceedings.

    \b
    Examples:
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
    """Retrieve a single proceeding by trial number.

    \b
    Examples:
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
@click.option("--out", "out_path", required=True, metavar="FILE", help="Output JSON file path.")
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
    """Download proceeding search results as JSON.

    \b
    Examples:
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
    click.echo(f"Saved: {saved}")


# ── decision 그룹 ─────────────────────────────────────────────────────────────

@main.group()
def decision() -> None:
    """Search and retrieve trial decisions."""


@decision.command("search")
@_common_search_options
@click.option("--type", "dec_type", default=None, help="Decision type (e.g. 'Institution Decision').")
@click.option("--petitioner", default=None, help="Petitioner name keyword.")
@click.option("--patent", default=None, help="Patent number (e.g. US9876543).")
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
    """Search trial decisions.

    \b
    Examples:
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
    """Retrieve a single decision by document ID."""
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
    """List decisions for a trial number.

    \b
    Examples:
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
    """Download decision search results as JSON."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = decisions.download_decisions_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"Saved: {saved}")


# ── doc 그룹 ──────────────────────────────────────────────────────────────────

@main.group()
def doc() -> None:
    """Search and retrieve trial documents."""


@doc.command("search")
@_common_search_options
@click.option("--type", "doc_type", default=None, help="Document type (e.g. 'Petition').")
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
    """Search trial documents."""
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
    """Retrieve a single document by document ID."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    data = documents.get_document(api_key=key, document_identifier=doc_id, timeout=timeout)
    out.print_detail(data, fmt=fmt)


@doc.command("list")
@click.argument("trial_number")
@click.option("--category", default=None, help="Document category filter (e.g. FINAL, DECISION, MOTION, Exhibit).")
@click.option("--party", default=None, help="Filing party filter (BOARD, PETITIONER, PATENT OWNER).")
@click.option("--format", "-f", "fmt", type=click.Choice(_FORMATS), default="table", show_default=True)
@click.option("--api-key", default=None)
@click.pass_context
def doc_list(ctx: click.Context, trial_number: str, category: Optional[str], party: Optional[str], fmt: str, api_key: Optional[str]) -> None:
    """List documents for a trial number.

    \b
    Examples:
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
    """Download document search results as JSON."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = documents.download_documents_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"Saved: {saved}")


@doc.command("pdf")
@click.argument("doc_id")
@click.option("--out", "out_path", default=None, metavar="FILE", help="Output path (default: {DOC_ID}.pdf).")
@click.option("--api-key", default=None)
@click.pass_context
def doc_pdf(ctx: click.Context, doc_id: str, out_path: Optional[str], api_key: Optional[str]) -> None:
    """Download a PDF file by document ID.

    \b
    Examples:
      ptab doc pdf 171200528
      ptab doc pdf 171200528 --out FWD_remand.pdf
    """
    key = _get_api_key(ctx.obj, api_key)
    save = out_path or f"{doc_id}.pdf"
    saved = documents.download_document_pdf(api_key=key, document_identifier=doc_id, save_path=save)
    click.echo(f"Saved: {saved}")


@doc.command("parse")
@click.argument("pdf_path", metavar="PDF_FILE")
@click.option(
    "--out", "out_path", default=None, metavar="FILE",
    help="Output .md path (default: same name as PDF with .md extension).",
)
@click.pass_context
def doc_parse(ctx: click.Context, pdf_path: str, out_path: Optional[str]) -> None:
    """Convert a downloaded PDF to Markdown for AI analysis.

    Extracts text using pdfminer.six and converts to structured Markdown
    with YAML front matter (trial number, patent, document type, date).

    Image-based pages (scanned exhibits) cannot be extracted automatically.
    When detected, the command saves what it can and prints a warning with
    the affected page numbers so you can handle them separately.

    \b
    Examples:
      ptab doc parse FinalWrittenDecision.pdf
      ptab doc parse 170093427.pdf --out analysis/fwd.md
    """
    save = out_path or pdf_parser.default_output_path(pdf_path)

    try:
        result = pdf_parser.parse_pdf(pdf_path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e))
    except ImportError as e:
        raise click.ClickException(str(e))

    saved = pdf_parser.save_markdown(result, save)

    click.echo(f"Saved: {saved}")
    click.echo(
        f"  {result.total_pages} pages · "
        f"{len(result.markdown):,} chars · "
        f"type: {result.metadata.get('document_type', 'unknown')}"
    )

    if result.needs_ocr:
        _warn_ocr_needed(pdf_path, result)


def _warn_ocr_needed(pdf_path: str, result: "pdf_parser.PdfParseResult") -> None:
    """OCR이 필요한 페이지에 대한 경고를 출력합니다."""
    total = result.total_pages
    ocr_pages = result.ocr_pages
    ratio = len(ocr_pages) / total if total else 0

    click.echo("", err=True)

    if ratio >= 0.8:
        # 대부분 또는 전체가 이미지 기반
        click.secho(
            "WARNING: This PDF appears to be image-based (scanned). "
            "Text extraction produced little or no content.",
            fg="yellow", bold=True, err=True,
        )
    else:
        # 일부 페이지만 이미지
        click.secho(
            f"WARNING: {len(ocr_pages)} of {total} pages have no text layer "
            f"(pages: {_format_page_list(ocr_pages)}).",
            fg="yellow", bold=True, err=True,
        )

    click.secho(
        "  These pages require OCR to extract text. Options:\n"
        "  1. Install tesseract + run:  pip install pytesseract pdf2image\n"
        "     then use a separate OCR script (see docs/ocr_fallback.md)\n"
        "  2. Send the PDF directly to Claude API (handles images natively)\n"
        "  3. Open the PDF manually to read image-only pages",
        fg="yellow", err=True,
    )
    click.echo("", err=True)


def _format_page_list(pages: list[int]) -> str:
    """[1, 2, 3, 5, 6, 9] → '1-3, 5-6, 9' 형태로 압축합니다."""
    if not pages:
        return ""
    ranges: list[str] = []
    start = pages[0]
    end = pages[0]
    for p in pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append(str(start) if start == end else f"{start}-{end}")
            start = end = p
    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ", ".join(ranges)


# ── appeal 그룹 ───────────────────────────────────────────────────────────────

@main.group()
def appeal() -> None:
    """Search and retrieve appeal decisions."""


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
    """Search appeal decisions."""
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
    """Retrieve a single appeal decision by document ID."""
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
    """List decisions for an appeal number."""
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
    """Download appeal decision search results as JSON."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = appeals.download_appeal_decisions_search(api_key=key, save_path=out_path, q=query, timeout=timeout)
    click.echo(f"Saved: {saved}")


# ── interference 그룹 ─────────────────────────────────────────────────────────

@main.group()
def interference() -> None:
    """Search and retrieve interference decisions."""


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
    """Search interference decisions."""
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
    """Retrieve a single interference decision by document ID."""
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
    """List decisions for an interference number."""
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
    """Download interference decision search results as JSON."""
    key = _get_api_key(ctx.obj, api_key)
    timeout = _get_timeout(ctx.obj)
    saved = interferences.download_interference_decisions_search(
        api_key=key, save_path=out_path, q=query, timeout=timeout,
    )
    click.echo(f"Saved: {saved}")
