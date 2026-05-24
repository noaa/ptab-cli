# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 개발 환경 설치
uv sync --all-groups

# 로컬 실행 (editable install 불필요, .venv/bin/ptab 사용)
.venv/bin/ptab proc search --q "petitionerPartyName:Apple"

# 린트
uv run ruff check src/

# 빌드 및 PyPI 배포
uv build
uv run twine upload dist/*
```

개발 시 `.env` 파일에 `USPTO_API_KEY=...`를 넣으면 `python-dotenv`가 자동 로드한다.

## Architecture

### 계층 구조

```
cli.py          ← Click 명령 정의, 옵션 파싱, 쿼리 조합
  ↓
proceedings.py  ← 도메인별 API 함수 (search_*, get_*, download_*)
documents.py
decisions.py
appeals.py
interferences.py
  ↓
client.py       ← HTTP 레이어 (get, get_and_save_json, download_binary, download_url)
  ↓
config.py       ← API 키·타임아웃 우선순위 결정, ~/.ptab-cli.toml 읽기/쓰기
output.py       ← table | json | csv 렌더러 (rich 사용)
```

### 핵심 설계 결정

**API 키 우선순위** (`config.py`): `--api-key` CLI 옵션 → `USPTO_API_KEY` 환경변수 → `~/.ptab-cli.toml`.

**도메인 모듈 패턴**: 각 모듈(`proceedings.py` 등)은 `search_*`, `get_*`, `download_*` 세 종류의 함수를 제공한다. `cli.py`는 이 함수들만 호출하며 HTTP를 직접 다루지 않는다.

**download 명령**: `/search/download` 엔드포인트는 ZIP이 아닌 JSON을 반환한다. `download_binary` 대신 `get_and_save_json`을 사용한다 (이슈 #5 수정).

**출력 필드 정의** (`output.py`): `PROC_FIELDS`, `DECISION_FIELDS` 등은 `("dotted.key.path", "헤더", no_wrap)` 튜플 리스트다. `_get_nested()`가 점 표기로 중첩 dict를 접근한다.

**`_RESULT_BAG_KEYS`** (`output.py`): USPTO API는 응답을 `patentTrialProceedingDataBag` 같은 래퍼 키에 담는다. 이 목록으로 키를 자동 탐지해 결과 리스트를 꺼낸다.

**`_build_query`** (`cli.py`): `--petitioner`, `--type`, `--from/--to` 같은 편의 옵션을 Lucene `AND` 절로 합쳐 `q` 파라미터를 구성한다.

### 버전 관리

버전은 `src/ptab_cli/__init__.py`의 `__version__`과 `pyproject.toml`의 `version` 두 곳을 함께 수정한다.
