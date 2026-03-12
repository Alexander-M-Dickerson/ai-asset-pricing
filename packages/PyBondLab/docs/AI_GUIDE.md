# PyBondLab AI Agent Guide

> Rules, decision trees, and code templates for Claude Code agents working with PyBondLab.

---

## OVERVIEW

PyBondLab constructs long-short factor portfolios from corporate bond panel data. The pipeline:

```
Strategy → StrategyFormation.fit() → FormationResults
  │                                       │
  ├─ SingleSort                           ├─ get_long_short()      → (EW, VW) Series
  ├─ DoubleSort                           ├─ get_turnover()        → (EW, VW) DataFrame
  ├─ Momentum                             ├─ get_characteristics() → (EW, VW) dict
  ├─ LTreversal                           ├─ get_long_short_ex_post() → (requires filters)
  └─ WithinFirmSort                       └─ summary()             → print stats
```

**Batch wrappers** process multiple signals: `BatchStrategyFormation`, `BatchWithinFirmSortFormation`, `DataUncertaintyAnalysis`, `BatchAssayAnomaly`.

### File-to-Purpose (compact)

| File | Purpose |
|------|---------|
| `PyBondLab.py` | Core engine: `StrategyFormation.fit()` |
| `StrategyClass.py` | Strategy definitions (SingleSort, DoubleSort, etc.) |
| `numba_core.py` | All numba JIT kernels (60+ functions) |
| `results.py` | Result container classes |
| `batch.py` | `BatchStrategyFormation` (multi-signal) |
| `batch_withinfirm.py` | `BatchWithinFirmSortFormation` |
| `data_uncertainty.py` | `DataUncertaintyAnalysis` (filter robustness) |
| `batch_assay.py` | `BatchAssayAnomaly` (specification grid) |
| `AnomalyAssayer.py` | `AssayAnomaly` (single-signal spec grid) |
| `FilterClass.py` | Trim/price/bounce/winsorize filters |
| `config.py` | Dataclass configuration |
| `constants.py` | Column names, rating bounds |
| `precompute.py` | Precompute ranks/thresholds per date |
| `naming.py` | `NamingConfig` for factor naming |
| `extract.py` | `extract_panel()` for unified output |
| `rolling_beta.py` | `RollingBeta` estimation |

---

## RULES: MANDATORY

### R1: Data Requirements

Input DataFrame must have these columns (names are configurable via column mapping):

| Column | Default Name | Type | Description |
|--------|-------------|------|-------------|
| Date | `date` | datetime64 | Month-end dates |
| Bond ID | `ID` | object/str | Unique bond identifier |
| Return | `ret` | float | Monthly total return |
| Value Weight | `VW` | float | Market cap (for VW portfolios) |
| Rating | `RATING_NUM` | int/float | Numeric rating 1-22 (optional, needed for rating filters) |
| Price | `PRICE` | float | Bond price (optional, needed for price filters) |
| Signal(s) | user-defined | float | Sorting variable(s) |

**Test data generator:**
```python
from PyBondLab.pbl_test import generate_synthetic_data
data = generate_synthetic_data(n_dates=60, n_bonds=500, seed=42)
# Shape: (24939, 11)
# Columns: date, ID, ret, RATING_NUM, VW, PRICE, signal1, signal2, char1, char2, char3
```

### R2: Column Mapping

If your data uses different column names, map them:

```python
# Option A: fit() parameters (preferred for StrategyFormation)
result = sf.fit(IDvar='cusip', RETvar='ret_vw', VWvar='mcap_e', RATINGvar='spc_rat')

# Option B: columns= dict (preferred for Batch/DUA)
batch = pbl.BatchStrategyFormation(
    data=data,
    columns={'cusip': 'ID', 'ret_vw': 'ret', 'mcap_e': 'VW', 'spc_rat': 'RATING_NUM'},
    signals=['cs', 'mom3_1'],
    ...
)
```

**Corner cases handled automatically:**
- `chars=['spc_rat']` + `RATINGvar='spc_rat'` → output key uses original name `'spc_rat'`
- Source column missing but target exists → silently skips mapping
- Both source and target exist → drops existing target, renames source

### R3: Strategy Selection Decision Tree

