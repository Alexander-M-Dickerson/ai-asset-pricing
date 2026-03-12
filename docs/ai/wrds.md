# WRDS Workflow

Use direct PostgreSQL access for WRDS whenever possible.

## Command Rules

- Prefer `psql service=wrds` for CRSP, Compustat, OptionMetrics, Fama-French, and similar datasets.
- Use SSH/SAS only for TAQ or WRDS-server file operations.
- On Windows, `PGSERVICEFILE=... psql` shell syntax does not work. In Python, pass env vars via `subprocess.run(..., env={...})`. In Bash, export first: `export PGSERVICEFILE=... && psql ...`. See `.claude/skills/wrds-psql/SKILL.md` for the full pattern.

## CRSP Version Policy

**Always use CRSP v2** for all new queries and research:
- Daily: `crsp.dsf_v2` (date column: `dlycaldt`). Or the denormalized view `crsp.wrds_dsfv2_query` (98 cols, includes ticker/issuer/exchange).
- Monthly: `crsp.msf_v2` (date column: `mthcaldt`). Or `crsp.wrds_msfv2_query` (91 cols).

v1 tables (`crsp.dsf`, `crsp.msf`) are **frozen at 2024-12-31** and will not receive new data.

Key v2 differences:
- Returns (`dlyret`, `mthret`) already include delisting returns — no manual merge
- Prices are always positive — no `abs(prc)`; `dlyprcflg` flags bid/ask midpoint
- Views are denormalized — `ticker`, `issuernm`, `primaryexch` built in; no `msenames` join
- Pre-computed market cap: `dlycap`, `mthcap`
- String classification codes: `sharetype='NS'`, `primaryexch IN ('N','A','Q')`

Use v1 ONLY for exact replication of published studies that used v1. See `.claude/agents/crsp-wrds-expert.md` for the full v1→v2 column mapping.

## Output Contract

Every extraction should write:

- `data.parquet`
- `metadata.json`

under a short descriptive folder in `data/`.

`metadata.json` should include, at minimum:

- `description`
- `sql`
- `database`
- `tables`
- `columns`
- `n_obs`
- `fetched_at`
- `output_file`

If identifier lists would be large, store a summary rather than the full list.

## Resume-Friendly Extraction Scripts

For multi-batch pulls, scripts should be resume-friendly:
- Save each chunk to a numbered file (e.g., `_partial/chunk_00.parquet`)
- On startup, skip chunks that already exist
- After all chunks succeed, concatenate and write the final Parquet
- Keep `_partial/` for debugging; note in metadata

## Deep References

For schema- or asset-specific work, use these `.claude/agents/` references:

- `crsp-wrds-expert.md`
- `optionmetrics-wrds-expert.md`
- `bonds-wrds-expert.md`
- `taq-wrds-expert.md`
- `ff-wrds-expert.md`
- `wrds-query-orchestrator.md`

These remain the detailed domain references until more knowledge is extracted into shared docs.

For implementation templates, the `.claude/skills/wrds-psql/SKILL.md` file
remains the best detailed reference for query-to-Parquet pipelines.
