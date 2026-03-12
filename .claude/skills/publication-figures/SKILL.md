---
name: publication-figures
description: "Publication-ready figure conventions for empirical finance and economics. Covers matplotlib styling, color palettes, export settings, and common figure types (time series, decile bars, coefficient plots, event studies). Auto-apply when creating any figure, plot, or visualization."
---

# Publication-Ready Figures

Apply these conventions whenever creating figures. The goal: every figure Claude produces is publication-ready by default — no manual cleanup needed.

## Quick Start

Copy `finance.mplstyle` from this skill directory into the project, then:
```python
import matplotlib.pyplot as plt
plt.style.use('path/to/finance.mplstyle')
```

Or apply inline (no file needed):
```python
import matplotlib.pyplot as plt
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'STIXGeneral', 'DejaVu Serif'],
    'mathtext.fontset': 'stix',
    'font.size': 9,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'axes.linewidth': 0.6,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'lines.linewidth': 1.2,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'legend.frameon': False,
    'figure.dpi': 150,
    'savefig.dpi': 600,
    'savefig.format': 'pdf',
    'pdf.fonttype': 42,
})
```

## Default Aesthetic

- **Fonts:** Times New Roman / STIX (serif, no LaTeX dependency)
- **Spines:** Bottom + left only (no top/right)
- **Grid:** Off by default
- **Ticks:** Outward, 8pt labels
- **Colors:** Okabe-Ito colorblind-safe palette (blue first)
- **Export:** PDF vector, 600 DPI, fonts embedded (type 42)

## Color Palettes

**Default cycle (Okabe-Ito, colorblind-safe):**
```python
PALETTE = ['#377EB8', '#E41A1C', '#4DAF4A', '#984EA3',
           '#FF7F00', '#A65628', '#F781BF', '#999999']
```

**Two-series (long vs short, treatment vs control):**
```python
BLUE_RED = ['#377EB8', '#E41A1C']
```

**Grayscale-safe (for guaranteed print clarity):**
```python
GRAYSCALE = ['#000000', '#555555', '#999999', '#CCCCCC']
# Combine with linestyles: '-', '--', ':', '-.'
```

**Sequential/diverging colormaps:** Use `viridis` or `cividis` (colorblind-safe) for heatmaps. Use `RdBu_r` for diverging (correlation matrices).

## Figure Sizing

| Context | Width (inches) | Use |
|---------|---------------|-----|
| Single column | 3.5 | Most journal figures |
| 1.5 column | 5.25 | Medium panels |
| Double column / full width | 7.0 | Wide multi-panel figures |
| Slide / presentation | 10.0 | Beamer, PowerPoint |

**Aspect ratio:** Default to golden ratio (width / 1.618). Use `square` for heatmaps, `wide` (width / 2.0) for time series.

```python
def set_size(width='single', ratio='golden'):
    widths = {'single': 3.5, 'onehalf': 5.25, 'double': 7.0, 'slide': 10.0}
    ratios = {'golden': 1.618, 'square': 1.0, 'wide': 2.0}
    w = widths.get(width, width)
    r = ratios.get(ratio, ratio)
    return (w, w / r)
```

## Common Figure Types in Empirical Finance

### Time Series
```python
fig, ax = plt.subplots(figsize=set_size('double', 'wide'))
ax.plot(dates, values)
ax.set_xlabel(''); ax.set_ylabel('Return (%)')
```
- Use `ax.axhline(0, color='grey', linewidth=0.5, zorder=0)` for zero reference
- Add NBER recession bands with `ax.axvspan(start, end, alpha=0.1, color='grey')`

### Cumulative Return / Wealth Paths
```python
cumret = (1 + returns).cumprod()
ax.plot(cumret.index, cumret.values)
ax.set_ylabel('Growth of $1')
```
- Start at 1.0 (or 100 for percentage scale)
- Log scale optional for long horizons: `ax.set_yscale('log')`