```
Is your signal a pre-computed column in the data?
├─ YES → SingleSort(sort_var='column_name')
│         Need conditional double-sort?
│         ├─ YES → DoubleSort(sort_var='signal', sort_var2='cond_var', how='conditional')
│         └─ NO, but need unconditional → DoubleSort(..., how='unconditional')
│
├─ NO, it's cumulative past returns (momentum)
│   └─ Momentum(lookback_period=K, skip=1)
│
├─ NO, it's average past returns (reversal)
│   └─ LTreversal(lookback_period=K, skip=S)
│
└─ Need within-firm bond dispersion?
    └─ WithinFirmSort(sort_var='signal', firm_id_col='PERMNO')
        (HP=1 only, 2 portfolios: HIGH/LOW)
```

**Key parameters for all strategies:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `holding_period` | int | 1 | 1=monthly, 3=quarterly staggered, etc. |
| `num_portfolios` | int | 5 | Quintiles (5), deciles (10), etc. |
| `sort_var` | str | required | Column name to sort on |
| `rebalance_frequency` | str | `'monthly'` | `'quarterly'`, `'semi-annual'`, `'annual'` |
| `rebalance_month` | int | 6 | Month of year for non-monthly rebalancing |

### R4: Fast Path Eligibility

PyBondLab auto-selects the fastest code path. Conditions:

```
Ultra-fast numba path (5-100x speedup):
  ✓ SingleSort only (not DoubleSort/WithinFirmSort)
  ✓ turnover=False
  ✓ chars=None
  ✓ banding_threshold=None
  ✓ No filters applied
  ✓ Monthly rebalancing

Non-staggered fast path (20-100x speedup):
  ✓ rebalance_frequency != 'monthly'
  ✓ SingleSort only
  (turnover/chars/banding all supported)

WithinFirmSort fast path (33x speedup):
  ✓ WithinFirmSort strategy
  ✓ turnover=False
  ✓ chars=None

Batch fast path (bypasses multiprocessing):
  ✓ All ultra-fast conditions met
  ✓ Processes ALL signals via vectorized numba
```

**When fast path is NOT available**, the slow (pandas) path is used automatically. Results are numerically identical.

### R5: Parameter Validation

| Parameter | Valid Values | Common Mistakes |
|-----------|-------------|-----------------|
| `holding_period` | int >= 1 | Don't use 0 |
| `num_portfolios` | int >= 2 | WithinFirmSort always uses 2 |
| `banding_threshold` | float 0-1 or None | e.g. 0.2; not int, not bool |
| `rating` | `'IG'`, `'NIG'`, `(min, max)` tuple, or None | Tuple uses 1-22 scale |
| `how` (DoubleSort) | `'conditional'` or `'unconditional'` | Not `conditional=True` |
| `sort_var2` (DoubleSort) | str | Not `cond_sort_var` |
| `num_portfolios2` (DoubleSort) | int | Not `cond_num_portfolios` |
| `dynamic_weights` | bool | True=VW from d-1, False=VW from formation |
| `filters` | dict or None | `{'adj': 'trim', 'level': 0.2}` |
| `rebalance_frequency` | `'monthly'`, `'quarterly'`, `'semi-annual'`, `'annual'` | String, not int |

### R6: Accessing Results

`StrategyFormation.fit()` returns a `FormationResults` object:

| Method | Returns | Notes |
|--------|---------|-------|
| `get_long_short()` | `(ew_ls, vw_ls)` Series | Long minus short factor returns |
| `get_long_short_ex_post()` | `(ew_ls, vw_ls)` Series | Only available when filters applied |
| `get_turnover()` | `(ew_df, vw_df)` DataFrames | Shape: (T, num_portfolios) |
| `get_characteristics()` | `(ew_dict, vw_dict)` | Keys = char names, values = DataFrame(T, nport) |
| `get_long_leg()` | `(ew, vw)` Series | Top portfolio returns |
| `get_short_leg()` | `(ew, vw)` Series | Bottom portfolio returns |
| `get_returns()` | DataFrame | EW portfolio returns (T, nport) |
| `get_ptf()` | `(ew_df, vw_df)` DataFrames | EW and VW portfolio returns |
| `get_bond_count()` | DataFrame | Bonds per portfolio per date |
| `summary()` | prints to stdout | Summary statistics |
| `save(path)` / `load(path)` | None / FormationResults | Pickle serialization |
| `get_ptf_bins()` | Dict[Timestamp → DataFrame] | Bond-level weights (requires `save_idx=True`) |

