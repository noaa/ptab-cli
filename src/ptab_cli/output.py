"""
출력 포맷 렌더러: table | json | csv.

- table: rich 라이브러리로 색상 테이블 출력 (기본)
- json : API 응답 원문 pretty-print
- csv  : 헤더 포함 CSV (stdout 또는 파일)
"""

import csv
import json
import sys
from typing import Any, Optional

from rich.console import Console
from rich.table import Table
from rich import box

_console = Console()
_err_console = Console(stderr=True)

# API 응답에서 결과 목록을 담는 키 (우선순위 순)
_RESULT_BAG_KEYS = [
    "patentTrialProceedingDataBag",
    "patentTrialDocumentDataBag",
    "patentAppealDecisionDataBag",
    "patentInterferenceDecisionDataBag",
    "results",
    "trials",
]


# ── 필드 정의 (key=점 표기 경로, label=헤더 텍스트) ───────────────────────────
# 점(.) 은 중첩 접근을 의미한다: "a.b" → record["a"]["b"]

# 필드 정의: (dotted_key, label, no_wrap)
# no_wrap=True 인 컬럼은 줄바꿈 없이 그대로 출력한다.

PROC_FIELDS = [
    ("trialNumber",                              "Trial No.",   True),
    ("trialMetaData.trialTypeCode",              "Type",        True),
    ("trialMetaData.petitionFilingDate",         "Filed",       True),
    ("trialMetaData.trialStatusCategory",        "Status",      False),
    ("regularPetitionerData.realPartyInInterestName", "Petitioner", False),
    ("patentOwnerData.patentNumber",             "Patent No.",  True),
]

DECISION_FIELDS = [
    ("trialNumber",                         "Trial No.",  True),
    ("documentData.documentIdentifier",     "Doc ID",     True),
    ("decisionData.decisionTypeCategory",   "Type",       True),
    ("decisionData.decisionIssueDate",      "Date",       True),
    ("decisionData.trialOutcomeCategory",   "Outcome",    False),
]

DOC_FIELDS = [
    ("trialNumber",                              "Trial No.",  True),
    ("documentData.documentIdentifier",          "Doc ID",     True),
    ("documentData.documentTypeDescriptionText", "Type",       False),
    ("documentData.documentFilingDate",          "Filed",      True),
    ("documentData.documentTitleText",           "Title",      False),
]

APPEAL_FIELDS = [
    ("trialNumber",                         "Trial No.",  True),
    ("documentData.documentIdentifier",     "Doc ID",     True),
    ("decisionData.decisionTypeCategory",   "Type",       True),
    ("decisionData.decisionIssueDate",      "Date",       True),
    ("decisionData.trialOutcomeCategory",   "Outcome",    False),
]

INTERFERENCE_FIELDS = [
    ("trialNumber",                         "Trial No.",  True),
    ("documentData.documentIdentifier",     "Doc ID",     True),
    ("decisionData.decisionTypeCategory",   "Type",       True),
    ("decisionData.decisionIssueDate",      "Date",       True),
    ("decisionData.trialOutcomeCategory",   "Outcome",    False),
]


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def print_list(
    data: dict[str, Any],
    fields: list[tuple[str, str, bool]],
    fmt: str = "table",
    out_path: Optional[str] = None,
) -> None:
    """검색/목록 결과(복수 레코드)를 출력."""
    results = _extract_results(data)
    total: int = data.get("count", len(results))

    if fmt == "json":
        _print_json(data, out_path)
    elif fmt == "csv":
        _print_csv(results, fields, out_path)
    else:
        _print_table(results, fields, total)


def print_detail(record: dict[str, Any], fmt: str = "table") -> None:
    """단건 조회 결과를 출력. bag 래퍼가 있으면 첫 번째 항목을 꺼낸다."""
    unwrapped = _unwrap_single(record)
    if fmt == "json":
        _print_json(unwrapped)
    else:
        _print_kv(unwrapped)


def _unwrap_single(data: dict[str, Any]) -> dict[str, Any]:
    """단건 응답의 bag 래퍼를 제거하고 실제 레코드를 반환."""
    for key in _RESULT_BAG_KEYS:
        if key in data and isinstance(data[key], list) and data[key]:
            return data[key][0]
    return data


def print_error(msg: str) -> None:
    _err_console.print(f"[red]Error:[/red] {msg}")


def print_info(msg: str) -> None:
    _err_console.print(f"[dim]{msg}[/dim]")


# ── 내부 구현 ─────────────────────────────────────────────────────────────────

def _extract_results(data: dict[str, Any]) -> list[dict]:
    """API 응답에서 결과 목록을 추출."""
    for key in _RESULT_BAG_KEYS:
        if key in data:
            return data[key]
    # 그 외: 값 중 처음 발견되는 list 반환
    for val in data.values():
        if isinstance(val, list):
            return val
    return []


def _get_nested(record: dict, dotted_key: str) -> str:
    """'a.b.c' 형식의 경로로 중첩 dict에서 값을 꺼낸다."""
    parts = dotted_key.split(".")
    val: Any = record
    for part in parts:
        if not isinstance(val, dict):
            return ""
        val = val.get(part)
        if val is None:
            return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val).strip()


def _print_table(
    results: list[dict],
    fields: list[tuple[str, str, bool]],
    total: int,
) -> None:
    if not results:
        _console.print("[yellow]No results[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_footer=False, highlight=True)
    for _, label, no_wrap in fields:
        table.add_column(label, no_wrap=no_wrap, overflow="fold", max_width=40)

    for rec in results:
        row = [_get_nested(rec, key) or "—" for key, _, _ in fields]
        table.add_row(*row)

    _console.print(table)
    _console.print(f"[dim]Showing {len(results)} of {total:,} total[/dim]", highlight=False)


def _print_kv(record: dict[str, Any]) -> None:
    """Key-Value 세로 형식 출력 (단건 조회용)."""
    flat = _flatten(record)
    if not flat:
        _console.print("[yellow]No data[/yellow]")
        return
    max_key = max(len(k) for k in flat)
    for key, val in flat.items():
        _console.print(f"[bold]{key:<{max_key}}[/bold]  {val}")


def _flatten(obj: Any, prefix: str = "") -> dict[str, str]:
    """중첩 dict를 'parent.child' 평탄화 dict로 변환."""
    result: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(_flatten(v, full_key))
            elif isinstance(v, list):
                result[full_key] = ", ".join(str(i) for i in v)
            elif v not in (None, ""):
                result[full_key] = str(v)
    return result


def _print_json(data: Any, out_path: Optional[str] = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print_info(f"Saved: {out_path}")
    else:
        print(text)


def _print_csv(
    results: list[dict],
    fields: list[tuple[str, str, bool]],
    out_path: Optional[str] = None,
) -> None:
    headers = [label for _, label, _ in fields]

    if out_path:
        f = open(out_path, "w", newline="", encoding="utf-8-sig")
    else:
        f = sys.stdout  # type: ignore[assignment]

    writer = csv.writer(f)
    writer.writerow(headers)
    for rec in results:
        writer.writerow([_get_nested(rec, key) for key, _, _ in fields])

    if out_path:
        f.close()
        print_info(f"Saved: {out_path}")
