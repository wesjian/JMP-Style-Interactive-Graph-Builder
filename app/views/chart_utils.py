# ==========================================
# Chart Utility Functions
# ==========================================
# Float-precision recovery, sigma sanitisation, and statistics helpers
# used by the Graph Builder module.

import numpy as np
import pandas as pd


def f64_series(series):
    """Inverse of the float32 RAM downcast for ONE series — recovers the stored decimal.

    A float32-cached value re-expands into its float64 garbage form when read back
    (0.99 → 0.990000009536743, 1.008 → 1.0080000162124634). numpy prints a float32 with
    the minimal digits that round-trip, so the shortest-repr string round trip recovers
    exactly the decimal the pipeline originally stored. Non-float32 input just gets a
    plain float64 cast.
    """
    s = pd.to_numeric(series, errors='coerce')
    if s.dtype != 'float32':
        return s.astype('float64')
    u, inv = np.unique(s.to_numpy(), return_inverse=True)
    return pd.Series(u.astype(str).astype('float64')[inv], index=s.index)


def strip_float32_noise(df):
    """Frame-wide `f64_series` for user-facing exports/tables — Excel/CSV/JSON show 0.99,
    not 0.990000009536743. Returns a copy with float32 columns as clean float64;
    everything else untouched.
    """
    f32 = [c for c in df.columns if df[c].dtype == 'float32']
    if not f32:
        return df
    out = df.copy()
    for c in f32:
        out[c] = f64_series(out[c])
    return out


def sanitize_sigma(std, mean):
    """Guard the auto ±kσ bands against float-noise σ on constant (quantized) series.

    A CoA where every reading is identical to the instrument's resolution can still
    carry ~1e-8-relative float noise from upstream arithmetic; ±3σ of that noise draws
    a fake band a hair above/below the flat data line and stretches the y-axis into
    1.00800014-style ticks. Relative σ below 1e-6 would require 7+ significant digits
    of recorded measurement precision — orders of magnitude below any real band
    (smallest real signal observed ≈ 2.5e-5 relative) — so collapse it to exactly 0.
    """
    try:
        std_f = float(std)
        if not np.isfinite(std_f) or std_f <= 0:
            return std
        scale = abs(float(mean)) if mean is not None and np.isfinite(float(mean)) else 0.0
        if std_f < (scale * 1e-6 if scale > 0 else 1e-12):
            return 0.0
        return std
    except (TypeError, ValueError):
        return std


def display_mean(series):
    """Mean for a constant display line (CL/±kσ anchor), exact on constant data."""
    v = f64_series(series)
    if v.notna().any():
        mn, mx = v.min(), v.max()
        if mn == mx:
            return mn
    return v.mean()


def band_stats(series):
    """(display mean, sanitized σ) for the CL/±kσ auto lines in one call."""
    v = f64_series(series)
    if v.notna().any():
        mn, mx = v.min(), v.max()
        m = mn if mn == mx else v.mean()
    else:
        m = v.mean()
    return m, sanitize_sigma(v.std(ddof=1), m)