### Output Timing Convention

All outputs are indexed by the **return realization date**, not the formation date:

| Output | Index date `t` contains | Formation happened at |
|--------|------------------------|-----------------------|
| Returns | Return earned during month `t` | `t - 1` |
| Turnover | Rebalancing cost for this portfolio | `t - 1` |
| Characteristics | Portfolio characteristics at formation | `t - 1` |
| Weights (`get_ptf_bins()`) | Bond-level EW/VW weights | `t - 1` |

All have `NaN` at `datelist[0]`. This alignment enables: `net_return[t] = return[t] - k * turnover[t]`.

`DataUncertaintyResults` properties:

| Property | Type | Description |
|----------|------|-------------|
| `ew_ex_ante` | DataFrame | EW EA long-short returns (T x configs) |
| `vw_ex_ante` | DataFrame | VW EA long-short returns |
| `ew_ex_post` | DataFrame | EW EP long-short returns |
| `vw_ex_post` | DataFrame | VW EP long-short returns |
| `configs` | DataFrame | Metadata for all configurations |
| `summary()` | DataFrame | Summary stats with NW t-statistics |
| `filter(signal=, hp=, ...)` | DataUncertaintyResults | Subset results |
| `to_excel(path)` | None | Export to Excel |

### R7: Common Pitfalls

**NEVER:**
- Use `conditional=True` for DoubleSort → use `how='conditional'`
- Use `cond_sort_var` → use `sort_var2`
- Call `get_long_short_ex_post()` without filters → raises exception
- Set `holding_period > 1` for WithinFirmSort → raises ValueError
- Use `banding=0.2` (float) → must be int (1 or 2)
- Pre-filter data by rating before passing to StrategyFormation → introduces look-ahead bias
- Use `ret_vw_bgn` as return column unless working with noisy/unadjusted signals

**ALWAYS:**
- Use `generate_synthetic_data()` for testing (self-contained, reproducible)
- Check `result.get_long_short()` returns a tuple of `(ew_series, vw_series)`
- Use `verbose=False` when running in automated pipelines
- Map `ret_vw` → `ret` (not `ret_vwx` unless you want excess returns)

---

## PATTERNS: CODE TEMPLATES

### P1: Basic Factor Construction

```python
import PyBondLab as pbl
from PyBondLab.pbl_test import generate_synthetic_data

data = generate_synthetic_data(n_dates=60, n_bonds=500, seed=42)

# SingleSort quintiles with turnover
strategy = pbl.SingleSort(holding_period=1, sort_var='signal1', num_portfolios=5)
sf = pbl.StrategyFormation(data, strategy=strategy, turnover=True, verbose=False)
result = sf.fit()

ew_ls, vw_ls = result.get_long_short()
# ew_ls: Series(60 dates), mean ≈ 0.000876
# vw_ls: Series(60 dates), mean ≈ 0.001470

ew_turn, vw_turn = result.get_turnover()
# ew_turn: DataFrame(60, 5), one column per portfolio
```

### P2: Batch Processing Many Signals

```python
batch = pbl.BatchStrategyFormation(
    data=data,
    signals=['signal1', 'signal2'],   # Column names in data
    holding_period=1,
    num_portfolios=5,
    turnover=False,                    # Fast numba path when False
    verbose=False,
)
results = batch.fit()

# Access per-signal results
ew_ls, vw_ls = results['signal1'].get_long_short()
```

### P3: Data Uncertainty Analysis

```python
results = pbl.DataUncertaintyAnalysis(
    data=data,
    signals=['signal1'],
    holding_periods=[1, 3],
    filters={
        'trim': [0.2],         # Trim returns > 20%
        'bounce': [0.05],      # Exclude bounce > 5%
    },
    num_portfolios=5,
    verbose=False,
).fit()

# Factor panels: DataFrame with dates as index, configs as columns
ew_ea = results.ew_ex_ante
# Columns: signal1_hp1_baseline, signal1_hp1_trim_0.2, signal1_hp1_bounce_0.05, ...

# Summary with Newey-West t-stats
summary = results.summary()
# Columns: signal, hp, filter_type, ew_ea_mean, ew_ea_tstat, ...
```

