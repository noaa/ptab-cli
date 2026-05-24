"""
USPTO ODP PTAB API 공통 HTTP 클라이언트.

재시도/지수 백오프 포함. 이 모듈은 ptab/ 패키지 내 모든 API 스크립트가 공유합니다.
"""

import time
import logging
import requests
import click
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.uspto.gov"
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _to_click_error(e: Exception) -> click.ClickException:
    """requests 예외를 Click이 처리할 수 있는 ClickException으로 변환."""
    if isinstance(e, requests.exceptions.HTTPError):
        status = e.response.status_code if e.response is not None else "?"
        # JSON 오류 응답에서 사람이 읽기 좋은 메시지 추출
        msg = _extract_api_message(e.response) or (e.response.text[:200] if e.response is not None else str(e))
        return click.ClickException(f"API 오류 {status}: {msg}")
    if isinstance(e, requests.exceptions.ConnectionError):
        return click.ClickException("네트워크 연결 실패. 인터넷 연결을 확인하세요.")
    if isinstance(e, requests.exceptions.Timeout):
        return click.ClickException("요청 타임아웃. --timeout 값을 늘려보세요.")
    return click.ClickException(str(e))


def _extract_api_message(response) -> str:
    """API JSON 오류 응답에서 detailedMessage 또는 message를 추출."""
    try:
        body = response.json()
        return body.get("detailedMessage") or body.get("message") or ""
    except Exception:
        return ""


def get(
    path: str,
    api_key: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> Dict[str, Any]:
    """
    GET 요청을 보내고 JSON 응답을 반환합니다.

    Args:
        path: BASE_URL 이후의 경로 (예: "/api/v1/patent/trials/proceedings/search").
        api_key: USPTO API 키 (X-API-KEY 헤더).
        params: URL 쿼리 파라미터 딕셔너리.
        timeout: 요청 타임아웃 (초).
        retries: 최대 재시도 횟수.
        backoff_factor: 지수 백오프 계수.

    Returns:
        JSON 응답 딕셔너리.

    Example:
        >>> data = get("/api/v1/patent/trials/proceedings/search", api_key, params={"q": "IPR2023"})
    """
    url = f"{BASE_URL}{path}"
    headers = {"X-API-KEY": api_key, "accept": "application/json"}

    for attempt in range(retries):
        try:
            logger.info(f"GET {url} params={params}")
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status in RETRY_STATUSES and attempt < retries - 1:
                wait = backoff_factor * (2 ** attempt)
                logger.warning(f"HTTP {status} — {wait}초 후 재시도 ({attempt + 1}/{retries})")
                time.sleep(wait)
            else:
                logger.error(f"GET 요청 실패: {e}")
                raise _to_click_error(e) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"GET 요청 오류: {e}")
            raise _to_click_error(e) from e

    raise click.ClickException(f"GET {url} — {retries}회 재시도 후 실패")


def download_binary(
    path: str,
    api_key: str,
    save_path: str,
    timeout: int = 120,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> str:
    """
    바이너리 파일(PDF, ZIP 등)을 다운로드하여 저장합니다.

    Args:
        path: BASE_URL 이후의 경로.
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로.
        timeout: 요청 타임아웃 (초).
        retries: 최대 재시도 횟수.
        backoff_factor: 지수 백오프 계수.

    Returns:
        저장된 파일의 절대 경로.

    Example:
        >>> path = download_binary("/api/v1/patent/trials/decisions/search/download", api_key, "output.zip")
    """
    import os
    url = f"{BASE_URL}{path}"
    headers = {"X-API-KEY": api_key, "accept": "application/zip"}

    for attempt in range(retries):
        try:
            logger.info(f"파일 다운로드: {url} → {save_path}")
            response = requests.get(url, headers=headers, stream=True, timeout=timeout)
            response.raise_for_status()

            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"다운로드 완료: {save_path}")
            return os.path.abspath(save_path)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status in RETRY_STATUSES and attempt < retries - 1:
                wait = backoff_factor * (2 ** attempt)
                logger.warning(f"HTTP {status} — {wait}초 후 재시도")
                time.sleep(wait)
            else:
                logger.error(f"다운로드 실패: {e}")
                raise _to_click_error(e) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"다운로드 오류: {e}")
            raise _to_click_error(e) from e

    raise click.ClickException(f"다운로드 {url} — {retries}회 재시도 후 실패")


def get_and_save_json(
    path: str,
    api_key: str,
    save_path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 120,
) -> str:
    """
    GET 요청으로 JSON을 받아 파일로 저장합니다.

    /search/download 엔드포인트는 ZIP이 아닌 JSON을 반환하므로
    download_binary 대신 이 함수를 사용합니다.

    Args:
        path: BASE_URL 이후의 경로.
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로 (예: "result.json").
        params: URL 쿼리 파라미터 딕셔너리.
        timeout: 요청 타임아웃 (초).

    Returns:
        저장된 파일의 절대 경로.
    """
    import os
    data = get(path, api_key, params=params, timeout=timeout)
    abs_path = os.path.abspath(save_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    import json as _json
    with open(abs_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON 저장 완료: {abs_path}")
    return abs_path


def download_url(
    full_url: str,
    api_key: str,
    save_path: str,
    timeout: int = 120,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> str:
    """
    전체 URL에서 바이너리 파일을 다운로드하여 저장합니다 (302 리다이렉트 follow 포함).

    Args:
        full_url: 다운로드할 전체 URL.
        api_key: USPTO API 키.
        save_path: 저장할 로컬 파일 경로.
        timeout: 요청 타임아웃 (초).
        retries: 최대 재시도 횟수.
        backoff_factor: 지수 백오프 계수.

    Returns:
        저장된 파일의 절대 경로.
    """
    import os
    headers = {"X-API-KEY": api_key}

    for attempt in range(retries):
        try:
            logger.info(f"파일 다운로드: {full_url} → {save_path}")
            response = requests.get(full_url, headers=headers, stream=True, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"다운로드 완료: {save_path}")
            return os.path.abspath(save_path)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status in RETRY_STATUSES and attempt < retries - 1:
                wait = backoff_factor * (2 ** attempt)
                logger.warning(f"HTTP {status} — {wait}초 후 재시도")
                time.sleep(wait)
            else:
                logger.error(f"다운로드 실패: {e}")
                raise _to_click_error(e) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"다운로드 오류: {e}")
            raise _to_click_error(e) from e

    raise click.ClickException(f"다운로드 {full_url} — {retries}회 재시도 후 실패")
