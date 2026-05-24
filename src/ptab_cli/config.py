"""
설정 파일 관리 및 API 키 우선순위 처리.

우선순위 (높은 순):
  1. CLI --api-key 옵션 (일회성 override)
  2. USPTO_API_KEY 환경변수 (CI/CD, shell profile)
  3. ~/.ptab-cli.toml [auth] api_key (ptab configure로 저장)

개발 환경에서는 python-dotenv가 설치된 경우 .env를 자동 로드하여
환경변수(2번)로 처리된다. 배포 환경에서는 dotenv가 없어도 정상 동작한다.
"""

import os
import sys
import tomllib
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".ptab-cli.toml"


def load() -> dict:
    """~/.ptab-cli.toml을 읽어 dict 반환. 파일 없으면 빈 dict."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save(config: dict) -> None:
    """config dict를 ~/.ptab-cli.toml에 저장."""
    CONFIG_PATH.write_text(_dump_toml(config), encoding="utf-8")


def resolve_api_key(cli_key: Optional[str] = None) -> str:
    """API 키를 우선순위에 따라 결정하여 반환.

    키를 찾지 못하면 빈 문자열 반환. 호출자가 오류 처리 책임.
    """
    # 1. CLI --api-key 옵션
    if cli_key:
        return cli_key

    # 2. 환경변수 (.env 포함 — dev 환경에서 dotenv가 설치된 경우만 로드)
    _try_load_dotenv()
    env_key = os.getenv("USPTO_API_KEY", "")
    if env_key:
        return env_key

    # 3. ~/.ptab-cli.toml
    cfg = load()
    file_key = cfg.get("auth", {}).get("api_key", "")
    return file_key


def resolve_timeout(cli_timeout: Optional[int] = None) -> int:
    """타임아웃을 우선순위에 따라 결정."""
    if cli_timeout is not None:
        return cli_timeout
    _try_load_dotenv()
    env_val = os.getenv("REQUEST_TIMEOUT", "")
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    cfg = load()
    return cfg.get("http", {}).get("timeout", 30)


def require_api_key(cli_key: Optional[str] = None) -> str:
    """API 키를 반환. 없으면 오류 메시지 출력 후 종료."""
    key = resolve_api_key(cli_key)
    if not key:
        import click
        click.echo(
            "오류: USPTO API 키가 설정되지 않았습니다.\n"
            "\n"
            "다음 중 하나로 설정하세요:\n"
            "  ptab configure          # 설정 파일에 저장 (권장)\n"
            "  export USPTO_API_KEY=.. # 환경변수\n"
            "  ptab proc search --api-key KEY ..  # 일회성 옵션",
            err=True,
        )
        sys.exit(1)
    return key


def mask_key(key: str) -> str:
    """API 키를 마스킹하여 반환 (끝 4자리만 표시)."""
    if not key:
        return "(없음)"
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def _try_load_dotenv() -> None:
    """python-dotenv가 설치된 경우(개발 환경)에만 .env를 로드."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _dump_toml(config: dict) -> str:
    """config dict를 TOML 문자열로 직렬화 (tomllib은 read-only라 직접 구현)."""
    lines: list[str] = []
    for section, values in config.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in values.items():
            if val is None or val == "":
                continue
            if isinstance(val, bool):
                lines.append(f"{key} = {'true' if val else 'false'}")
            elif isinstance(val, (int, float)):
                lines.append(f"{key} = {val}")
            else:
                escaped = str(val).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
        lines.append("")
    return "\n".join(lines)
