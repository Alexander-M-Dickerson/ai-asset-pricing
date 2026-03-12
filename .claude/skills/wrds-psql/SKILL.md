---
name: wrds-psql
description: Use this skill when the user needs to query WRDS data via PostgreSQL from the local machine. Covers psql connection using .pgpass credentials, query execution patterns, CSV/parquet export, and best practices for large extractions. Invoke when the user wants to pull data from WRDS (CRSP, OptionMetrics, Compustat) via SQL.
argument-hint: "[query or description of data needed]"
---

# WRDS PostgreSQL Query Skill (Local psql via .pgpass)

Execute WRDS queries directly from the local machine using `psql` with service file authentication. No SSH required.

## CRSP Version Policy

**All CRSP queries MUST use v2 tables:**
- `crsp.dsf_v2` / `crsp.wrds_dsfv2_query` (daily) — NOT `crsp.dsf`
- `crsp.msf_v2` / `crsp.wrds_msfv2_query` (monthly) — NOT `crsp.msf`

v1 is frozen at 2024-12-31. v2 is updated through 2025-12-31+.

v2 eliminates three common v1 error patterns:
1. No `abs(prc)` — prices are always positive (`dlyprcflg` flags bid/ask midpoint)
2. No `msenames` join — ticker, issuer name, exchange are columns in the v2 views
3. No delisting merge — `dlyret`/`mthret` already include delisting returns

For the full column mapping see `.claude/agents/crsp-wrds-expert.md`.

## Examples

- `/wrds-psql` -- interactive guidance for building a query
- `/wrds-psql "daily returns for AAPL in 2024"` -- natural language query description
- `/wrds-psql "SELECT permno, dlycaldt, dlyret FROM crsp.dsf_v2 WHERE permno=14593"` -- direct SQL

## Critical Rule: Single-Line Commands Only

**Always write psql commands as a single line.** Never use `\` line continuation or heredocs. This avoids shell expansion approval prompts.

```bash
# GOOD — single line
psql service=wrds -c "SELECT permno, dlycaldt, dlyret FROM crsp.dsf_v2 WHERE permno = 84398 LIMIT 10;"

# BAD — multi-line
psql service=wrds \
    -c "SELECT permno, dlycaldt, dlyret
        FROM crsp.dsf_v2
        WHERE permno = 84398 LIMIT 10;"
```

For complex queries, write SQL to a file and use `-f`:
```bash
psql service=wrds -f query.sql
```

## Connection

Connection details are in `~/.pg_service.conf` (host, port, database, user); password in `~/.pgpass`.

### Windows

On Windows, `PGSERVICEFILE=... psql` shell syntax does not work. In Python, pass environment variables via `subprocess.run(..., env={...})`:

```python
import os, subprocess
env = os.environ.copy()
env['PGSERVICEFILE'] = os.path.expandvars(r'$APPDATA\postgresql\pg_service.conf')
result = subprocess.run(
    ['psql', '-X', '-w', 'service=wrds', '-c', sql],
    capture_output=True, text=True, timeout=300, env=env,
)
```

In Bash, export first: `export PGSERVICEFILE="$APPDATA/postgresql/pg_service.conf" && psql service=wrds ...`

Check `LOCAL_ENV.md` for exact paths on this machine.

### DUO Two-Factor Authentication

WRDS requires DUO 2FA. The first `psql` connection of a session triggers a push notification — **tell the user to check their phone and approve it**. The connection hangs (up to 60s) until approved. Subsequent connections from the same IP are cached (~24 hours). If the connection times out, DUO is almost always the reason — retry once before diagnosing further.

## Query Patterns

### Inline query
```bash
psql service=wrds -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='crsp' AND table_name='dsf_v2' ORDER BY ordinal_position;"
```

### Query from file (preferred for complex SQL)
```bash
psql service=wrds -f query.sql
```

### Tuples-only output (no headers/footers)
```bash
psql service=wrds -t -A -F',' -c "SELECT permno, dlycaldt, dlyret FROM crsp.dsf_v2 WHERE permno=84398 LIMIT 10"
```
Flags: `-t` (tuples only), `-A` (unaligned), `-F','` (comma field separator).

## Data Export

**Default output is Parquet with metadata.** Every extraction follows this pipeline:

### Step 1: psql → CSV to stdout → pipe into Python → Parquet + metadata.json

This is a single pipeline. Do NOT save intermediate CSV files.

```bash
psql service=wrds -c "COPY (SELECT permno, dlycaldt, dlyret, dlyprc FROM crsp.dsf_v2 WHERE permno = 84398 AND dlycaldt >= '2024-01-01' ORDER BY dlycaldt) TO STDOUT WITH CSV HEADER" | python -c "
import sys, json, pandas as pd
from datetime import datetime, timezone

