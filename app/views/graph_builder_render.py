"""Graph Builder internal render helpers (extracted from page_graph_builder.py).

These eliminate the previous 3x duplication for trendlines (rolling / OLS / LOWESS / forecast)
and 3x duplication for spec lines (UCL/LCL / USL/LSL / Mean / +/-3sigma / +/-6sigma) across
single-panel, stack-Y, and GroupX/GroupY subplot modes. Each helper takes optional row/col for
subplot placement; row=None means single-panel mode (legend shown, full hover)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.views.chart_utils import band_stats


def _add_panel_trace(fig, trace, row=None, col=None):
    if row is not None:
        fig.add_trace(trace, row=row, col=col)
    else:
        fig.add_trace(trace)


def _render_rolling_trendline(fig, df, x_col, y_cols, sym_map, ma_window, *, row=None, col=None):
    """Append rolling-MA trace per Y. Subplot mode (row/col given) hides legend + uses raw y name."""
    is_subplot = row is not None
    for y in y_cols:
        if y not in df.columns:
            continue
        y_num = pd.to_numeric(df[y], errors='coerce')
        window = min(int(ma_window or 20), max(3, len(df) // 10))
        rolling_mean = y_num.rolling(window=window, min_periods=1).mean()
        _add_panel_trace(fig, go.Scatter(
            x=df[x_col], y=rolling_mean, mode='lines',
            name=f"MA({y if is_subplot else sym_map.get(y, y)})",
            showlegend=not is_subplot,
            line=dict(dash='dash', width=2, color='rgba(255,0,0,0.5)'),
            hoverinfo='skip',
        ), row=row, col=col)


def _compute_ols_stats(df, x_col, y):
    """Return dict with fit_line/r2/rmse/eq_str/slope/intercept, or None if too few valid points."""
    if y not in df.columns:
        return None
    y_num = pd.to_numeric(df[y], errors='coerce').reset_index(drop=True)
    x_raw = pd.to_numeric(df[x_col], errors='coerce').reset_index(drop=True)
    use_numeric_x = x_raw.notna().sum() > len(df) * 0.5
    x_num = x_raw.values if use_numeric_x else np.arange(len(y_num))
    valid = y_num.notna() & (x_raw.notna() if use_numeric_x else pd.Series([True] * len(y_num)))
    if valid.sum() <= 2:
        return None
    x_valid = x_num[valid]
    y_valid = y_num[valid].values
    coeffs = np.polyfit(x_valid, y_valid, 1)
    fit_line = np.polyval(coeffs, x_num)
    y_pred = np.polyval(coeffs, x_valid)
    ss_res = np.sum((y_valid - y_pred) ** 2)
    ss_tot = np.sum((y_valid - np.mean(y_valid)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = np.sqrt(np.mean((y_valid - y_pred) ** 2))
    slope, intercept = coeffs
    eq_str = f"y = {slope:.4g}x {'+' if intercept >= 0 else '-'} {abs(intercept):.4g}"
    return dict(fit_line=fit_line, r2=r2, rmse=rmse, eq_str=eq_str, slope=slope, intercept=intercept)


def _render_ols_trendline(fig, df, x_col, y_cols, *, row=None, col=None, mode='single'):
    """Add OLS fit line per Y.
        mode='single'   → showlegend=True; returns list of annotation strings (caller adds one box).
        mode='stack_y'  → showlegend=False; per-Y annotation drawn inside helper; returns None.
        mode='group_xy' → showlegend=False; no annotation; returns None.
    """
    is_subplot = row is not None
    annotation_lines = [] if mode == 'single' else None
    for yi, y in enumerate(y_cols):
        stats = _compute_ols_stats(df, x_col, y)
        if not stats:
            continue
        r2, rmse, eq_str = stats['r2'], stats['rmse'], stats['eq_str']
        x_arr = df[x_col].reset_index(drop=True) if mode == 'group_xy' else df[x_col]
        trace_kw = dict(
            x=x_arr, y=stats['fit_line'], mode='lines',
            name=f"OLS({y}) R²={r2:.3f}",
            line=dict(dash='dot', width=2, color='rgba(0,0,0,0.4)'),
        )
        if is_subplot:
            trace_kw['showlegend'] = False
            if mode == 'group_xy':
                trace_kw['hoverinfo'] = 'skip'
            else:
                trace_kw['hovertemplate'] = f"OLS Fit<br>{eq_str}<br>R²={r2:.4f}<br>RMSE={rmse:.4g}<extra></extra>"
        else:
            trace_kw['hovertemplate'] = f"OLS Fit<br>{eq_str}<br>R²={r2:.4f}<br>RMSE={rmse:.4g}<extra></extra>"
        _add_panel_trace(fig, go.Scatter(**trace_kw), row=row, col=col)

        if mode == 'single':
            annotation_lines.append(f"<b>OLS({y})</b>: {eq_str}  R²={r2:.4f}  RMSE={rmse:.4g}")
        elif mode == 'stack_y':
            _yax_ref = 'y' if yi == 0 else f'y{yi + 1}'
            fig.add_annotation(
                text=f"<b>OLS</b>: {eq_str}  R²={r2:.4f}  RMSE={rmse:.4g}", align='left',
                xref='paper', yref=f'{_yax_ref} domain', x=0.01, y=0.97,
                xanchor='left', yanchor='top', showarrow=False,
                bgcolor='rgba(255,255,255,0.85)', bordercolor='#90CAF9',
                borderwidth=1, borderpad=4,
                font=dict(size=10, family='Consolas, monospace', color='#1a1a2e'),
            )
    return annotation_lines


def _render_lowess_trendline(fig, df, x_col, y_cols, sym_map, *, row=None, col=None):
    """Append LOWESS trace per Y. Silently no-ops if statsmodels missing."""
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess as sm_lowess
    except ImportError:
        return
    is_subplot = row is not None
    for y in y_cols:
        if y not in df.columns:
            continue
        y_num = pd.to_numeric(df[y], errors='coerce')
        x_num = np.arange(len(y_num))
        valid = y_num.notna()
        if valid.sum() <= 5:
            continue
        result = sm_lowess(y_num[valid].values, x_num[valid], frac=0.3)
        valid_idx = np.where(valid)[0]
        _add_panel_trace(fig, go.Scatter(
            x=df[x_col].iloc[valid_idx], y=result[:, 1],
            mode='lines',
            name=f"LOWESS({y if is_subplot else sym_map.get(y, y)})",
            showlegend=not is_subplot,
            line=dict(dash='dash', width=2, color='rgba(0,128,0,0.6)'),
            hoverinfo='skip',
        ), row=row, col=col)


def _render_forecast_trendline(fig, df, x_col, y_cols, sym_map, user_perms):
    """Single-panel only. 3 traces per Y: upper CI (invisible), lower CI (fill='tonexty'),
    forecast mean. Gated by master `fcst_enable` + `fcst_gb` permission; horizon read from `def_fcst_horizon_<N>`."""
    if 'fcst_enable' not in user_perms or 'fcst_gb' not in user_perms:
        return
    try:
        from app.models.forecast import forecast_series
    except ImportError:
        return
    _hz = 5
    for _p in user_perms:
        if isinstance(_p, str) and _p.startswith('def_fcst_horizon_'):
            try:
                _hz = max(1, min(int(_p.replace('def_fcst_horizon_', '')), 50))
            except (ValueError, TypeError):
                pass
            break
    for y in y_cols:
        if y not in df.columns:
            continue
        y_num = pd.to_numeric(df[y], errors='coerce').dropna()
        if len(y_num) < 3:
            continue
        mean_arr, lo_arr, up_arr = forecast_series(y_num.values, horizon=_hz, ci=0.95)
        if np.all(np.isnan(mean_arr)):
            continue
        _fc_x = [f"FCST-{i+1}" for i in range(_hz)]
        fig.add_trace(go.Scatter(x=_fc_x, y=up_arr, mode='lines',
                                 line=dict(color='rgba(0,31,107,0.0)', width=0),
                                 showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=_fc_x, y=lo_arr, mode='lines',
                                 line=dict(color='rgba(0,31,107,0.0)', width=0),
                                 fill='tonexty', fillcolor='rgba(0,31,107,0.15)',
                                 name=f'🔮 CI [{sym_map.get(y, y)}]', hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=_fc_x, y=mean_arr, mode='lines+markers',
                                 line=dict(color='#001F6B', dash='dash', width=1.5),
                                 marker=dict(size=5, color='#001F6B', symbol='diamond'),
                                 name=f'🔮 Forecast [{sym_map.get(y, y)}] (next {_hz})',
                                 hovertemplate=f'<b>{sym_map.get(y, y)}</b>: %{{y:.4g}}<extra></extra>'))


def _build_sigma_cache(df_stat, y_cols, spec_toggles):
    """Pre-compute {y: (m1y, std1y, m2y, std2y)} from df_stat baseline.
    Hoists the date-window slicing out of inner loops (used by all 3 spec-line modes).
    Returns empty dict if no sigma lines requested or date column missing."""
    cache = {}
    has_date = '製造日期' in df_stat.columns
    need_1y = has_date and ('3s1y' in spec_toggles or '6s1y' in spec_toggles)
    need_2y = has_date and ('3s2y' in spec_toggles or '6s2y' in spec_toggles)
    if not (need_1y or need_2y):
        return cache
    max_d = df_stat['製造日期'].max()
    s_1y = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=365))] if need_1y else None
    s_2y = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=730))] if need_2y else None
    for y in y_cols:
        m1y = std1y = m2y = std2y = None
        if need_1y and s_1y is not None and y in s_1y.columns:
            m1y, std1y = band_stats(s_1y[y])
        if need_2y and s_2y is not None and y in s_2y.columns:
            m2y, std2y = band_stats(s_2y[y])
        cache[y] = (m1y, std1y, m2y, std2y)
    return cache


def _render_spec_lines_for_y(fig, df_panel, x_col, y, spec_toggles, sigma_cache, *, row=None, col=None):
    """Render UCL/LCL/USL/LSL/Mean/±3σ/±6σ lines for one Y on one panel.
    sigma_cache should be built once per build via `_build_sigma_cache`.
    Single-panel (row=None): UCL/LCL/USL/LSL show in legend; Mean and sigmas hidden.
    Subplot (row/col given): all spec lines hidden from legend."""
    is_subplot = row is not None
    leg_for_limits = not is_subplot  # UCL/LCL/USL/LSL legend only in single-panel mode

    if 'cl' in spec_toggles:
        if f"{y}_UCL" in df_panel.columns and df_panel[f"{y}_UCL"].notna().any():
            _add_panel_trace(fig, go.Scatter(
                x=df_panel[x_col], y=df_panel[f"{y}_UCL"], mode='lines',
                name=f'{y} UCL', line=dict(color='#e53935', dash='dash'),
                showlegend=leg_for_limits,
            ), row=row, col=col)
        if f"{y}_LCL" in df_panel.columns and df_panel[f"{y}_LCL"].notna().any():
            _add_panel_trace(fig, go.Scatter(
                x=df_panel[x_col], y=df_panel[f"{y}_LCL"], mode='lines',
                name=f'{y} LCL', line=dict(color='#e53935', dash='dash'),
                showlegend=leg_for_limits,
            ), row=row, col=col)
    if 'sl' in spec_toggles:
        if f"{y}_USL" in df_panel.columns and df_panel[f"{y}_USL"].notna().any():
            _add_panel_trace(fig, go.Scatter(
                x=df_panel[x_col], y=df_panel[f"{y}_USL"], mode='lines',
                name=f'{y} USL', line=dict(color='red', width=2),
                showlegend=leg_for_limits,
            ), row=row, col=col)
        if f"{y}_LSL" in df_panel.columns and df_panel[f"{y}_LSL"].notna().any():
            _add_panel_trace(fig, go.Scatter(
                x=df_panel[x_col], y=df_panel[f"{y}_LSL"], mode='lines',
                name=f'{y} LSL', line=dict(color='red', width=2),
                showlegend=leg_for_limits,
            ), row=row, col=col)
    if 'mean' in spec_toggles:
        _mv = pd.to_numeric(df_panel[y], errors='coerce').mean()
        if pd.notna(_mv):
            _add_panel_trace(fig, go.Scatter(
                x=df_panel[x_col], y=[_mv] * len(df_panel), mode='lines',
                name=f'{y} CL', line=dict(color='#616161', dash='solid', width=1.2),
                showlegend=False,
            ), row=row, col=col)

    m1y, std1y, m2y, std2y = sigma_cache.get(y, (None, None, None, None))
    if pd.notna(m1y) and pd.notna(std1y):
        if '3s1y' in spec_toggles:
            for sign, lbl in ((+1, '+3σ(1Y)'), (-1, '-3σ(1Y)')):
                _add_panel_trace(fig, go.Scatter(
                    x=df_panel[x_col], y=[m1y + sign * 3 * std1y] * len(df_panel), mode='lines',
                    name=f'{y} {lbl}', line=dict(color='#ff9800', dash='dashdot', width=1.2),
                    showlegend=False,
                ), row=row, col=col)
        if '6s1y' in spec_toggles:
            for sign, lbl in ((+1, '+6σ(1Y)'), (-1, '-6σ(1Y)')):
                _add_panel_trace(fig, go.Scatter(
                    x=df_panel[x_col], y=[m1y + sign * 6 * std1y] * len(df_panel), mode='lines',
                    name=f'{y} {lbl}', line=dict(color='#6A1B9A', dash='longdash', width=1.2),
                    showlegend=False,
                ), row=row, col=col)
    if pd.notna(m2y) and pd.notna(std2y):
        if '3s2y' in spec_toggles:
            for sign, lbl in ((+1, '+3σ(2Y)'), (-1, '-3σ(2Y)')):
                _add_panel_trace(fig, go.Scatter(
                    x=df_panel[x_col], y=[m2y + sign * 3 * std2y] * len(df_panel), mode='lines',
                    name=f'{y} {lbl}', line=dict(color='#009688', dash='dashdot', width=1.2),
                    showlegend=False,
                ), row=row, col=col)
        if '6s2y' in spec_toggles:
            for sign, lbl in ((+1, '+6σ(2Y)'), (-1, '-6σ(2Y)')):
                _add_panel_trace(fig, go.Scatter(
                    x=df_panel[x_col], y=[m2y + sign * 6 * std2y] * len(df_panel), mode='lines',
                    name=f'{y} {lbl}', line=dict(color='#37474F', dash='longdashdot', width=1.2),
                    showlegend=False,
                ), row=row, col=col)

