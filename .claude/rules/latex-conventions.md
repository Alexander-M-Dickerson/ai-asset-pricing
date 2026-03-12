---
description: LaTeX structural conventions for empirical finance papers
paths:
  - "**/*.tex"
  - "**/*.bib"
---

# LaTeX Conventions

> **Related files**: `academic-writing.md` for prose style and banned words; `latex-citations.md` for citation verification; `latex-compile.md` for compilation rules.

This file covers structural LaTeX conventions for figures, tables, equations, bibliography, and cross-references.

---

## Section Markers

Delimit every section with comment markers to enable programmatic extraction:

```latex
%% BEGIN introduction
\section{Introduction}
...
%% END introduction

%% BEGIN methodology
\section{Methodology}
...
%% END methodology
```

### Rules
- Keys are lowercase, hyphenated: `trade-intensity`, not `Trade_Intensity`
- Every `\section{}` must have a marker pair
- `%% END key` goes immediately before the next `%% BEGIN key` or `\end{document}`
- Projects define their own registered section keys in the project's `CLAUDE.md`

---

## Figures

- **Formats**: Use PDF for vector graphics and PNG for matplotlib/raster output
- **Axis labels**: Every axis must have a label with units (e.g., "Monthly return (%)")
- **Self-contained captions**: Caption must be readable without the surrounding text
  - State what the figure shows
  - Define key variables
  - Mention sample period
- **No 3D charts** unless the third dimension adds genuine information
- **Crisis shading**: Include on all time-series plots. Common recessions: GFC (2007:12--2009:06), COVID (2020:03--2020:04)

### Example
```latex
\begin{figure}[t]
\centering
\includegraphics[width=\textwidth]{figure/returns_by_decile.pdf}
\caption{Mean monthly returns by portfolio decile.
  Value-weighted returns in percent.
  Sample: January 1963 -- December 2023.}
\label{fig:decile_returns}
\end{figure}
```

---

## Tables

### Self-Contained Captions
Every table caption must be readable standalone:
- State what the table shows
- Define key variables
- Mention the sample period
- Note the unit of measurement (basis points, percentage, etc.)

### Formatting
- Use `booktabs` package: `\toprule`, `\midrule`, `\bottomrule`
- **No vertical lines** (ever)
- Left-align text columns, right-align number columns
- 2--3 significant digits maximum (not computer output)

### Example
```latex
\begin{table}[t]
\centering
\caption{Factor premia before and after transaction costs.
  Monthly long-short returns in percent.
  Sample: January 1963 -- December 2023 (732 months).}
\label{tab:main_results}
\begin{tabular}{lrrr}
\toprule
Factor & Gross & Net & Cost (\%) \\
\midrule
HML & 0.38 & 0.21 & 0.17 \\
UMD & 0.65 & 0.31 & 0.34 \\
\bottomrule
\end{tabular}
\end{table}
```

---

## Significant Digits

Follow Cochrane: report 2--3 significant digits. Readers cannot distinguish 4.56 from 4.57.

```
% Good:
$t$-statistic of 3.2
premium of 45 basis points
$R^2$ of 0.12

% Bad:
$t$-statistic of 3.23456
premium of 45.2371 basis points
$R^2$ of 0.12345
```

---

## Equation Environment Selection

| Content | Environment | When |
|---------|-------------|------|
| Single numbered equation | `equation` | Default for key results |
| Multi-line aligned | `align` | Derivations with alignment points |
| Unnumbered one-off | `equation*` | Brief intermediate steps |
| Cases | `cases` inside `equation` | Piecewise definitions |

- Number equations that are referenced; use `*` variants for those that are not
- Use `\eqref` (never `\ref`) for equation references

---

## Writing Rules for Math Sections

