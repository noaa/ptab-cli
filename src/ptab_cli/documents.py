"""
PTAB Trials — Documents API.

엔드포인트:
  GET /api/v1/patent/trials/documents/search                     - 문서 검색
  GET /api/v1/patent/trials/documents/search/download            - 검색 결과 다운로드
  GET /api/v1/patent/trials/documents/{documentIdentifier}       - 개별 문서 조회
  GET /api/v1/patent/trials/{trialNumber}/documents              - Trial별 문서 목록

독립 실행:
    cd uspto-odp/ptab
    uv run python documents.py
"""

import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import click

from .client import download_url, get, get_and_save_json

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("USPTO_API_KEY", "")
_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))


# ── 공개 함수 ───────────────────────────────────────────────────────────────

def search_documents(
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
    **kwargs,
) -> Dict[str, Any]:
    """
    PTAB Trial 문서를 검색합니다.

    Args:
        api_key: USPTO API 키.
        q: Lucene 쿼리 문자열 (예: "trialNumber:IPR2023-00001").
        sort: 정렬 필드와 방향 (예: "filingDate desc").
        offset: 시작 레코드 위치 (기본 0).
        limit: 반환할 최대 레코드 수 (기본 25).
        facets: 패싯 집계 필드 (쉼표 구분).
        fields: 반환 필드 제한 (쉼표 구분).
        filters: 필드 값 필터.
        range_filters: 범위 필터.
        timeout: 요청 타임아웃 (초).

    Returns:
        문서 검색 결과 딕셔너리.

    Example:
        >>> results = search_documents(api_key, q="trialNumber:IPR2023-00001", limit=10)
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

    return get("/api/v1/patent/trials/documents/search", api_key, params=params, timeout=timeout, **kwargs)


def download_documents_search(
    api_key: str,
    save_path: str,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    offset: int = 0,
    limit: int = 25,
    filters: Optional[str] = None,
    range_filters: Optional[str] = None,
    timeout: int = 120,
    **kwargs,
) -> str:
    """
    PTAB Trial 문서 검색 결과를 파일로 다운로드합니다.

    Args:
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로 (예: "json/documents.zip").
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
        >>> path = download_documents_search(api_key, "json/docs.zip", q="IPR2023-00001")
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

    return get_and_save_json("/api/v1/patent/trials/documents/search/download", api_key, save_path, params=params, timeout=timeout, **kwargs)


def get_document(
    api_key: str,
    document_identifier: str,
    timeout: int = _TIMEOUT,
    **kwargs,
) -> Dict[str, Any]:
    """
    특정 문서 식별자의 PTAB Trial 문서를 조회합니다.

    Args:
        api_key: USPTO API 키.
        document_identifier: 문서 식별자.
        timeout: 요청 타임아웃 (초).

    Returns:
        해당 문서의 상세 정보 딕셔너리.

    Example:
        >>> doc = get_document(api_key, "DOCUMENT-ID-456")
    """
    return get(f"/api/v1/patent/trials/documents/{document_identifier}", api_key, timeout=timeout, **kwargs)


def download_document_pdf(
    api_key: str,
    document_identifier: str,
    save_path: str,
    timeout: int = 120,
    **kwargs,
) -> str:
    """
    문서 ID로 PDF 파일을 다운로드합니다.

    문서 메타데이터에서 fileDownloadURI를 조회한 뒤 API 키 헤더로 다운로드합니다.

    Args:
        api_key: USPTO API 키.
        document_identifier: 문서 식별자 (예: "171200528").
        save_path: 저장할 로컬 파일 경로 (예: "output.pdf").
        timeout: 다운로드 타임아웃 (초).

    Returns:
        저장된 파일의 절대 경로.

    Example:
        >>> path = download_document_pdf(api_key, "171200528", "FWD.pdf")
    """
    meta = get_document(api_key, document_identifier, timeout=30, **kwargs)

    file_uri: Optional[str] = None
    doc_data = meta.get("documentData") or {}
    file_uri = doc_data.get("fileDownloadURI")
    if not file_uri:
        bags = meta.get("patentTrialDocumentDataBag") or []
        if bags:
            file_uri = (bags[0].get("documentData") or {}).get("fileDownloadURI")
    if not file_uri:
        raise click.ClickException(
            f"문서 {document_identifier}의 fileDownloadURI를 찾을 수 없습니다. "
            "'ptab doc get' 으로 응답 구조를 확인하세요."
        )

    return download_url(file_uri, api_key, save_path, timeout=timeout, **kwargs)


def get_documents_by_trial(
    api_key: str,
    trial_number: str,
    timeout: int = _TIMEOUT,
    **kwargs,
) -> Dict[str, Any]:
    """
    특정 Trial 번호에 해당하는 모든 PTAB 문서를 조회합니다.

    Args:
        api_key: USPTO API 키.
        trial_number: Trial 번호 (예: "IPR2023-00001").
        timeout: 요청 타임아웃 (초).

    Returns:
        해당 Trial의 문서 목록 딕셔너리.

    Example:
        >>> docs = get_documents_by_trial(api_key, "IPR2023-00001")
    """
    return get(f"/api/v1/patent/trials/{trial_number}/documents", api_key, timeout=timeout, **kwargs)


# ── 단독 실행 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _API_KEY:
        raise ValueError("USPTO_API_KEY 환경변수가 설정되지 않았습니다.")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(project_root, "json")
    os.makedirs(json_dir, exist_ok=True)

    # 1) 문서 검색 예시
    logger.info("=== PTAB Documents 검색 ===")
    results = search_documents(_API_KEY, limit=5)
    out = os.path.join(json_dir, "ptab_documents_search.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"검색 결과 저장: {out}")

    # 2) Trial별 문서 조회 예시 (실제 trialNumber로 교체 필요)
    # trial_number = "IPR2023-00001"
    # docs = get_documents_by_trial(_API_KEY, trial_number)
    # out2 = os.path.join(json_dir, f"ptab_documents_{trial_number}.json")
    # with open(out2, "w", encoding="utf-8") as f:
    #     json.dump(docs, f, ensure_ascii=False, indent=2)
    # logger.info(f"Trial 문서 저장: {out2}")