### P4: DoubleSort

```python
strategy = pbl.DoubleSort(
    holding_period=1,
    sort_var='signal1',         # Primary sort
    num_portfolios=5,           # 5 portfolios on primary
    sort_var2='signal2',        # Conditioning variable
    num_portfolios2=3,          # 3 groups on conditioning
    how='unconditional',        # or 'conditional'
)
sf = pbl.StrategyFormation(data, strategy=strategy, turnover=True, verbose=False)
result = sf.fit()

ew_ls, vw_ls = result.get_long_short()
```

### P5: Staggered Rebalancing (HP > 1)

```python
# HP=3: Three overlapping cohorts, averaged
strategy = pbl.SingleSort(holding_period=3, sort_var='signal1', num_portfolios=5)
sf = pbl.StrategyFormation(data, strategy=strategy, turnover=True,
                            chars=['char1', 'char2'], verbose=False)
result = sf.fit()

ew_ls, vw_ls = result.get_long_short()
ew_chars, vw_chars = result.get_characteristics()
# ew_chars['char1']: DataFrame(60, 5) — portfolio-level characteristic means
```

### P6: WithinFirmSort

```python
import numpy as np
# Data needs a firm identifier column (e.g., PERMNO)
np.random.seed(42)
unique_ids = data['ID'].unique()
firm_map = {bid: f'FIRM_{i % 50}' for i, bid in enumerate(unique_ids)}
data['PERMNO'] = data['ID'].map(firm_map)

strategy = pbl.WithinFirmSort(
    holding_period=1,           # HP=1 only
    sort_var='signal1',
    firm_id_col='PERMNO',       # Firm identifier column
)
sf = pbl.StrategyFormation(data, strategy=strategy, turnover=False, verbose=False)
result = sf.fit()

ew_ls, vw_ls = result.get_long_short()
# 2 portfolios only: HIGH and LOW (within-firm dispersion)
```

### P7: Non-Staggered Rebalancing

```python
# Quarterly rebalancing: portfolios formed every 3 months, held until next rebalancing
strategy = pbl.SingleSort(
    holding_period=1,
    sort_var='signal1',
    num_portfolios=5,
    rebalance_frequency='quarterly',
    rebalance_month=3,          # March, June, September, December
)
sf = pbl.StrategyFormation(data, strategy=strategy, turnover=False, verbose=False)
result = sf.fit()

ew_ls, vw_ls = result.get_long_short()
# Returns computed EVERY month, ranks fixed between rebalancing dates
```

### P8: Column Mapping (Real Data)

```python
import pandas as pd

# Real bond data with Dickerson column names
data = pd.read_parquet('path/to/cmd_data_raw.parquet')
data = data[data['date'] >= '2002-08-01']  # TRACE-only

batch = pbl.BatchStrategyFormation(
    data=data,
    columns={'cusip': 'ID', 'ret_vw': 'ret', 'mcap_e': 'VW', 'spc_rat': 'RATING_NUM'},
    signals=['cs', 'mom3_1', 'tmat'],
    holding_period=1,
    num_portfolios=5,
    turnover=False,
    rating='IG',                # Investment grade only (RATING_NUM 1-10)
    verbose=True,
)
results = batch.fit()
```

### P9: Filters with StrategyFormation

```python
# Trim filter: exclude returns > 20%
strategy = pbl.SingleSort(holding_period=1, sort_var='signal1', num_portfolios=5)
sf = pbl.StrategyFormation(
    data, strategy=strategy,
    filters={'adj': 'trim', 'level': 0.2},
    verbose=False,
)
result = sf.fit()

ew_ea, vw_ea = result.get_long_short()           # Ex-Ante (raw returns)
ew_ep, vw_ep = result.get_long_short_ex_post()    # Ex-Post (filtered returns)
# EA ≠ EP when filters are applied
```

---

## ARCHITECTURE

### Main Pipeline Call Graph