1. **Define on first use**: Every symbol must be defined where it first appears (e.g., "where $\tau$ is the execution delay")
2. **Use `\eqref` for equations**: Always `Eq.~\eqref{eq:main}`, never `Eq.~\ref{eq:main}`
3. **Non-breaking spaces**: Always `Eq.~\eqref{...}`, `Section~\ref{...}`, `Figure~\ref{...}`
4. **Consistent operator style**: Use `\text{}` for words in subscripts: $\lambda^{\text{buy}}$, not $\lambda^{buy}$
5. **Interpretive prose**: Follow each formal result with explanatory text connecting it to the paper's economic argument
6. **Approximation clarity**: Flag first-order approximations explicitly
7. **Units in context**: State whether quantities are in percent, basis points, or decimal when introducing them

---

## Bibliography Hygiene

### Proper Noun Protection
Wrap proper nouns in braces to prevent case folding:
```bibtex
title = {The {TRACE} Enhanced Data Set and Corporate Bond Pricing in the {U.S.}},
title = {The {CAPM} Strikes Back? {A}n Equilibrium Model},
title = {{NYSE} Market Structure and the Pricing of {IPOs}},
```

### Common Protected Terms
`{CAPM}`, `{U.S.}`, `{NYSE}`, `{NASDAQ}`, `{S\&P}`, `{CRSP}`, `{TRACE}`, `{FINRA}`, `{OTC}`, `{IPO}`, `{CEO}`, `{GDP}`, `{Gaussian}`, `{Bayesian}`, `{Fama}`, `{French}`, `{Black}`, `{Scholes}`

### Pre-Submission Checks
- **Duplicates**: Search for papers appearing under multiple keys
- **Unused entries**: Remove `.bib` entries not cited in any `.tex` file
- **Consistency**: All `@article` entries must have `journal`, `year`, `volume`, `pages`
- **Working papers**: Use `@unpublished` or `@misc` with `note = {Working paper}`

---

## Common LaTeX Patterns

```latex
\textit{ex-post}             % Italicize Latin phrases
\textit{ex-ante}
\textit{ceteris paribus}

e.g.,                        % Note comma after
i.e.,                        % Note comma after

$t$-statistic                % Hyphenated, math-mode t
$p$-value                    % Hyphenated, math-mode p
```

---

## Cross-Reference Quick Reference

Always use non-breaking space (`~`) between reference type and command:

```latex
Table~\ref{tab:main}
Figure~\ref{fig:returns}
Section~\ref{sec:methodology}
Eq.~\eqref{eq:main}
```

## Compilation Gotchas

- **`longtable` is LR mode** — you cannot use `\begin{spacing}`, `\begin{justify}`, `\begin{adjustwidth}`, or other paragraph-mode environments inside `longtable`. Place table notes AFTER `\end{longtable}`, not inside it.
- **`tabular` inside `table` is fine** — but `longtable` replaces both `table` and `tabular`, so it has different nesting rules.
- **`inputenc` encoding** — always use `\usepackage[utf8]{inputenc}`, NOT `utf8x` (loads `ucs.sty`, conflicts with modern packages) or `utf` (invalid, causes error). Modern LaTeX (2018+) defaults to UTF-8, making `inputenc` technically redundant but harmless.

## Longtable

`longtable` replaces both `\begin{table}` and `\begin{tabular}`. Do NOT wrap it in `\begin{table}`. Required structure:

1. `\caption{...} \\` immediately after `\begin{longtable}{...}`
2. Header rows + `\endfirsthead`
3. Continuation header + `\endhead`
4. Footer + `\endfoot`
5. Final footer + `\endlastfoot`
6. Data rows
7. `\label{...}` before `\end{longtable}`
8. Table notes go AFTER `\end{longtable}`, never inside it

See `boilerplate/template_main.tex` for a working commented-out example.

## Auto-Generated LaTeX from Data

When writing data strings (company names, tickers, percentages) to `.tex` files, **escape LaTeX specials**:

| Char | Escape | Common source |
|------|--------|---------------|
| `&` | `\&` | Company names (S&P), column headers |
| `%` | `\%` | Percentage values in text |
| `_` | `\_` | Variable names, tickers |
| `#` | `\#` | Rare |
| `$` | `\$` | Currency symbols |

Python helper:
```python
def latex_escape(s: str) -> str:
    for ch, esc in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#'), ('$', r'\$')]:
        s = s.replace(ch, esc)
    return s
```