df = pd.read_csv(sys.stdin)

# Auto-detect and parse date columns
for col in df.columns:
    if col in ('date','datadate','dlycaldt','mthcaldt','exdate','last_date','linkdt','linkenddt','sdate','edate','namedt','nameendt'):
        df[col] = pd.to_datetime(df[col])

# Save parquet
outdir = 'data/crsp_spy_daily'  # ← set per query
import os; os.makedirs(outdir, exist_ok=True)
df.to_parquet(f'{outdir}/data.parquet', index=False, compression='snappy')

# Save metadata
meta = {
    'description': 'SPY daily returns and prices',  # ← set per query
    'sql': 'SELECT permno, dlycaldt, dlyret, dlyprc FROM crsp.dsf_v2 WHERE permno = 84398 AND dlycaldt >= 2024-01-01 ORDER BY dlycaldt',
    'database': 'crsp',
    'tables': ['crsp.dsf_v2'],
    'columns': list(df.columns),
    'n_obs': len(df),
    'date_range': [str(df[next(c for c in df.columns if c in ('date','datadate','dlycaldt','mthcaldt'))].min().date()), str(df[next(c for c in df.columns if c in ('date','datadate','dlycaldt','mthcaldt'))].max().date())] if any(c in df.columns for c in ('date','datadate','dlycaldt','mthcaldt')) else None,
    'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'output_file': 'data.parquet',
    'compression': 'snappy'
}
with open(f'{outdir}/metadata.json', 'w') as f:
    json.dump(meta, f, indent=2, default=str)