```
StrategyFormation.fit()
 ├─ _prepare_data()                          # Validate, apply column mapping
 ├─ [fast path check]
 │   ├─ _fit_fast_returns_only()             # Ultra-fast numba path
 │   ├─ _fit_nonstaggered_fast()             # Non-staggered fast path
 │   └─ _fit_withinfirm_fast()              # WithinFirmSort fast path
 ├─ _precompute_data()                       # Ranks, thresholds, date index
 │   ├─ precompute._compute_ranks()          # Percentile-based ranking
 │   ├─ precompute._create_date_index()      # It0, It1, It1m per date
 │   └─ utils_optimized.compute_thresholds() # Numba threshold computation
 ├─ _form_cohort_portfolios()                # Monthly staggered
 │   └─ _form_single_period()               # Per (date, cohort) computation
 │       ├─ numba_core.compute_portfolio_returns_single()
 │       ├─ numba_core.compute_portfolio_weights_single()
 │       └─ numba_core.compute_scaled_weights_single()
 └─ _finalize_results()                      # Build FormationResults
```

### Date Indexing

```
Formation date (t):     Signal observed, bonds ranked, portfolios formed
Return date (t+1):      Returns collected for bonds in portfolio
VW date:                dynamic_weights=True  → t (day before return)
                        dynamic_weights=False → formation date

For HP=3 staggered:
  Cohort 0: formed at t,   returns at t+1
  Cohort 1: formed at t-1, returns at t+1
  Cohort 2: formed at t-2, returns at t+1
  Final return = average across 3 cohorts
```

### Result Indexing

All results (returns, turnover, characteristics) are indexed by **return date**, not formation date.

---

## PERFORMANCE

### Timing Reference (synthetic data, 60 dates x 500 bonds)

| Operation | Fast Path | Slow Path | Speedup |
|-----------|-----------|-----------|---------|
| SingleSort HP=1, no turnover | 0.2s | 0.7s | 3.5x |
| SingleSort HP=1, turnover | 0.6s | 1.6s | 2.7x |
| SingleSort HP=3, turnover | 1.2s | 3.2s | 2.7x |
| DoubleSort HP=1, turnover | 0.7s | 2.4s | 3.5x |
| BatchStrategyFormation (10 signals) | 0.5s | 10s | 20x |
| DataUncertaintyAnalysis (20 configs) | 0.4s | 32s | 75x |
| Non-staggered annual | 0.02s | 3.7s | 180x |
| WithinFirmSort HP=1 | 0.03s | 1.0s | 33x |

### Large Data (2M+ rows)

| Operation | Fast Path | Notes |
|-----------|-----------|-------|
| SingleSort HP=1 | ~1s | Ultra-fast path |
| BatchStrategyFormation 50 signals | ~3s | Vectorized numba |
| DataUncertaintyAnalysis 100 configs | ~5s | Parallel prange |

---

## TAG INDEX

Grep for these tags in `PyBondLab/*.py`:

| Tag | Meaning | Example Grep |
|-----|---------|-------------|
| `@entrypoint` | Public API method/class | `Grep @entrypoint PyBondLab/` |
| `@internal` | Private implementation | `Grep @internal PyBondLab/` |
| `@numba-kernel` | Numba JIT function | `Grep @numba-kernel numba_core.py` |
| `@fast-path` | Optimized code path | `Grep @fast-path PyBondLab.py` |
| `@slow-path` | Reference/fallback path | `Grep @slow-path PyBondLab.py` |
| `@perf-critical` | Hot loop / bottleneck | `Grep @perf-critical` |
| `@data-flow:step-N` | Pipeline step N | `Grep @data-flow PyBondLab.py` |
| `@called-by:X` | Traces callers | `Grep @called-by precompute.py` |
| `@calls:X` | Traces callees | `Grep @calls PyBondLab.py` |
| `@see:docs/X` | Cross-reference | `Grep @see` |

### Finding Key Code

```bash
# Find all public entry points
Grep "@entrypoint" PyBondLab/

# Find fast path conditions
Grep "_can_use_fast_path" PyBondLab/PyBondLab.py

# Find all numba kernels
Grep "@numba-kernel" PyBondLab/numba_core.py

# Find where a specific kernel is called
Grep "compute_portfolio_returns_single" PyBondLab/

# Find pipeline steps
Grep "@data-flow" PyBondLab/PyBondLab.py
```

---

## DETAILED REFERENCE

For the full API surface, see `docs/API_REFERENCE.md`.
