"""
PTAB Interferences — Decisions API.

엔드포인트:
  GET /api/v1/patent/interferences/decisions/search                      - 저촉심사 결정 검색
  GET /api/v1/patent/interferences/decisions/search/download             - 검색 결과 다운로드
  GET /api/v1/patent/interferences/{interferenceNumber}/decisions        - 저촉심사 번호별 결정
  GET /api/v1/patent/interferences/decisions/{documentIdentifier}        - 개별 결정 조회

독립 실행:
    cd uspto-odp/ptab
    uv run python interferences.py
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode



from .client import download_binary, get

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("USPTO_API_KEY", "")
_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))


# ── 공개 함수 ───────────────────────────────────────────────────────────────

def search_interference_decisions(
    api_key: str,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    offset: int = 0,
    limit: int = 25,
    facets: Optional[str] = None,
    fields: Optional[str] = None,
    filters: Optional[str] = None,
    range_filters: Optional[str] = None,
    timeout: int = _TIMEOUT,
) -> Dict[str, Any]:
    """
    PTAB 저촉심사 결정(Interference Decisions)을 검색합니다.

    Args:
        api_key: USPTO API 키.
        q: Lucene 쿼리 문자열 (예: "interferenceNumber:105678").
        sort: 정렬 필드와 방향 (예: "decisionDate desc").
        offset: 시작 레코드 위치 (기본 0).
        limit: 반환할 최대 레코드 수 (기본 25).
        facets: 패싯 집계 필드 (쉼표 구분).
        fields: 반환 필드 제한 (쉼표 구분).
        filters: 필드 값 필터.
        range_filters: 범위 필터.
        timeout: 요청 타임아웃 (초).

    Returns:
        저촉심사 결정 검색 결과 딕셔너리.

    Example:
        >>> results = search_interference_decisions(api_key, limit=10)
        >>> print(results["count"])
    """
    params: Dict[str, Any] = {"offset": offset, "limit": limit}
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort
    if facets:
        params["facets"] = facets
    if fields:
        params["fields"] = fields
    if filters:
        params["filters"] = filters
    if range_filters:
        params["rangeFilters"] = range_filters

    return get("/api/v1/patent/interferences/decisions/search", api_key, params=params, timeout=timeout)


def download_interference_decisions_search(
    api_key: str,
    save_path: str,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    offset: int = 0,
    limit: int = 25,
    filters: Optional[str] = None,
    range_filters: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """
    PTAB 저촉심사 결정 검색 결과를 파일로 다운로드합니다.

    Args:
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로 (예: "json/interferences.zip").
        q: Lucene 쿼리 문자열.
        sort: 정렬 필드와 방향.
        offset: 시작 레코드 위치.
        limit: 반환할 최대 레코드 수.
        filters: 필드 값 필터.
        range_filters: 범위 필터.
        timeout: 다운로드 타임아웃 (초).

    Returns:
        저장된 파일의 절대 경로.

    Example:
        >>> path = download_interference_decisions_search(api_key, "json/interferences.zip")
    """
    params: Dict[str, Any] = {"offset": offset, "limit": limit}
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort
    if filters:
        params["filters"] = filters
    if range_filters:
        params["rangeFilters"] = range_filters

    path = f"/api/v1/patent/interferences/decisions/search/download?{urlencode(params)}"
    return download_binary(path, api_key, save_path, timeout=timeout)


def get_decisions_by_interference(
    api_key: str,
    interference_number: str,
    timeout: int = _TIMEOUT,
) -> Dict[str, Any]:
    """
    특정 저촉심사 번호에 해당하는 모든 PTAB 결정을 조회합니다.

    Args:
        api_key: USPTO API 키.
        interference_number: 저촉심사 번호 (예: "105678").
        timeout: 요청 타임아웃 (초).

    Returns:
        해당 저촉심사의 결정 목록 딕셔너리.

    Example:
        >>> decisions = get_decisions_by_interference(api_key, "105678")
    """
    return get(
        f"/api/v1/patent/interferences/{interference_number}/decisions",
        api_key,
        timeout=timeout,
    )


def get_interference_decision(
    api_key: str,
    document_identifier: str,
    timeout: int = _TIMEOUT,
) -> Dict[str, Any]:
    """
    특정 문서 식별자의 PTAB 저촉심사 결정을 조회합니다.

    Args:
        api_key: USPTO API 키.
        document_identifier: 문서 식별자.
        timeout: 요청 타임아웃 (초).

    Returns:
        해당 저촉심사 결정의 상세 정보 딕셔너리.

    Example:
        >>> decision = get_interference_decision(api_key, "INTERFERENCE-DOC-001")
    """
    return get(
        f"/api/v1/patent/interferences/decisions/{document_identifier}",
        api_key,
        timeout=timeout,
    )


# ── 단독 실행 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _API_KEY:
        raise ValueError("USPTO_API_KEY 환경변수가 설정되지 않았습니다.")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(project_root, "json")
    os.makedirs(json_dir, exist_ok=True)

    # 저촉심사 결정 검색 예시
    logger.info("=== PTAB Interference Decisions 검색 ===")
    results = search_interference_decisions(_API_KEY, limit=5)
    out = os.path.join(json_dir, "ptab_interferences_search.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"검색 결과 저장: {out}")

    # 저촉심사 번호별 결정 조회 예시 (실제 interferenceNumber로 교체 필요)
    # interference_number = "105678"
    # decisions = get_decisions_by_interference(_API_KEY, interference_number)
    # out2 = os.path.join(json_dir, f"ptab_interference_{interference_number}.json")
    # with open(out2, "w", encoding="utf-8") as f:
    #     json.dump(decisions, f, ensure_ascii=False, indent=2)
    # logger.info(f"저촉심사 결정 저장: {out2}")