print(f'Saved {len(df)} rows to {outdir}/data.parquet')
"
```

**Important:** The Python code above is a template. For each query, customize:
- `outdir` — the subfolder name (e.g., `data/crsp_monthly_sp500`)
- `meta['description']` — what the data is
- `meta['sql']` — the exact SQL used
- `meta['database']` and `meta['tables']` — source database and tables
- Add optional fields like `identifiers`, `filters` when relevant
- **Bloat guard:** If `identifiers` (permnos, secids, tickers, gvkeys) would exceed 50 entries, store a summary instead of the full list: `{"permno": {"count": 2847, "sample": [10107, 14593, 84398], "description": "all NYSE common stocks"}}`

### CSV export (only when user explicitly asks)
```bash
mkdir -p output_dir && psql service=wrds -c "COPY (SELECT ...) TO STDOUT WITH CSV HEADER" > output_dir/output.csv
```

## Schema Discovery

```bash
psql service=wrds -c "\dn" | head -40
psql service=wrds -c "\dt crsp.*"
psql service=wrds -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='crsp' AND table_name='dsf_v2' ORDER BY ordinal_position;"
psql service=wrds -c "SELECT COUNT(*), MIN(dlycaldt), MAX(dlycaldt) FROM crsp.dsf_v2;"
```

## Common Databases and Key Tables

| Schema | Table | Description | Key Columns |
|--------|-------|-------------|-------------|
| `crsp` | `dsf_v2` | Daily stock file (v2) | permno, dlycaldt, dlyret, dlyprc, dlyvol, dlycap, shrout |
| `crsp` | `dsi` | Daily S&P index | date, sprtrn, spindx, vwretd |
| `crsp` | `msf_v2` | Monthly stock file (v2) | permno, mthcaldt, mthret, mthprc, mthcap |
| `crsp` | `stksecurityinfohist` | Security info (v2) | permno, secinfostartdt, secinfoenddt, ticker, cusip |
| `crsp` | `stkdelists` | Delisting events (v2) | permno, dlstdt; rarely needed — v2 returns include delisting |
| `optionm` | `opprcd{YYYY}` | Option prices (yearly) | secid, date, exdate, cp_flag, strike_price(/1000!), best_bid, best_offer, impl_volatility, delta |
| `optionm` | `securd` | Security reference | secid, ticker, cusip, index_flag |
| `optionm` | `stdopd` | Standardized options | secid, date, days, impl_volatility, delta |
| `optionm` | `zerocd` | Zero-coupon rates | date, days, rate |
| `comp` | `funda` | Annual fundamentals | gvkey, datadate, fyear, at, lt, seq, ceq, pstk, pstkrv, txditc, ni, ib, revt, csho, prcc_f; **filters: indfmt='INDL', datafmt='STD', popsrc='D', consol='C'** |
| `comp` | `fundq` | Quarterly fundamentals | gvkey, datadate, fqtr, rdq, atq, seqq, ceqq, pstkq, pstkrq, ibq, saleq, cshoq |
| `crsp` | `ccmxpf_lnkhist` | CRSP-Compustat link | gvkey, lpermno, linkdt, linkenddt, linktype, linkprim |
| `wrdsapps` | `opcrsphist` | OptionMetrics-CRSP link | secid, permno, sdate, edate |
| `contrib` | `global_factor` | JKP pre-computed factors (443 cols, 93 countries) | permno, gvkey, date, eom, excntry, obs_main, common, exch_main, primary_sec, me, ret, ret_exc, be_me, beta_60m, size_grp; **always filter: excntry='USA' AND date range** |
| `contrib` | `dickerson_bonds_monthly` | Dickerson cleaned TRACE bond data (140 cols, monthly) | cusip, date, issuer_cusip, permno, gvkey, ret_vw, cs(credit spread), md_dur, ytm, spc_rat(1=AAA,10=BBB-,22=D), mom12_1; **multiple rows per issuer per month** |
| `contrib` | `dickerson_bonds_daily` | Dickerson daily bond prices/analytics (43 cols, daily) | cusip_id, trd_exctn_dt, pr(clean price), prfull(dirty price), credit_spread, mod_dur, ytm, prc_bid, prc_ask, trade_count, qvolume, dvolume, spc_rating(1-22); **30M rows, always filter trd_exctn_dt; column names differ from monthly** |

## Known Gotchas

1. **OptionMetrics strike_price** — stored as strike * 1000. Always `strike_price / 1000.0` in queries.
2. **OptionMetrics yearly tables** — option prices are partitioned by year: `optionm.opprcd1996`, `optionm.opprcd1997`, ..., `optionm.opprcd2025`. Use `UNION ALL` across years or query one at a time.
3. **CRSP column names** — `crsp.dsi` uses `date` (not `caldt`), `spindx` (not `sprindx`). v2 daily uses `dly` prefix (`dlycaldt`, `dlyret`, `dlyprc`); monthly uses `mth` prefix (`mthcaldt`, `mthret`). Do NOT use v1 names (`date`, `ret`, `prc`) with v2 tables — they produce hard errors, and PostgreSQL HINTs may suggest wrong columns (e.g., `disfacpr` instead of the correct `dlycumfacpr`).
4. **Numeric precision** — PostgreSQL returns `numeric` type for many WRDS columns. When loading into Python, cast to `float64`.
5. **Large queries — always chunk** — WRDS may timeout on queries returning millions of rows.
   - Break by date ranges (1-year windows): `WHERE dlycaldt >= '2020-01-01' AND dlycaldt < '2021-01-01'`
   - Or batch by ~50 PERMNOs per query for cross-sectional pulls
   - Save intermediate chunks for resume-friendliness: `if os.path.exists(chunk_file): continue`
6. **COPY vs SELECT** — `COPY ... TO STDOUT` is much faster than piping `SELECT` output for large extractions.
7. **NULL handling** — many columns have NULLs (missing returns, missing prices). Always consider `WHERE ret IS NOT NULL` or handle in downstream code.
8. **SPY identifiers** — CRSP PERMNO: 84398. OptionMetrics SECID: 109820. SPX SECID: 108105.
9. **CCM linking filters** — always filter: `linktype IN ('LC','LU') AND linkprim IN ('P','C')` and check date overlap.
10. **CCM link column name** — the PERMNO column in `crsp.ccmxpf_lnkhist` is `lpermno`, not `permno`. Always alias: `l.lpermno AS permno`.
11. **CCM active links** — `linkenddt` is NULL for currently active links. Always use `COALESCE(linkenddt, '9999-12-31')`.
12. **Compustat standard filters** — every `comp.funda`/`comp.fundq` query MUST include: `indfmt='INDL' AND datafmt='STD' AND popsrc='D' AND consol='C'`. Omitting these produces duplicate rows.
13. **Global Factor Data size** — `contrib.global_factor` has 30M+ rows (12.2M for USA). ALWAYS filter by `excntry` AND `eom`/`date` range. Never query without both filters or the query will timeout.
14. **Dickerson bond data: multiple rows per issuer** — `contrib.dickerson_bonds_monthly` has one row per bond tranche per month. Apple has ~44 tranches. Aggregate by `issuer_cusip` or `permno` with face-value weighting for firm-level.
15. **Dickerson bond ratings** — `spc_rat`/`mdc_rat` are numeric (1=AAA/Aaa, 10=BBB-/Baa3, 22=Default). Investment grade: `spc_rat <= 10`. High yield: `spc_rat BETWEEN 11 AND 21`.
16. **Dickerson `cs_sprd` is NOT credit spread** — it's the Corwin-Schultz high-low spread estimator (a liquidity measure). The actual credit spread column is `cs`.
17. **Dickerson daily bond column names differ from monthly** — daily uses `cusip_id` (not `cusip`), `trd_exctn_dt` (not `date`), `credit_spread` (not `cs`), `mod_dur` (not `md_dur`), `spc_rating` (not `spc_rat`). Always check which table you're querying.
18. **Dickerson daily bonds: sparse panel** — bonds only appear on days they trade. ~30M rows total. Return computation requires LAG() over consecutive trading days. Always filter `trd_exctn_dt`.
19. **Dickerson daily bonds: no issuer_cusip** — daily table lacks `issuer_cusip`. Join to monthly table (`d.cusip_id = m.cusip AND DATE_TRUNC('month', d.trd_exctn_dt) = DATE_TRUNC('month', m.date)`) for issuer-level grouping.
20. **First-call timeout** — the first `psql` call in a session often triggers DUO 2FA and hangs 30-60s. Do not kill it — accept the push. Retry once before diagnosing.
21. **CRSP `nameendt` spelling** — `crsp.msenames` uses `nameendt` (single d), NOT `nameenddt`. Compare with `linkenddt` in `ccmxpf_lnkhist` which IS double-d. This is the #1 CRSP column-name typo. (v2 note: this table is rarely needed — v2 views embed security info directly.)
22. **WRDS data lag** — CRSP, Compustat, and other WRDS databases lag months behind the current date. Never use the current year in smoke tests or data validation. Use a historical year (e.g., 2022) guaranteed to be fully populated.

## Best Practices

1. **Always filter by date first** — date columns are indexed; this dramatically reduces scan time.
2. **Use COPY for bulk export** — `COPY (...) TO STDOUT WITH CSV HEADER` is the fastest way to extract data.
3. **Test with LIMIT** — always test queries with `LIMIT 100` before running full extraction.
4. **Default to Parquet** — always save as `.parquet` (snappy compression) with `metadata.json`. Never save CSV unless the user explicitly asks.
5. **Avoid SELECT *** — specify only the columns you need to reduce data transfer.
6. **Use CTEs for complex joins** — break multi-table queries into `WITH` clauses for readability and to help the query planner.
7. **Never run exploratory queries in parallel** — if one query in a parallel Bash batch fails, Claude Code cancels ALL remaining queries. You lose their results and must re-run individually. Only parallelize queries known to succeed (e.g., different date ranges of a validated query). Run schema-discovery and column-testing queries sequentially.
8. **Always mkdir before writing** — before any file write (`>`, `to_parquet`, `to_csv`), run `mkdir -p <dir>` or `os.makedirs(dir, exist_ok=True)`. Never assume a directory exists.

## Putting It Together: Full Extraction Workflow

```bash
# 1. Test the query
psql service=wrds -c "SELECT permno, dlycaldt, dlyret, dlyprc FROM crsp.dsf_v2 WHERE permno = 84398 AND dlycaldt >= '2024-01-01' ORDER BY dlycaldt LIMIT 10;"

