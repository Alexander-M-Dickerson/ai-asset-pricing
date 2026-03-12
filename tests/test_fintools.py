"""Minimal test suite for fintools package."""

import sys
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
import pytest


def test_fintools_imports():
    """Package imports without error."""
    import fintools
    assert hasattr(fintools, "__version__")


def test_panel_lag():
    """Panel lagging produces correct shifts."""
    from fintools.lags import panel_lag

    df = pd.DataFrame({
        "permno": [1, 1, 1, 2, 2, 2],
        "date": pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"] * 2),
        "x": [10.0, 20.0, 30.0, 100.0, 200.0, 300.0],
    })
    result = panel_lag(df, id_col="permno", date_col="date", cols="x", periods=1)
    # Result should be a DataFrame with the lagged column
    assert "x_lag1" in result.columns
    # First obs per group should be NaN
    assert np.isnan(result["x_lag1"].iloc[0])
    assert np.isnan(result["x_lag1"].iloc[3])
    # Second obs should equal first obs value
    assert result["x_lag1"].iloc[1] == 10.0
    assert result["x_lag1"].iloc[4] == 100.0


def test_rolling_betas_shape():
    """Rolling betas returns correct shape."""
    from fintools.betas import rolling_betas

    np.random.seed(42)
    n = 120
    dates = pd.date_range("2010-01-31", periods=n, freq="ME")
    returns = pd.DataFrame({
        "permno": [1] * n,
        "date": dates,
        "ret": np.random.randn(n) * 0.05,
    })
    factors = pd.DataFrame({
        "date": dates,
        "mktrf": np.random.randn(n) * 0.04,
    })
    result = rolling_betas(
        returns, factors, id_col="permno", date_col="date",
        ret_col="ret", factor_cols=["mktrf"], window=60, min_obs=36,
    )
    assert len(result) == n
    assert "beta_mktrf" in result.columns
    # First 35 obs should be NaN (min_obs=36)
    assert result["beta_mktrf"].iloc[:35].isna().all()


def test_pybondlab_imports():
    """PyBondLab imports without error."""
    import PyBondLab as pbl
    assert hasattr(pbl, "StrategyFormation")
    assert hasattr(pbl, "SingleSort")
    assert hasattr(pbl, "DoubleSort")