### Decile Portfolio Bar Chart with Newey-West CIs
```python
# returns_df: DataFrame with columns 0..9 (portfolio return time series)
plot_portfolio_bars(ax, returns_df, show_ls=True, ls_label='10-1')
# Computes means, Newey-West SEs (lag = floor(T^0.25)), 95% CI error bars
# Includes long-short bar with t-stat annotation
```
- Use `plot_portfolio_bars` for any portfolio sort figure — it handles NW SEs automatically
- Short leg (decile 1) colored red, long leg (decile 10) green, L-S bar purple
- t-stat annotated on the L-S bar

For simple bars without CIs (pre-computed means):
```python
plot_decile_bars(ax, means, highlight_extremes=True, spread_label=True)
```

### Coefficient Plot (Forest Plot)
```python
ax.errorbar(coefs, range(len(coefs)), xerr=[coefs-ci_lo, ci_hi-coefs],
            fmt='o', color='#377EB8', capsize=3, markersize=4)
ax.axvline(0, color='grey', linewidth=0.5, linestyle='--')
ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
```

### Event Study (CAR Plot)
```python
days = range(event_window[0], event_window[1] + 1)
ax.plot(days, car, color='#377EB8')
ax.fill_between(days, ci_lo, ci_hi, alpha=0.2, color='#377EB8')
ax.axvline(0, color='grey', linewidth=0.5, linestyle='--')
ax.axhline(0, color='grey', linewidth=0.5)
ax.set_xlabel('Days Relative to Event'); ax.set_ylabel('CAR (%)')
```

### Correlation Heatmap
```python
import seaborn as sns
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
sns.heatmap(corr, mask=mask, cmap='RdBu_r', center=0, vmin=-1, vmax=1,
            annot=True, fmt='.2f', linewidths=0.5, ax=ax,
            cbar_kws={'shrink': 0.8})
```

### Multi-Panel Figures
```python
fig, axes = plt.subplots(1, 3, figsize=set_size('double', 'wide'))
# Label panels
for i, ax in enumerate(axes):
    ax.text(-0.1, 1.05, f'({chr(97+i)})', transform=ax.transAxes,
            fontsize=10, fontweight='bold', va='top')
```

## Export Checklist

Before saving any figure:
1. **Format:** PDF (vector) for papers; PNG (300+ DPI) for slides/web
2. **Font embedding:** `pdf.fonttype = 42` (already in style)
3. **Bbox:** `bbox_inches='tight'` to avoid clipped labels
4. **DPI:** 600 for publication, 150 for screen preview
5. **Size:** Match target journal column width — don't rescale in LaTeX/Word

```python
fig.savefig('figure.pdf', bbox_inches='tight', dpi=600)
# Also save PNG for quick preview:
fig.savefig('figure.png', bbox_inches='tight', dpi=150)
```

## Journal-Specific Overrides

| Journal | Override |
|---------|----------|
| **RFS** | Export as TIF at 300 DPI (photos) or 600 DPI (line art). Fonts: Arial, Courier, Times, Helvetica, Symbol only. |
| **AER** | No shading, no gridlines, no background color. Vector PDF/EPS preferred. Max 9 columns wide including row headings for tables. |
| **JF** | Color figures OK online (free). Color in print costs $500/page. Design for grayscale print compatibility. |
| **Nature** | Sans-serif fonts required (Helvetica/Arial). Override: `plt.rcParams['font.family'] = 'sans-serif'` |

## Do NOT

- Use rainbow colormaps (`jet`, `hsv`) — not perceptually uniform, not colorblind-safe
- Use 3D plots unless the data genuinely requires a third dimension
- Add chartjunk: unnecessary gridlines, borders, background colors
- Scale figures in LaTeX/Word — set correct size in matplotlib, include at 100%
- Use different fonts/sizes across figures in the same paper
- Use LaTeX escapes (`\&`, `\%`, `\_`) in matplotlib text (titles, labels, annotations) — matplotlib's default text engine renders backslashes literally. Write plain `S&P 500`, not `S\&P 500`. LaTeX escapes only work when `plt.rcParams['text.usetex'] = True`, which requires a full LaTeX installation and is NOT enabled by default in our style.