# 2. Extract → Parquet + metadata (single pipeline, no intermediate CSV)
psql service=wrds -c "COPY (SELECT permno, dlycaldt, dlyret, dlyprc FROM crsp.dsf_v2 WHERE permno = 84398 AND dlycaldt >= '2024-01-01' ORDER BY dlycaldt) TO STDOUT WITH CSV HEADER" | python -c "
import sys, json, os, pandas as pd
from datetime import datetime, timezone
df = pd.read_csv(sys.stdin)
for c in df.columns:
    if c in ('date','datadate','dlycaldt','mthcaldt','exdate','last_date'):
        df[c] = pd.to_datetime(df[c])
outdir = 'data/crsp_spy_daily'
os.makedirs(outdir, exist_ok=True)
df.to_parquet(f'{outdir}/data.parquet', index=False, compression='snappy')
date_cols = [c for c in df.columns if c in ('date','datadate','dlycaldt','mthcaldt')]
meta = {
    'description': 'SPY daily returns and prices, 2024+',
    'sql': 'SELECT permno, dlycaldt, dlyret, dlyprc FROM crsp.dsf_v2 WHERE permno = 84398 AND dlycaldt >= 2024-01-01 ORDER BY dlycaldt',
    'database': 'crsp', 'tables': ['crsp.dsf_v2'],
    'columns': list(df.columns), 'n_obs': len(df),
    'date_range': [str(df[date_cols[0]].min().date()), str(df[date_cols[0]].max().date())] if date_cols else None,
    'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'output_file': 'data.parquet', 'compression': 'snappy'
}
with open(f'{outdir}/metadata.json', 'w') as f:
    json.dump(meta, f, indent=2, default=str)
print(f'Saved {len(df)} rows to {outdir}/data.parquet')
"
```

## Instructions

**Python invocation:** Use `python` (not `python3`). If the command fails, check `CLAUDE.local.md` for the full path to the Python executable on this machine (e.g., `C:/Users/name/anaconda3/python.exe` on Windows, `/usr/bin/python3` on Linux).

When given a query request (`$ARGUMENTS`):

1. Identify which WRDS schemas/tables are needed
2. Write the SQL query with appropriate filters and joins
3. Test with `LIMIT 10` to verify correctness
4. Choose a subfolder name: `data/{database}_{short_description}` (e.g., `data/crsp_monthly_sp500`)
5. Run the full pipeline: `psql COPY ... | python` → saves `data.parquet` + `metadata.json`
6. The metadata.json must include at minimum: `description`, `sql`, `database`, `tables`, `columns`, `n_obs`, `fetched_at`, `output_file`
7. Add optional metadata fields when relevant: `date_range`, `identifiers`, `filters`, `compression`
8. Report to the user: subfolder path, row count, date range, and any data quality notes
9. For large extractions, suggest breaking into date ranges
