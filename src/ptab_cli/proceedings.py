"""
PTAB Trials — Proceedings API.

엔드포인트:
  GET /api/v1/patent/trials/proceedings/search            - 절차 검색
  GET /api/v1/patent/trials/proceedings/search/download   - 검색 결과 다운로드
  GET /api/v1/patent/trials/proceedings/{trialNumber}     - 개별 절차 조회

독립 실행:
    cd uspto-odp/ptab
    uv run python proceedings.py
"""

import os
import json
import logging
from typing import Any, Dict, Optional



from .client import download_binary, get

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("USPTO_API_KEY", "")
_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

_BASE_PATH = "/api/v1/patent/trials/proceedings"


# ── 공개 함수 ───────────────────────────────────────────────────────────────

def search_proceedings(
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
    PTAB Trial 절차를 검색합니다.

    Args:
        api_key: USPTO API 키.
        q: Lucene 쿼리 문자열 (예: "trialNumber:IPR2023-00001").
        sort: 정렬 필드와 방향 (예: "filingDate desc").
        offset: 시작 레코드 위치 (기본 0).
        limit: 반환할 최대 레코드 수 (기본 25).
        facets: 패싯 집계 필드 (쉼표 구분).
        fields: 반환 필드 제한 (쉼표 구분).
        filters: 필드 값 필터 (예: "proceedingTypeCategory IPR").
        range_filters: 범위 필터 (예: "filingDate [2023-01-01 TO 2023-12-31]").
        timeout: 요청 타임아웃 (초).

    Returns:
        절차 검색 결과 딕셔너리.

    Example:
        >>> results = search_proceedings(api_key, q="trialNumber:IPR2023-00001")
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

    return get(f"{_BASE_PATH}/search", api_key, params=params, timeout=timeout)


def download_proceedings_search(
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
    PTAB Trial 절차 검색 결과를 파일로 다운로드합니다.

    Args:
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로 (예: "json/proceedings.zip").
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
        >>> path = download_proceedings_search(api_key, "json/proceedings.zip", q="IPR2023")
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

    # 다운로드 엔드포인트는 쿼리 파라미터를 URL에 포함
    from urllib.parse import urlencode
    path = f"{_BASE_PATH}/search/download?{urlencode(params)}"
    return download_binary(path, api_key, save_path, timeout=timeout)


def get_proceeding(
    api_key: str,
    trial_number: str,
    timeout: int = _TIMEOUT,
) -> Dict[str, Any]:
    """
    특정 Trial 번호의 PTAB 절차 정보를 조회합니다.

    Args:
        api_key: USPTO API 키.
        trial_number: Trial 번호 (예: "IPR2023-00001").
        timeout: 요청 타임아웃 (초).

    Returns:
        해당 절차의 상세 정보 딕셔너리.

    Example:
        >>> proc = get_proceeding(api_key, "IPR2023-00001")
        >>> print(proc["trialNumber"])
    """
    return get(f"{_BASE_PATH}/{trial_number}", api_key, timeout=timeout)


# ── 단독 실행 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _API_KEY:
        raise ValueError("USPTO_API_KEY 환경변수가 설정되지 않았습니다.")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(project_root, "json")
    os.makedirs(json_dir, exist_ok=True)

    # 1) 절차 검색 예시 (trialMetaData.trialTypeCode 필드 사용)
    logger.info("=== PTAB Proceedings 검색 ===")
    results = search_proceedings(_API_KEY, q="trialMetaData.trialTypeCode:IPR", limit=5)
    out = os.path.join(json_dir, "ptab_proceedings_search.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"검색 결과 저장: {out}")

    # 2) 개별 절차 조회 예시 (실제 trialNumber로 교체 필요)
    # trial_number = "IPR2023-00001"
    # proc = get_proceeding(_API_KEY, trial_number)
    # out2 = os.path.join(json_dir, f"ptab_proceeding_{trial_number}.json")
    # with open(out2, "w", encoding="utf-8") as f:
    #     json.dump(proc, f, ensure_ascii=False, indent=2)
    # logger.info(f"절차 정보 저장: {out2}")
