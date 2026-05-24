# ptab-cli

USPTO PTAB(Patent Trial and Appeal Board) API를 터미널에서 직접 조회하는 CLI 도구.
IPR/PGR/CBM Trial 절차·결정·문서, 항소 결정, 저촉심사 결정을 검색·조회합니다.

## 설치

```bash
pip install ptab-cli
# 또는
uv tool install ptab-cli
# 또는
pipx install ptab-cli
```

## 빠른 시작

```bash
# 1. API 키 저장
ptab configure

# 2. IPR 절차 검색
ptab proc search --q "petitionerPartyName:Apple" --type IPR

# 3. Trial 번호로 단건 조회
ptab proc get IPR2023-00001

# 4. Trial의 결정 목록
ptab decision list IPR2023-00001
```

## API 키 설정

우선순위 (높은 순):

| 방식 | 예시 |
|---|---|
| 명령어 옵션 | `ptab proc get IPR2023-00001 --api-key KEY` |
| 환경변수 | `export USPTO_API_KEY=KEY` |
| 설정 파일 | `ptab configure` → `~/.ptab-cli.toml` |

```bash
ptab configure          # 대화형 설정 (API 키 + 타임아웃 저장)
ptab configure --show   # 현재 설정 확인
```

타임아웃도 동일한 우선순위로 결정됩니다:
- `--timeout N` 글로벌 옵션
- `REQUEST_TIMEOUT` 환경변수
- `~/.ptab-cli.toml` `[http] timeout` (기본: 30초)

## 명령어

### proc — Trial 절차 (IPR/PGR/CBM)

```bash
ptab proc search [--q Q] [--type IPR|PGR|CBM] [--from DATE] [--to DATE] [--limit N] [--sort FIELD]
ptab proc get TRIAL_NUMBER
ptab proc download [--q Q] [--type IPR|PGR|CBM] [--from DATE] [--to DATE] --out FILE.json
```

### decision — Trial 결정

```bash
ptab decision search [--q Q] [--type TYPE] [--petitioner NAME] [--patent NUMBER] [--from DATE] [--to DATE]
ptab decision get DOC_ID
ptab decision list TRIAL_NUMBER
ptab decision download [--q Q] --out FILE.json
```

### doc — Trial 문서

```bash
ptab doc search [--q Q] [--type TYPE] [--from DATE] [--to DATE]
ptab doc get DOC_ID
ptab doc list TRIAL_NUMBER [--category CATEGORY] [--party PARTY]
ptab doc pdf DOC_ID [--out FILE.pdf]
ptab doc download [--q Q] --out FILE.json
```

### appeal — 항소 결정

```bash
ptab appeal search [--q Q] [--from DATE] [--to DATE]
ptab appeal get DOC_ID
ptab appeal list APPEAL_NUMBER
ptab appeal download [--q Q] --out FILE.json
```

### interference — 저촉심사 결정

```bash
ptab interference search [--q Q] [--from DATE] [--to DATE]
ptab interference get DOC_ID
ptab interference list INTERFERENCE_NUMBER
ptab interference download [--q Q] --out FILE.json
```

## 공통 옵션

모든 `search` 명령에 적용:

```
--q TEXT          Lucene 쿼리 문자열
--from DATE       시작일 (YYYY-MM-DD)
--to DATE         종료일 (YYYY-MM-DD)
--limit N         최대 결과 수 (기본: 25)
--offset N        페이지 오프셋 (기본: 0)
--sort FIELD      정렬 필드 (예: "filingDate desc")
--format/-f       출력 포맷: table | json | csv (기본: table)
--out FILE        결과 저장 경로 (csv/json)
--api-key KEY     API 키 (일회성 override)
```

글로벌 옵션 (`ptab` 바로 다음에 위치):

```
--verbose/-v      HTTP 요청/응답 디버그 로그 (stderr)
--timeout N       요청 타임아웃 초
--version         버전 출력
```

## 출력 포맷

**table** (기본) — 터미널 가독성 우선, 핵심 필드만 표시:

```
 Trial No.       Type  Filed       Status       Petitioner        Patent No.
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 IPR2023-00001   IPR   2023-01-05  Terminated   Apple Inc.        US9876543

총 1건 (전체 1건)
```

**json** — API 응답 원문 pretty-print (파이프라인 연계용)

**csv** — 헤더 포함 CSV (스프레드시트·데이터 분석용, UTF-8 BOM)

## 사용 예시

```bash
# 2023년 Apple IPR 청구 검색
ptab proc search --q "petitionerPartyName:Apple" --type IPR --from 2023-01-01 --to 2023-12-31

# Trial 단건 조회 (JSON 출력)
ptab proc get IPR2023-00001 --format json

# 최종 서면 결정 CSV 저장
ptab decision search --type "Final Written Decision" --from 2024-01-01 --format csv --out decisions.csv

# 청구인 이름으로 결정 검색
ptab decision search --petitioner Apple --format csv --out apple_decisions.csv

# 특정 특허번호 관련 결정 검색
ptab decision search --patent US9876543

# Samsung IPR 절차 JSON 다운로드
ptab proc download --q "petitionerPartyName:Samsung" --type IPR --out samsung_ipr.json

# Trial 문서 목록
ptab doc list IPR2023-00001

# 카테고리별 필터링 (FINAL, DECISION, MOTION, Exhibit 등)
ptab doc list IPR2023-00001 --category FINAL

# 제출 주체별 필터링 (BOARD, PETITIONER, PATENT OWNER)
ptab doc list IPR2023-00001 --party BOARD

# 조합 필터
ptab doc list IPR2023-00001 --category FINAL --party BOARD

# 개별 문서 PDF 다운로드
ptab doc pdf 171200528
ptab doc pdf 171200528 --out petition.pdf

# Lucene 쿼리 조합
ptab proc search --q "statusCategory:Terminated AND trialMetaData.trialTypeCode:IPR"

# 타임아웃 연장 (느린 네트워크)
ptab --timeout 60 proc search --q "petitionerPartyName:Apple"
```

## 요구사항

- Python 3.11 이상
- USPTO PTAB API 키 ([developer.uspto.gov](https://developer.uspto.gov) 에서 발급)

## 라이선스

MIT
