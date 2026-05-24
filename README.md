# ptab-cli

A command-line tool for querying the USPTO Patent Trial and Appeal Board (PTAB) API directly from your terminal. Search and retrieve IPR/PGR/CBM trial proceedings, decisions, documents, appeal decisions, and interference decisions.

## Installation

```bash
pip install ptab-cli
# or
uv tool install ptab-cli
# or
pipx install ptab-cli
```

## Quick Start

```bash
# 1. Save your API key
ptab configure

# 2. Search IPR proceedings
ptab proc search --q "petitionerPartyName:Apple" --type IPR

# 3. Look up a single trial
ptab proc get IPR2023-00001

# 4. List decisions for a trial
ptab decision list IPR2023-00001
```

## API Key Setup

Priority order (highest first):

| Method | Example |
|---|---|
| CLI option | `ptab proc get IPR2023-00001 --api-key KEY` |
| Environment variable | `export USPTO_API_KEY=KEY` |
| Config file | `ptab configure` → `~/.ptab-cli.toml` |

```bash
ptab configure          # Interactive setup (saves API key + timeout)
ptab configure --show   # Show current configuration
```

Timeout follows the same priority:
- `--timeout N` global option
- `REQUEST_TIMEOUT` environment variable
- `~/.ptab-cli.toml` `[http] timeout` (default: 30s)

## Commands

### proc — Trial Proceedings (IPR/PGR/CBM)

```bash
ptab proc search [--q Q] [--type IPR|PGR|CBM] [--from DATE] [--to DATE] [--limit N] [--sort FIELD]
ptab proc get TRIAL_NUMBER
ptab proc download [--q Q] [--type IPR|PGR|CBM] [--from DATE] [--to DATE] --out FILE.json
```

### decision — Trial Decisions

```bash
ptab decision search [--q Q] [--type TYPE] [--petitioner NAME] [--patent NUMBER] [--from DATE] [--to DATE]
ptab decision get DOC_ID
ptab decision list TRIAL_NUMBER
ptab decision download [--q Q] --out FILE.json
```

### doc — Trial Documents

```bash
ptab doc search [--q Q] [--type TYPE] [--from DATE] [--to DATE]
ptab doc get DOC_ID
ptab doc list TRIAL_NUMBER
ptab doc pdf DOC_ID [--out FILE.pdf]
ptab doc download [--q Q] --out FILE.json
```

### appeal — Appeal Decisions

```bash
ptab appeal search [--q Q] [--from DATE] [--to DATE]
ptab appeal get DOC_ID
ptab appeal list APPEAL_NUMBER
ptab appeal download [--q Q] --out FILE.json
```

### interference — Interference Decisions

```bash
ptab interference search [--q Q] [--from DATE] [--to DATE]
ptab interference get DOC_ID
ptab interference list INTERFERENCE_NUMBER
ptab interference download [--q Q] --out FILE.json
```

## Options

All `search` commands accept:

```
--q TEXT          Lucene query string
--from DATE       Start date (YYYY-MM-DD)
--to DATE         End date (YYYY-MM-DD)
--limit N         Maximum results (default: 25)
--offset N        Page offset (default: 0)
--sort FIELD      Sort field (e.g. "filingDate desc")
--format/-f       Output format: table | json | csv (default: table)
--out FILE        Save output to file (csv/json)
--api-key KEY     API key (one-time override)
```

Global options (placed immediately after `ptab`):

```
--verbose/-v      Debug HTTP request/response logs (stderr)
--timeout N       Request timeout in seconds
--version         Show version
```

## Output Formats

**table** (default) — Terminal-friendly, key fields only:

```
 Trial No.       Type  Filed       Status       Petitioner        Patent No.
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 IPR2023-00001   IPR   2023-01-05  Terminated   Apple Inc.        US9876543

1 results (1 total)
```

**json** — Raw API response, pretty-printed (useful for piping)

**csv** — CSV with headers (UTF-8 BOM, for spreadsheets and data analysis)

## Examples

```bash
# Search Apple IPR filings in 2023
ptab proc search --q "petitionerPartyName:Apple" --type IPR --from 2023-01-01 --to 2023-12-31

# Get a single trial as JSON
ptab proc get IPR2023-00001 --format json

# Save Final Written Decisions to CSV
ptab decision search --type "Final Written Decision" --from 2024-01-01 --format csv --out decisions.csv

# Search decisions by petitioner name
ptab decision search --petitioner Apple --format csv --out apple_decisions.csv

# Search decisions by patent number
ptab decision search --patent US9876543

# Download Samsung IPR proceedings as JSON
ptab proc download --q "petitionerPartyName:Samsung" --type IPR --out samsung_ipr.json

# List documents for a trial
ptab doc list IPR2023-00001

# Download a single document as PDF
ptab doc pdf 171200528
ptab doc pdf 171200528 --out petition.pdf

# Combine Lucene query clauses
ptab proc search --q "statusCategory:Terminated AND trialMetaData.trialTypeCode:IPR"

# Extend timeout for slow connections
ptab --timeout 60 proc search --q "petitionerPartyName:Apple"
```

## Requirements

- Python 3.11+
- USPTO PTAB API key (obtain at [developer.uspto.gov](https://developer.uspto.gov))

## License

MIT
