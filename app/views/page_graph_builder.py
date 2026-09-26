# ==========================================
# JMP-Style Interactive Graph Builder Module
# ==========================================
# JMP-style interactive graph builder.
# This file holds the callback registration; the static layout lives in
# graph_builder_layout.py and the figure render helpers in graph_builder_render.py.
# Features:
# - Dynamic X/Y/Color/Size/Group axis mapping
# - Multiple chart types: Scatter, Line, Bar, Box, Histogram, Violin, Bubble, Heatmap, Pareto
# - Dynamic filters (pattern matching callbacks)
# - Trend lines (rolling MA / OLS / LOWESS / forecast), facets/subplots, dual Y, data preview
# ==========================================

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State, ALL, MATCH
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import re

from app.core.textutils import build_date_mask, get_filename_template, build_export_filename
from app.core.constants import COLOR_PRIMARY, COLOR_ACCENT
from app.views.graph_builder_style import COLOR_TEXT, COLOR_BORDER
from app.views.graph_builder_render import (
    _render_rolling_trendline, _render_ols_trendline, _render_lowess_trendline,
    _render_forecast_trendline, _build_sigma_cache, _render_spec_lines_for_y,
)
from app.views.chart_utils import sanitize_sigma, f64_series, band_stats, display_mean, strip_float32_noise





# ==========================================
# Callbacks
# ==========================================

def register_graph_builder_callbacks(app, output_base_dir, rule_config, dash_config, shared_ctx):
    """Register all callbacks for Graph Builder."""

    from app.models.data_loader import load_db_data
    write_audit_log = shared_ctx.get('write_audit_log', lambda *a, **kw: None)

    # ── Permission Enforcement: toggle GB UI elements based on role ──
    @app.callback(
        [Output('gb-filter-section', 'style'),
         Output('gb-trendline', 'disabled'),
         Output('gb-data-preview-container', 'style'),
         Output('gb-y2-axis', 'disabled'),
         Output('gb-group-x', 'disabled'), Output('gb-group-y', 'disabled'),
         Output('gb-chart-type', 'options'),
         Output('gb-btn-export-done', 'style'),
         Output('gb-btn-export-chart', 'style'),
         Output('gb-btn-clipboard', 'style'),
         Output('gb-btn-share', 'style'),
         Output('gb-palette-section', 'style'),
         # Y display mode container visibility (Stack Y permission)
         Output('gb-y-display-mode-container', 'style'),
         # Chart type button styles (permission enforcement)
         Output('gb-type-scatter', 'style'),
         Output('gb-type-line', 'style'),
         Output('gb-type-bar', 'style'),
         Output('gb-type-box', 'style'),
         Output('gb-type-histogram', 'style'),
         Output('gb-type-violin', 'style'),
         Output('gb-type-bubble', 'style'),
         Output('gb-type-heatmap', 'style'),
         Output('gb-type-pareto', 'style'),
         Output('gb-type-correlation', 'style')],
        [Input('actual-role', 'data'), Input('role-permissions', 'data')]
    )
    def gb_enforce_permissions(role, perms):
        user_perms = perms.get(role, []) if perms else []
        card_style_local = {'backgroundColor': '#ffffff', 'padding': '20px', 'borderRadius': '4px', 'boxShadow': 'none', 'border': '1px solid #e2e8f0', 'marginBottom': '15px'}

        # Filter section visibility
        filter_style = {} if 'gb_filter' in user_perms else {'display': 'none'}

        # Trendline disabled state
        trendline_disabled = 'gb_trendline' not in user_perms

        # Data preview visibility
        preview_style = {**card_style_local, 'padding': '16px'} if 'gb_data_preview' in user_perms else {'display': 'none'}

        # Y2 Axis disabled
        y2_disabled = 'gb_dual_y' not in user_perms

        # Group X/Y disabled
        gx_disabled = 'gb_group_xy' not in user_perms
        gy_disabled = 'gb_group_xy' not in user_perms

        # Chart type options filtered by permission
        CHART_MAP = {
            'scatter': ('⚪ Scatter', 'gb_chart_scatter'),
            'line': ('📈 Line+Marker', 'gb_chart_line'),
            'bar': ('📊 Bar', 'gb_chart_bar'),
            'box': ('📦 Box Plot', 'gb_chart_box'),
            'histogram': ('📉 Histogram', 'gb_chart_histogram'),
            'violin': ('🎻 Violin', 'gb_chart_violin'),
            'bubble': ('🫧 Bubble', 'gb_chart_bubble'),
            'heatmap': ('🔥 Heatmap', 'gb_chart_heatmap'),
            'pareto': ('📊 Pareto', 'gb_chart_pareto'),
            'correlation': ('🔗 Correlation', 'gb_chart_heatmap'),
        }
        chart_opts = [{'label': label, 'value': val} for val, (label, perm_key) in CHART_MAP.items() if perm_key in user_perms]
        if not chart_opts:
            chart_opts = [{'label': '⚪ Scatter', 'value': 'scatter'}]  # Minimum fallback

        # Export button styles
        export_excel_style = {'display': 'none'} if 'gb_export' not in user_perms else {'backgroundColor': '#43A047', 'color': 'white', 'border': 'none', 'padding': '8px 20px', 'borderRadius': '6px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '140px', 'textAlign': 'center'}
        export_chart_style = {'display': 'none'} if 'gb_export_chart' not in user_perms else {'backgroundColor': '#5C6BC0', 'color': 'white', 'border': 'none', 'padding': '8px 20px', 'borderRadius': '6px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '140px', 'textAlign': 'center'}
        clipboard_style = {'display': 'none'} if 'gb_clipboard_copy' not in user_perms else {'backgroundColor': '#7B1FA2', 'color': 'white', 'border': 'none', 'padding': '8px 20px', 'borderRadius': '6px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '160px', 'textAlign': 'center'}
        share_style = {'display': 'none'} if 'gb_share_link' not in user_perms else {'backgroundColor': COLOR_ACCENT, 'color': 'white', 'border': 'none', 'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '140px', 'textAlign': 'center'}
        palette_style = {'marginBottom': '15px', 'paddingBottom': '12px', 'borderBottom': f'1px solid {COLOR_BORDER}'} if 'gb_custom_palette' in user_perms else {'display': 'none'}

        # Chart type icon button styles — disable unpermitted buttons
        _btn_base = {'padding': '5px 8px', 'fontSize': '13px', 'borderRadius': '4px', 'transition': 'all 0.15s', 'lineHeight': '1'}
        _btn_enabled = {**_btn_base, 'border': f'1px solid {COLOR_BORDER}', 'cursor': 'pointer', 'backgroundColor': '#fff'}
        _btn_disabled = {**_btn_base, 'border': '1px solid #e8e8e8', 'cursor': 'not-allowed', 'backgroundColor': '#f5f5f5', 'opacity': '0.35', 'pointerEvents': 'none'}
        CHART_BTN_PERMS = [
            'gb_chart_scatter', 'gb_chart_line', 'gb_chart_bar', 'gb_chart_box',
            'gb_chart_histogram', 'gb_chart_violin', 'gb_chart_bubble', 'gb_chart_heatmap',
            'gb_chart_pareto',
            'gb_chart_heatmap',  # correlation shares heatmap perm
        ]
        chart_btn_styles = [_btn_enabled if perm in user_perms else _btn_disabled for perm in CHART_BTN_PERMS]

        # Y display mode container (Stack Y) — visible only with gb_subplots permission
        y_display_style = {'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginLeft': '8px'} if 'gb_subplots' in user_perms else {'display': 'none'}

        return (filter_style, trendline_disabled, preview_style, y2_disabled, gx_disabled, gy_disabled, chart_opts,
                export_excel_style, export_chart_style, clipboard_style,
                share_style, palette_style,
                y_display_style,
                *chart_btn_styles)


    @app.callback(
        Output('gb-max-series', 'value'),
        [Input('actual-role', 'data')],
        [State('role-permissions', 'data')]
    )
    def gb_apply_max_series_default(role, perms):
        user_perms = (perms or {}).get(role, []) if perms else []
        for p in user_perms:
            if isinstance(p, str) and p.startswith('def_gb_max_'):
                try: return int(p.replace('def_gb_max_', ''))
                except: pass
        return 20

    @app.callback(
        [Output('gb-legend-checklist', 'options'), Output('gb-legend-checklist', 'value')],
        [Input('actual-role', 'data'), Input('role-permissions', 'data')],
        State('gb-legend-checklist', 'value'),
    )
    def gb_update_legend(role, perms, current_value):
        user_perms = perms.get(role, []) if perms else []
        G_OOB_ITEMS = shared_ctx['G_OOB_ITEMS']
        PERM_MAP = shared_ctx['PERM_MAP']
        opts = []
        for col, lbl, key in G_OOB_ITEMS:
            if not rule_config.get(key, True): continue
            if PERM_MAP[key] not in user_perms: continue
            opts.append({'label': f" {lbl}", 'value': lbl})
        # Preserve user selection across role/perm refresh; drop any value no longer permitted.
        valid_vals = {o['value'] for o in opts}
        preserved = [v for v in (current_value or []) if v in valid_vals]
        return opts, preserved

    # Auto-hide the Alarms section for chart types where it has no effect (only scatter/line render alarms)
    @app.callback(
        Output('gb-legend-section', 'style'),
        [Input('gb-chart-type', 'value'),
         Input('gb-legend-checklist', 'options')],
    )
    def gb_toggle_alarms_visibility(chart_type, opts):
        base = {'alignItems': 'center', 'flexWrap': 'wrap',
                'backgroundColor': '#fff5f5', 'borderRadius': '6px', 'padding': '4px 8px',
                'border': f'1px solid {COLOR_BORDER}'}
        if chart_type in ('scatter', 'line') and opts:
            return {**base, 'display': 'flex'}
        return {**base, 'display': 'none'}

    # ── Time preset buttons → DatePickerRange ──
    # Maps preset clicks to (start_date, end_date) anchored on max('製造日期') for the loaded product.
    # 'All' clears the range so build_date_mask returns the full dataset.
    # Triggers an auto-rebuild when graph was previously built (matches spec/alarms behaviour).
    @app.callback(
        [Output('gb-date-picker-range', 'start_date', allow_duplicate=True),
         Output('gb-date-picker-range', 'end_date', allow_duplicate=True),
         Output('gb-rebuild-signal', 'data', allow_duplicate=True)],
        [Input('gb-btn-all', 'n_clicks'),
         Input('gb-btn-2y', 'n_clicks'), Input('gb-btn-1y', 'n_clicks'),
         Input('gb-btn-6m', 'n_clicks'), Input('gb-btn-3m', 'n_clicks'),
         Input('gb-btn-1m', 'n_clicks'), Input('gb-btn-7d', 'n_clicks'),
         Input('gb-btn-clear-range', 'n_clicks')],
        [State('group-dropdown', 'value'),
         State('gb-built-data', 'data'),
         State('gb-rebuild-signal', 'data')],
        prevent_initial_call=True
    )
    def gb_apply_time_preset(n_all, n_2y, n_1y, n_6m, n_3m, n_1m, n_7d, n_clear,
                              group, built_data, current_signal):
        from dash import ctx
        tid = ctx.triggered_id
        if not tid:
            raise dash.exceptions.PreventUpdate
        # 'All' and explicit clear button → wipe both ends. Bump signal so a no-op
        # (None→None) preset click still triggers rebuild when graph already exists.
        if tid in ('gb-btn-all', 'gb-btn-clear-range'):
            return None, None, (current_signal or 0) + (1 if built_data else 0)
        if not group:
            raise dash.exceptions.PreventUpdate
        try:
            df_stat, *_ = load_db_data(group, output_base_dir, rule_config)
        except Exception:
            raise dash.exceptions.PreventUpdate
        if df_stat.empty or '製造日期' not in df_stat.columns:
            raise dash.exceptions.PreventUpdate
        max_d = pd.to_datetime(df_stat['製造日期'].max())
        if pd.isna(max_d):
            raise dash.exceptions.PreventUpdate
        delta_days = {'gb-btn-2y': 730, 'gb-btn-1y': 365, 'gb-btn-6m': 182,
                      'gb-btn-3m': 91, 'gb-btn-1m': 30, 'gb-btn-7d': 7}.get(tid)
        if delta_days is None:
            raise dash.exceptions.PreventUpdate
        start = (max_d - pd.Timedelta(days=delta_days)).strftime('%Y-%m-%d')
        end = max_d.strftime('%Y-%m-%d')
        next_signal = (current_signal or 0) + (1 if built_data else 0)
        return start, end, next_signal

    # ── Highlight active preset button based on current date range ──
    app.clientside_callback(
        """
        function(sd, ed) {
            var btns = {'gb-btn-all':'All','gb-btn-2y':'2Y','gb-btn-1y':'1Y','gb-btn-6m':'6M','gb-btn-3m':'3M','gb-btn-1m':'1M','gb-btn-7d':'7D'};
            var activeId = null;
            if (!sd && !ed) {
                activeId = 'gb-btn-all';
            } else if (sd && ed) {
                var ms = (new Date(ed) - new Date(sd)) / 86400000;
                // Match the same day-offsets used server-side, with a ±2-day tolerance.
                var presets = [['gb-btn-2y',730],['gb-btn-1y',365],['gb-btn-6m',182],['gb-btn-3m',91],['gb-btn-1m',30],['gb-btn-7d',7]];
                for (var i=0; i<presets.length; i++) {
                    if (Math.abs(ms - presets[i][1]) <= 2) { activeId = presets[i][0]; break; }
                }
            }
            Object.keys(btns).forEach(function(id) {
                var b = document.getElementById(id);
                if (!b) return;
                if (id === activeId) {
                    b.style.backgroundColor = '#001F6B';
                    b.style.color = '#fff';
                    b.style.borderColor = '#001F6B';
                    b.style.fontWeight = '700';
                } else {
                    b.style.backgroundColor = '#fff';
                    b.style.color = '#333';
                    b.style.borderColor = '#E0E0E0';
                    b.style.fontWeight = 'normal';
                }
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-btn-all', 'data-dummy'),
        [Input('gb-date-picker-range', 'start_date'),
         Input('gb-date-picker-range', 'end_date')],
    )

    # ── Update axis options when product changes ──
    @app.callback(
        [Output('gb-x-axis', 'options'), Output('gb-y-axis', 'options'),
         Output('gb-color', 'options'), Output('gb-size', 'options'),
         Output('gb-group-x', 'options'), Output('gb-group-y', 'options'),
         Output('gb-y2-axis', 'options'),
         Output('gb-x-axis', 'value'), Output('gb-y-axis', 'value'),
         Output('gb-variable-palette', 'children')],
        [Input('group-dropdown', 'value'),
         Input('role-permissions', 'data'),
         Input('actual-role', 'data')],
    )
    def gb_update_axis_options(group, perms, role):
        empty_palette = [html.Div("Select a product...", style={'color': '#999', 'fontSize': '12px', 'padding': '15px', 'textAlign': 'center'})]
        if not group:
            return [], [], [], [], [], [], [], None, [], empty_palette

        df_stat, _, sym_map, df_chart_config, _, df_variable_info, _ = load_db_data(group, output_base_dir, rule_config)
        if df_stat.empty:
            return [], [], [], [], [], [], [], None, [], empty_palette

        # CoA Items
        coa_items = df_chart_config['CoAItem'].dropna().unique().tolist() if not df_chart_config.empty and 'CoAItem' in df_chart_config.columns else []
        coa_items = [c for c in coa_items if c in df_stat.columns and c not in ('LotNo', '製造日期', 'SafeLot')
                     and not any(k in c for k in [' Max', ' Min', ' BSL ', ' week ', ' P95 ', ' P50 ', ' P05 ',
                                                   '_UCL', '_LCL', '_USL', '_LSL', '_Resolution', '_DetectionLimit', ' Ratio', ' Shift', ' Trend', ' Sigma'])]

        # Variable Items — Graph Builder palette/axis usage is independent of hover.
        # Strict opt-in: only items explicitly checked under vig:<group>:<item> appear in
        # the palette, axis dropdowns, and color/size/group selectors.
        user_perms = (perms or {}).get(role, []) if perms and role else []
        vi_items = df_variable_info['VariableItem'].tolist() if not df_variable_info.empty and 'VariableItem' in df_variable_info.columns else []
        vi_items = [v for v in vi_items if v in df_stat.columns]
        _vig_prefix = f'vig:{group}:'
        _selected_vig = {p[len(_vig_prefix):] for p in user_perms if isinstance(p, str) and p.startswith(_vig_prefix)}
        vi_items = [v for v in vi_items if v in _selected_vig]

        # Build options
        base_opts = [
            {'label': '📅 Date (製造日期)', 'value': '製造日期'},
            {'label': '🏷️ Lot Number', 'value': 'LotNo'},
        ]
        coa_opts = [{'label': f'📊 {c}', 'value': c} for c in coa_items]
        vi_opts = [{'label': f'🧪 {v}', 'value': v} for v in vi_items]

        xy_opts = base_opts + coa_opts + vi_opts
        color_group_opts = [{'label': '(None)', 'value': ''}] + vi_opts + coa_opts
        panel_opts = [{'label': '(None)', 'value': ''}] + vi_opts + coa_opts

        # Build variable palette with draggable chips
        chip_base = {'display': 'block', 'padding': '3px 8px', 'margin': '1px 0', 'borderRadius': '10px', 'fontSize': '11px', 'cursor': 'grab', 'userSelect': 'none', 'whiteSpace': 'nowrap', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}
        palette_children = []
        # Base variables
        palette_children.append(html.Div("── Base ──", style={'fontSize': '10px', 'color': '#999', 'textAlign': 'center', 'padding': '4px 0', 'borderBottom': '1px solid #eee'}))
        for opt in base_opts:
            palette_children.append(html.Div(opt['label'], **{'data-var': opt['value']}, className='gb-drag-chip', style={**chip_base, 'backgroundColor': '#E3F2FD', 'color': '#1565C0', 'border': '1px solid #90CAF9'}))
        # CoA variables
        if coa_items:
            palette_children.append(html.Div("── CoA Items ──", style={'fontSize': '10px', 'color': '#999', 'textAlign': 'center', 'padding': '4px 0', 'borderBottom': '1px solid #eee'}))
            for c in coa_items:
                palette_children.append(html.Div(f'📊 {c}', **{'data-var': c}, className='gb-drag-chip', style={**chip_base, 'backgroundColor': '#E8F5E9', 'color': '#2E7D32', 'border': '1px solid #A5D6A7'}))
        # Variable items
        if vi_items:
            palette_children.append(html.Div("── Variables ──", style={'fontSize': '10px', 'color': '#999', 'textAlign': 'center', 'padding': '4px 0', 'borderBottom': '1px solid #eee'}))
            for v in vi_items:
                palette_children.append(html.Div(f'🧪 {v}', **{'data-var': v}, className='gb-drag-chip', style={**chip_base, 'backgroundColor': '#FFF3E0', 'color': '#E65100', 'border': '1px solid #FFCC80'}))

        default_x = 'LotNo'
        default_y = [coa_items[0]] if coa_items else []

        return xy_opts, xy_opts, color_group_opts, color_group_opts, panel_opts, panel_opts, xy_opts, default_x, default_y, palette_children

    def _gb_filter_col_opts(group, perms, role):
        """Build the Column dropdown options for a filter row, respecting vig: perms."""
        if not group:
            return []
        from app.models.data_loader import load_db_data
        df_stat, _, sym_map, df_chart_config, _, df_variable_info, _ = load_db_data(group, output_base_dir, rule_config)
        coa_items = df_chart_config['CoAItem'].dropna().unique().tolist() if not df_chart_config.empty else []
        coa_items = [c for c in coa_items if c in df_stat.columns and c not in ('LotNo', '製造日期', 'SafeLot')
                     and not any(k in c for k in [' Max', ' Min', ' BSL ', ' week ', ' P95 ', ' P50 ', ' P05 ',
                                                   '_UCL', '_LCL', '_USL', '_LSL', '_Resolution', '_DetectionLimit', ' Ratio', ' Shift', ' Trend', ' Sigma'])]
        vi_items = df_variable_info['VariableItem'].tolist() if not df_variable_info.empty and 'VariableItem' in df_variable_info.columns else []
        vi_items = [v for v in vi_items if v in df_stat.columns]
        _u_perms = (perms or {}).get(role, []) if perms and role else []
        _vig_prefix = f'vig:{group}:'
        _selected_vig = {p[len(_vig_prefix):] for p in _u_perms if isinstance(p, str) and p.startswith(_vig_prefix)}
        vi_items = [v for v in vi_items if v in _selected_vig]
        return [{'label': c, 'value': c} for c in (['LotNo', '製造日期'] + coa_items + vi_items)]

    def _gb_build_filter_row(idx, col_opts, col_val=None, min_val=None, max_val=None, str_val=None):
        """Render one filter row. Initial Match options include any pre-selected str_val so
        the chips render before gb_populate_filter_str_options fires."""
        if str_val:
            sv = str_val if isinstance(str_val, list) else [str_val]
            str_opts = [{'label': v, 'value': v} for v in sv if v]
        else:
            str_opts = []
        return html.Div(id={'type': 'gb-filter-row', 'index': idx}, children=[
            dcc.Dropdown(id={'type': 'gb-filter-col', 'index': idx}, options=col_opts, value=col_val, placeholder='Column...', style={'width': '200px', 'fontSize': '13px'}),
            dcc.Input(id={'type': 'gb-filter-min', 'index': idx}, type='number', value=min_val, placeholder='Min (numeric)', debounce=True, style={'width': '110px', 'padding': '4px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'fontSize': '13px'}),
            dcc.Input(id={'type': 'gb-filter-max', 'index': idx}, type='number', value=max_val, placeholder='Max (numeric)', debounce=True, style={'width': '110px', 'padding': '4px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'fontSize': '13px'}),
            dcc.Dropdown(id={'type': 'gb-filter-str', 'index': idx}, options=str_opts, value=str_val or None, multi=True, searchable=True, placeholder='Match (pick column first)', style={'width': '300px', 'fontSize': '13px'}),
            html.Button("×", id={'type': 'gb-filter-remove', 'index': idx}, style={'backgroundColor': '#e53935', 'color': 'white', 'border': 'none', 'borderRadius': '50%', 'width': '26px', 'height': '26px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '14px'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '6px', 'flexWrap': 'wrap'})

    # ── Add filter row (pattern matching) ──
    @app.callback(
        [Output('gb-filter-container', 'children', allow_duplicate=True),
         Output('gb-filter-count', 'data', allow_duplicate=True)],
        [Input('gb-add-filter', 'n_clicks'), Input({'type': 'gb-filter-remove', 'index': ALL}, 'n_clicks')],
        [State('gb-filter-container', 'children'), State('gb-filter-count', 'data'),
         State('group-dropdown', 'value'),
         State('role-permissions', 'data'), State('actual-role', 'data')],
        prevent_initial_call=True
    )
    def gb_manage_filters(add_clicks, remove_clicks, current_children, filter_count, group, perms, role):
        ctx = dash.callback_context
        if not ctx.triggered: raise dash.exceptions.PreventUpdate
        trigger = ctx.triggered[0]['prop_id']
        trigger_value = ctx.triggered[0].get('value')

        current_children = current_children or []
        filter_count = filter_count or 0

        # Handle delete — but ignore "phantom" triggers from newly-mounted remove buttons
        # (URL restore creates rows whose n_clicks starts at None; that fires the pattern-
        # matching Input but is NOT a real user click).
        if 'gb-filter-remove' in trigger:
            if not trigger_value:  # None or 0 → not a real click, just a fresh mount
                raise dash.exceptions.PreventUpdate
            try:
                trig_dict = json.loads(trigger.split('.')[0])
                remove_idx = trig_dict['index']
                current_children = [c for c in current_children if c['props'].get('id', {}).get('index') != remove_idx]
                # Rebuild children matching
                new_children = []
                for c in current_children:
                    child_id = None
                    if isinstance(c, dict) and 'props' in c:
                        child_id = c['props'].get('id')
                    if child_id and isinstance(child_id, dict) and child_id.get('index') == remove_idx:
                        continue
                    new_children.append(c)
                return new_children, filter_count
            except Exception:
                return current_children, filter_count

        # Handle add
        if 'gb-add-filter' in trigger:
            filter_count += 1
            idx = filter_count
            col_opts = _gb_filter_col_opts(group, perms, role)
            current_children.append(_gb_build_filter_row(idx, col_opts))
            return current_children, filter_count

        return current_children, filter_count

    # ── Main Build Graph ──
    @app.callback(
        [Output('gb-graph', 'figure'), Output('gb-graph', 'style'),
         Output('gb-data-table', 'data'),
         Output('gb-data-table', 'columns'), Output('gb-built-data', 'data'),
         Output('gb-zone-sync', 'data'),
         Output('gb-graph-resizer', 'style', allow_duplicate=True)],
        [Input('gb-btn-build', 'n_clicks'),
         Input('group-dropdown', 'value'),
         Input('gb-spec-checklist', 'value'),
         Input('gb-legend-checklist', 'value'),
         Input('gb-date-picker-range', 'start_date'),
         Input('gb-date-picker-range', 'end_date'),
         Input('gb-rebuild-signal', 'data')],
        [State('gb-style-config', 'data'),
         State('gb-style-legend-pos', 'value'), State('gb-style-legend-size', 'value'),
         State('gb-axis-config', 'data'),
         State('gb-x-axis', 'value'),
         State('gb-y-axis', 'value'), State('gb-color', 'value'),
         State('gb-size', 'value'),
         State('gb-chart-type', 'value'),
         State('gb-trendline', 'value'),
         State('gb-date-group', 'value'),
         State('gb-group-x', 'value'), State('gb-group-y', 'value'),
         State('gb-y2-axis', 'value'),
         State({'type': 'gb-filter-col', 'index': ALL}, 'value'),
         State({'type': 'gb-filter-min', 'index': ALL}, 'value'),
         State({'type': 'gb-filter-max', 'index': ALL}, 'value'),
         State({'type': 'gb-filter-str', 'index': ALL}, 'value'),
         State('actual-role', 'data'), State('role-permissions', 'data'),
         State('gb-ref-lines-store', 'data'),
         State('gb-built-data', 'data'), State('gb-y-display-mode', 'value'),
         State('gb-group-levels', 'value'), State('gb-ma-window', 'value'),
         State('gb-trace-state-store', 'data'),
         State('gb-max-series', 'value')],
        prevent_initial_call=True
    )
    def gb_build_graph(n_clicks, group, spec_toggles, legend_features,
                       start_date_str, end_date_str, rebuild_signal,
                       style_config, leg_pos, leg_size, axis_config,
                       x_col, y_cols, color_col, size_col,
                       chart_type, trendline, date_group,
                       group_x_col, group_y_col, y2_cols,
                       filter_cols, filter_mins, filter_maxs, filter_strs, role, perms,
                       ref_lines, built_data, y_display_mode, group_levels, ma_window,
                       trace_state_store, max_series):

        ctx = dash.callback_context
        # Collect ALL triggered prop ids — Dash batches simultaneous changes into one fire,
        # but ctx.triggered_id only reflects the first. URL-share/save-config load mutates
        # many stores at once (date picker, style cfg, rebuild signal ...), so checking only
        # the first trigger caused the date-picker guard to swallow a legitimate build.
        trigger_ids = [t['prop_id'].split('.')[0] for t in (ctx.triggered or [])]
        triggered_id = (ctx.triggered[0]['prop_id'] if ctx.triggered else '')
        # rebuild-signal is the consolidated "system says build" trigger (URL share /
        # style+axis Apply / time preset). Treated as user-initiated, same as a direct click.
        user_initiated = 'gb-btn-build' in trigger_ids or 'gb-rebuild-signal' in trigger_ids

        def _wrapper_style(height_px=480):
            """Build the gb-graph-resizer style. Auto-grows for stacked-Y / subplots so the
            whole chart fits without a scrollbar; user can still drag-resize after build."""
            return {
                'height': f'{height_px}px', 'minHeight': '280px',
                'width': '100%', 'minWidth': '420px',
                'resize': 'both', 'overflow': 'auto',
                'border': f'1px dashed {COLOR_BORDER}', 'borderRadius': '4px',
                'position': 'relative',
            }

        # Product change warning — but skip if this fire also includes a Build bump
        # (which happens during URL-share load that switches product + restores config).
        if not user_initiated and 'group-dropdown' in trigger_ids:
            if not built_data:
                raise dash.exceptions.PreventUpdate
            empty = go.Figure()
            empty.update_layout(
                title=f"⚠️ Product changed to {group}. Please re-configure settings and click Build Graph",
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            return empty, {'height': '480px'}, [], [], [], dash.no_update, _wrapper_style()

        # Auto-rebuild guards: skip when triggered by a downstream Input but no graph yet exists.
        # Applies to spec/alarms checklists and the date picker — user must click Build first.
        _auto_triggers = {'gb-spec-checklist', 'gb-legend-checklist', 'gb-date-picker-range'}
        if not user_initiated and any(tid in _auto_triggers for tid in trigger_ids):
            if not built_data:
                raise dash.exceptions.PreventUpdate

        # Ensure y_cols and y2_cols are lists and merge them for processing
        if y_cols is None: y_cols = []
        if isinstance(y_cols, str): y_cols = [y_cols]
        if y2_cols is None: y2_cols = []
        if isinstance(y2_cols, str): y2_cols = [y2_cols]
        
        # Combine all requested Y variables conceptually into y_cols, but preserve order and avoid duplicates
        y_cols = list(dict.fromkeys(y_cols + y2_cols))

        # Enforce per-role max series limit (0 = unlimited)
        try:
            _limit = int(max_series or 0)
        except (TypeError, ValueError):
            _limit = 0
        if _limit > 0 and len(y_cols) > _limit:
            y_cols = y_cols[:_limit]
            y2_cols = [c for c in y2_cols if c in y_cols]

        if not group or not x_col or not y_cols:
            empty = go.Figure()
            empty.update_layout(
                title="⚠️ Please select X-axis and at least one Y-axis (or Y2-axis), then click Build Graph",
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            return empty, {'height': '480px'}, [], [], [], dash.no_update, _wrapper_style()

        df_stat, _, sym_map, df_chart_config, df_action, df_variable_info, _ = load_db_data(group, output_base_dir, rule_config)
        if df_stat.empty:
            empty = go.Figure()
            empty.update_layout(title="⚠️ No data available")
            return empty, {'height': '480px'}, [], [], [], dash.no_update, _wrapper_style()

        # Filter first, then copy — avoids copying the whole DataFrame
        df = df_stat.loc[build_date_mask(df_stat, start_date_str, end_date_str)].copy()

        # go.Figure serialises float32 columns as f4 binary typed arrays (bdata); the browser
        # decodes them at the float64 EXPANSION while σ/CL/limit lines are plain floats at the
        # stored decimals — recover every plotted axis column up front (charts.f64_series).
        for _c in dict.fromkeys([x_col] + (y_cols or []) +
                                [f'{_y}{_suf}' for _y in (y_cols or [])
                                 for _suf in ('_UCL', '_LCL', '_USL', '_LSL')]):
            if _c and _c in df.columns and df[_c].dtype == 'float32':
                df[_c] = f64_series(df[_c])

        # Date grouping pre-processing
        if date_group and date_group != 'none' and '製造日期' in df.columns:
            freq = date_group if date_group != 'none' else None
            if freq:
                _freq_fix = {'ME': 'M', 'QE': 'Q'}
                freq = _freq_fix.get(freq, freq)
                df['__DatePeriod__'] = df['製造日期'].dt.to_period(freq).astype(str)
                x_col = '__DatePeriod__'  # Always use period as X when date grouping is active

        # Apply dynamic filters. Each row has three independent inputs which AND together:
        # • Min   → numeric lower bound (>=)
        # • Max   → numeric upper bound (<=)
        # • Match → multi-select dropdown of distinct values (list of strings)
        # Min/Max ignored on non-numeric columns; Match ignored when the user doesn't pick any.
        for i in range(len(filter_cols or [])):
            col = filter_cols[i] if filter_cols else None
            fmin = filter_mins[i] if filter_mins else None
            fmax = filter_maxs[i] if filter_maxs else None
            fstr = filter_strs[i] if filter_strs else None
            if not col or col not in df.columns: continue
            if fmin in (None, '') and fmax in (None, '') and not fstr: continue

            col_series = df[col]

            # 1) Numeric range filter (Min / Max). Coerces non-numeric to NaN, then drops by mask.
            if fmin not in (None, '') or fmax not in (None, ''):
                col_num = pd.to_numeric(col_series, errors='coerce')
                try:
                    if fmin not in (None, ''): df = df[col_num >= float(fmin)]
                    if fmax not in (None, ''): df = df[col_num <= float(fmax)]
                    col_series = df[col]  # rebind after row trimming
                except (ValueError, TypeError):
                    pass

            # 2) String match. fstr is a list (multi-select dropdown); legacy CSV string
            # still supported for URL-shared / saved configs from the old text-input era.
            # Values containing '*' are treated as glob patterns (e.g. 'A-97*', '*-9*').
            if fstr:
                if isinstance(fstr, str):
                    vals = [v.strip() for v in fstr.split(',') if v.strip()]
                else:
                    vals = [str(v).strip() for v in fstr if str(v).strip()]
                if vals:
                    exact_vals = [v for v in vals if '*' not in v]
                    pattern_vals = [v for v in vals if '*' in v]
                    series_str = col_series.astype(str).str.strip()
                    mask = pd.Series(False, index=df.index)
                    if exact_vals:
                        mask |= series_str.isin(exact_vals)
                    for pat in pattern_vals:
                        # Glob → regex: escape everything then unescape '*' → '.*'. Full-string match.
                        regex = '^' + re.escape(pat).replace(r'\*', '.*') + '$'
                        mask |= series_str.str.match(regex, na=False)
                    df = df[mask]

        if df.empty:
            empty = go.Figure()
            empty.update_layout(title="⚠️ No data after filtering")
            return empty, {'height': '480px'}, [], [], [], dash.no_update, _wrapper_style()

        # Clean up empty values
        color_col = color_col if color_col else None
        size_col = size_col if size_col else None
        group_x_col = group_x_col if group_x_col else None
        group_y_col = group_y_col if group_y_col else None

        # Cap color categories to prevent chart overload
        if color_col and color_col in df.columns and df[color_col].nunique() > 50:
            top_cats = df[color_col].value_counts().head(50).index.tolist()
            df.loc[~df[color_col].isin(top_cats), color_col] = 'Other'

        # Convert numeric columns
        for y in y_cols:
            if y in df.columns:
                df[y] = pd.to_numeric(df[y], errors='coerce')
        if size_col and size_col in df.columns:
            df[size_col] = pd.to_numeric(df[size_col], errors='coerce')

        # Extract style config with safe defaults
        _sc = style_config if isinstance(style_config, dict) else {}
        if _sc.get('series_overrides'):
            import logging
            logging.getLogger('dashboard').info(f"[GB] Per-series overrides active: {_sc['series_overrides'][:len(y_cols)]}")
        _marker_size = _sc.get('marker_size', 6)
        _marker_opacity = _sc.get('marker_opacity', 0.7)
        _marker_symbol = _sc.get('marker_symbol', 'auto')
        _line_width = _sc.get('line_width', 1.5)
        _line_dash = _sc.get('line_dash', 'solid')
        _legend_pos = leg_pos or 'bottom'
        _legend_size = leg_size or 11
        _palette_name = _sc.get('palette', 'Plotly')
        _series_ov = _sc.get('series_overrides', [])

        def _get_series_override(yi):
            """Get per-series style override for Y column index yi."""
            if yi < len(_series_ov):
                ov = _series_ov[yi]
                return ov.get('color', '') or '', ov.get('symbol', 'auto') or 'auto', ov.get('dash', 'auto') or 'auto'
            return '', 'auto', 'auto'

        # Hover Tooltip Info + permission check
        user_perms = perms.get(role, []) if perms and role else []
        # Enforce chart type permission server-side (JS buttons can bypass dropdown filtering)
        CHART_PERM_MAP = {
            'scatter': 'gb_chart_scatter', 'line': 'gb_chart_line', 'bar': 'gb_chart_bar',
            'box': 'gb_chart_box', 'histogram': 'gb_chart_histogram', 'violin': 'gb_chart_violin',
            'bubble': 'gb_chart_bubble', 'heatmap': 'gb_chart_heatmap',
            'pareto': 'gb_chart_pareto', 'correlation': 'gb_chart_heatmap',
        }
        req_perm = CHART_PERM_MAP.get(chart_type)
        if req_perm and req_perm not in user_perms:
            chart_type = 'scatter'  # fallback to default
        # Enforce dual-Y permission server-side
        if 'gb_dual_y' not in user_perms:
            y2_cols = []
        vi_items = df_variable_info['VariableItem'].tolist() if not df_variable_info.empty and 'VariableItem' in df_variable_info.columns else []
        if 'show_variable_info' in user_perms:
            # GB chart hover = tooltip extras → governed by vih:<group>:<item>. Strict opt-in.
            _vih_prefix = f'vih:{group}:'
            _selected_vih = {p[len(_vih_prefix):] for p in user_perms if isinstance(p, str) and p.startswith(_vih_prefix)}
            custom_cols = [v for v in vi_items if v in _selected_vih and v in df.columns]
        else:
            custom_cols = []
        
        # Gate by the current '👁 View Action Log' perm. 'show_action_comment' is its legacy
        # pre-rename token — no UI offers it any more, but roles saved before the rename may
        # still carry it, so it keeps working (this line was the only remaining checker; with
        # only the legacy token the feature had become un-grantable for new roles).
        if (('view_action_log' in user_perms or 'show_action_comment' in user_perms)
                and not df_action.empty and 'LotNo' in df.columns):
            for y in y_cols:
                y_acts = df_action[df_action['CoAItem'] == y][['LotNo', 'Action_Comment']].rename(columns={'Action_Comment': f'Action_{y}'})
                y_acts['LotNo'] = y_acts['LotNo'].astype(str)
                df['LotNo'] = df['LotNo'].astype(str)
                df = df.merge(y_acts, on='LotNo', how='left')

        def get_hover_data(target_df, y):
            c_cols = custom_cols.copy()
            if f'Action_{y}' in target_df.columns:
                c_cols.append(f'Action_{y}')
            # JMP-style tooltip: row number, category, axis values, custom data
            extra_cols = []
            if 'LotNo' in target_df.columns and 'LotNo' not in c_cols and x_col != 'LotNo':
                extra_cols.append('LotNo')
            if color_col and color_col in target_df.columns and color_col not in c_cols:
                extra_cols.append(color_col)
            all_extra = extra_cols + c_cols
            c_data = target_df[all_extra].values if all_extra else np.empty((len(target_df), 0))
            # Build JMP-style hover template
            tpl = '<b style="font-size:13px">%{data.name}</b><br>'
            tpl += '<span style="color:#888">\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500</span><br>'
            tpl += f'<b>{x_col}</b>: %{{x}}<br>'
            tpl += f'<b>{y}</b>: %{{y:.4g}}<br>'
            for i, col in enumerate(all_extra):
                lbl = col.replace(f"Action_{y}", "\U0001f4dd Action")
                tpl += f'{lbl}: %{{customdata[{i}]}}<br>'
            tpl += '<extra></extra>'
            return c_data, tpl

        # ──  LTTB downsample for big-data scatter/line charts ──
        # Keep df_full for stats/export; df trimmed for visual rendering.
        try:
            from app.models.anomaly_scores import lttb_downsample
        except ImportError:
            lttb_downsample = None
        df_full = df  # alias retained in case downstream code wants the full set
        _lttb_threshold = 0
        for _p in user_perms:
            if isinstance(_p, str) and _p.startswith('def_gb_lttb_'):
                try: _lttb_threshold = int(_p.replace('def_gb_lttb_', ''))
                except (ValueError, TypeError): _lttb_threshold = 0
                break
        if lttb_downsample and _lttb_threshold > 0 and chart_type in ('scatter', 'line') and len(df) > _lttb_threshold:
            # Downsample using the first Y column as the magnitude reference; keeps row alignment via LTTB indices.
            _ref_y = pd.to_numeric(df[y_cols[0]], errors='coerce').values if y_cols and y_cols[0] in df.columns else None
            if _ref_y is not None and not np.all(np.isnan(_ref_y)):
                _x_idx = np.arange(len(df))
                _x_pick, _ = lttb_downsample(_x_idx, _ref_y, _lttb_threshold)
                df = df.iloc[_x_pick.astype(int)].reset_index(drop=True)

        # ── Subplot variable defaults ──
        gy_vals, gx_vals, gy_col, gx_col = ['(all)'], ['(all)'], None, None

        # ── Shared-X Parallel-Y (Stack Y) mode ──
        _stack_y_requested = (y_display_mode == 'stack_y' and len(y_cols) > 1)
        _stack_y = (
            _stack_y_requested
            and chart_type in ('scatter', 'line', 'bar')
            and not group_x_col and not group_y_col
        )
        _use_subplots = False
        _subplot_height = 480
        _subplot_width = None  # None = use container width (auto)
        if _stack_y:
            from plotly.subplots import make_subplots as _make_subplots
            import plotly.colors as _pcolors
            _cat_colors = getattr(_pcolors.qualitative, _palette_name, _pcolors.qualitative.Plotly) * 10
            _sym_styles = [_marker_symbol] * 60 if _marker_symbol != 'auto' else ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up'] * 10
            n_y_rows = len(y_cols)
            y2_cols = []  # mutually exclusive with dual-Y
            # Store for trendline subplot iteration
            gy_vals = list(range(n_y_rows))
            gx_vals = ['(all)']
            gy_col = None
            gx_col = None

            fig = _make_subplots(
                rows=n_y_rows, cols=1, shared_xaxes=True,
                vertical_spacing=min(0.05, 0.95 / max(n_y_rows - 1, 1)) if n_y_rows > 1 else 0.05
            )
            srt = df.sort_values(x_col) if x_col != 'LotNo' else df
            for yi, y in enumerate(y_cols):
                if y not in srt.columns: continue
                _ov_color, _ov_symbol, _ov_dash = _get_series_override(yi)
                _yi_color = _ov_color or _cat_colors[yi % len(_cat_colors)]
                _yi_symbol = _ov_symbol if _ov_symbol != 'auto' else _sym_styles[yi % len(_sym_styles)]
                if color_col and color_col in srt.columns:
                    unique_cats = sorted(srt[color_col].dropna().unique())
                    for j, cat in enumerate(unique_cats):
                        sub = srt[srt[color_col] == cat]
                        sub_y = pd.to_numeric(sub[y], errors='coerce')
                        legend_name = str(cat)
                        show_leg = (yi == 0)
                        c_data, tpl = get_hover_data(sub, y)
                        _j_color = _ov_color or _cat_colors[j % len(_cat_colors)]
                        if chart_type == 'scatter':
                            fig.add_trace(go.Scatter(
                                x=sub[x_col], y=sub_y, mode='markers', name=legend_name,
                                showlegend=show_leg, legendgroup=legend_name, meta=y,
                                marker=dict(color=_j_color, symbol=_yi_symbol, size=_marker_size, opacity=_marker_opacity),
                                customdata=c_data, hovertemplate=tpl
                            ), row=yi + 1, col=1)
                        elif chart_type == 'line':
                            fig.add_trace(go.Scatter(
                                x=sub[x_col], y=sub_y, mode='lines+markers', name=legend_name,
                                showlegend=show_leg, legendgroup=legend_name, meta=y,
                                marker=dict(color=_j_color, size=max(2, _marker_size - 2)),
                                line=dict(color=_j_color, width=_line_width, dash=_ov_dash if _ov_dash != 'auto' else None),
                                customdata=c_data, hovertemplate=tpl
                            ), row=yi + 1, col=1)
                        elif chart_type == 'bar':
                            fig.add_trace(go.Bar(
                                x=sub[x_col], y=sub_y, name=legend_name,
                                showlegend=show_leg, legendgroup=legend_name, meta=y,
                                marker_color=_j_color, customdata=c_data, hovertemplate=tpl
                            ), row=yi + 1, col=1)
                else:
                    y_num = pd.to_numeric(srt[y], errors='coerce')
                    c_data, tpl = get_hover_data(srt, y)
                    if chart_type == 'scatter':
                        fig.add_trace(go.Scatter(
                            x=srt[x_col], y=y_num, mode='markers', name=sym_map.get(y, y), meta=y,
                            marker=dict(color=_yi_color, symbol=_yi_symbol, size=_marker_size, opacity=_marker_opacity),
                            customdata=c_data, hovertemplate=tpl
                        ), row=yi + 1, col=1)
                    elif chart_type == 'line':
                        fig.add_trace(go.Scatter(
                            x=srt[x_col], y=y_num, mode='lines+markers', name=sym_map.get(y, y), meta=y,
                            marker=dict(color=_yi_color, size=max(2, _marker_size - 2)),
                            line=dict(color=_yi_color, width=_line_width, dash=_ov_dash if _ov_dash != 'auto' else None),
                            customdata=c_data, hovertemplate=tpl
                        ), row=yi + 1, col=1)
                    elif chart_type == 'bar':
                        fig.add_trace(go.Bar(
                            x=srt[x_col], y=y_num, name=sym_map.get(y, y), meta=y,
                            marker_color=_yi_color, customdata=c_data, hovertemplate=tpl
                        ), row=yi + 1, col=1)
                # Set Y-axis label per subplot
                fig.update_yaxes(title_text=sym_map.get(y, y), row=yi + 1, col=1)

            # X-axis title/ticks only on bottom subplot
            _sx_title = (axis_config or {}).get('x', {}).get('title', '') or x_col
            for yi in range(n_y_rows):
                is_bottom = yi == n_y_rows - 1
                fig.update_xaxes(
                    title_text=_sx_title if is_bottom else None,
                    showticklabels=is_bottom,
                    row=yi + 1, col=1
                )



            fig.update_layout(
                height=max(400, n_y_rows * 280),
                template='plotly_white', hovermode='closest',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Inter, Arial, sans-serif'),
            )
            fig.update_xaxes(showgrid=False, showline=False)
            fig.update_yaxes(showgrid=False, showline=False)
            if x_col == 'LotNo':
                fig.update_xaxes(type='category', tickangle=-90)
            _use_subplots = True

        # ── Group X / Group Y: JMP-style Panel Subplots ──
        if not _use_subplots:
            _use_subplots = (
                chart_type in ('scatter', 'line', 'bar') and
                ((group_x_col and group_x_col in df.columns) or (group_y_col and group_y_col in df.columns))
            )
        if _use_subplots and not _stack_y:
            from plotly.subplots import make_subplots as _make_subplots

            def _compute_groups(col):
                """Return list of group labels; bin numeric cols into configurable ranges."""
                max_lvl = group_levels if group_levels else 10
                if pd.api.types.is_numeric_dtype(df[col]):
                    n_bins = min(max_lvl, df[col].nunique())
                    df[f'__G_{col}__'] = pd.cut(df[col], bins=max(1, n_bins)).astype(str)
                else:
                    top_n = df[col].value_counts().head(max_lvl).index
                    df[f'__G_{col}__'] = df[col].astype(str).where(df[col].isin(top_n), 'Other')
                return sorted(df[f'__G_{col}__'].dropna().unique()), f'__G_{col}__'

            if group_x_col and group_x_col in df.columns:
                gx_vals, gx_col = _compute_groups(group_x_col)
            else:
                gx_vals, gx_col = ['(all)'], None
            if group_y_col and group_y_col in df.columns:
                gy_vals, gy_col = _compute_groups(group_y_col)
            else:
                gy_vals, gy_col = ['(all)'], None

            # Cap panel counts to prevent overflow
            MAX_COLS, MAX_ROWS = 8, 8
            if len(gx_vals) > MAX_COLS: gx_vals = gx_vals[:MAX_COLS]
            if len(gy_vals) > MAX_ROWS: gy_vals = gy_vals[:MAX_ROWS]
            n_cols_sp, n_rows_sp = len(gx_vals), len(gy_vals)
            sp_titles = []
            for ry in gy_vals:
                for cx in gx_vals:
                    parts = []
                    if gx_col: parts.append(f"{group_x_col}={cx}")
                    if gy_col: parts.append(f"{group_y_col}={ry}")
                    sp_titles.append(" | ".join(parts) or "All")

            import plotly.colors as _pcolors
            _cat_colors = getattr(_pcolors.qualitative, _palette_name, _pcolors.qualitative.Plotly) * 10
            _sym_styles = [_marker_symbol] * 60 if _marker_symbol != 'auto' else ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up'] * 10

            fig = _make_subplots(
                rows=n_rows_sp, cols=n_cols_sp,
                shared_xaxes=True, shared_yaxes=True,
                subplot_titles=sp_titles,
                horizontal_spacing=min(0.05, 0.95 / max(n_cols_sp - 1, 1)) if n_cols_sp > 1 else 0.05,
                vertical_spacing=min(0.05, 0.95 / max(n_rows_sp - 1, 1)) if n_rows_sp > 1 else 0.05
            )
            for ri, ry_val in enumerate(gy_vals):
                for ci, cx_val in enumerate(gx_vals):
                    p_df = df.copy()
                    if gy_col: p_df = p_df[p_df[gy_col] == ry_val]
                    if gx_col: p_df = p_df[p_df[gx_col] == cx_val]
                    if p_df.empty: continue
                    p_df = p_df.sort_values(x_col) if x_col != 'LotNo' else p_df
                    for yi, y in enumerate(y_cols):
                        if y not in p_df.columns: continue
                        show_leg_first = (ri == 0 and ci == 0)

                        # ── Color grouping within subplot cells ──
                        if color_col and color_col in p_df.columns:
                            unique_cats = sorted(p_df[color_col].dropna().unique())
                            for j, cat in enumerate(unique_cats):
                                sub = p_df[p_df[color_col] == cat]
                                sub_y = pd.to_numeric(sub[y], errors='coerce')
                                legend_name = str(cat)
                                show_leg = show_leg_first
                                c_data, tpl = get_hover_data(sub, y)
                                if chart_type == 'scatter':
                                    fig.add_trace(go.Scatter(
                                        x=sub[x_col], y=sub_y, mode='markers', name=legend_name,
                                        showlegend=show_leg, legendgroup=legend_name, meta=y,
                                        marker=dict(color=_cat_colors[j % len(_cat_colors)], symbol=_sym_styles[yi % len(_sym_styles)], size=_marker_size, opacity=_marker_opacity),
                                        customdata=c_data, hovertemplate=tpl
                                    ), row=ri + 1, col=ci + 1)
                                elif chart_type == 'line':
                                    fig.add_trace(go.Scatter(
                                        x=sub[x_col], y=sub_y, mode='lines+markers', name=legend_name,
                                        showlegend=show_leg, legendgroup=legend_name, meta=y,
                                        marker=dict(color=_cat_colors[j % len(_cat_colors)], size=max(2, _marker_size - 2)),
                                        line=dict(color=_cat_colors[j % len(_cat_colors)], width=_line_width),
                                        customdata=c_data, hovertemplate=tpl
                                    ), row=ri + 1, col=ci + 1)
                                elif chart_type == 'bar':
                                    fig.add_trace(go.Bar(
                                        x=sub[x_col], y=sub_y, name=legend_name,
                                        showlegend=show_leg, legendgroup=legend_name,
                                        marker_color=_cat_colors[j % len(_cat_colors)]
                                    ), row=ri + 1, col=ci + 1)
                        else:
                            # No color grouping — color by Y variable index
                            y_num = pd.to_numeric(p_df[y], errors='coerce')
                            c_data, tpl = get_hover_data(p_df, y)
                            if chart_type == 'scatter':
                                fig.add_trace(go.Scatter(
                                    x=p_df[x_col], y=y_num, mode='markers', name=y,
                                    showlegend=show_leg_first, legendgroup=y,
                                    marker=dict(color=_cat_colors[yi % len(_cat_colors)], symbol=_sym_styles[yi % len(_sym_styles)], size=_marker_size, opacity=_marker_opacity),
                                    customdata=c_data, hovertemplate=tpl
                                ), row=ri + 1, col=ci + 1)
                            elif chart_type == 'line':
                                fig.add_trace(go.Scatter(
                                    x=p_df[x_col], y=y_num, mode='lines+markers', name=y,
                                    showlegend=show_leg_first, legendgroup=y,
                                    marker=dict(color=_cat_colors[yi % len(_cat_colors)], size=max(2, _marker_size - 2)),
                                    line=dict(color=_cat_colors[yi % len(_cat_colors)], width=_line_width),
                                    customdata=c_data, hovertemplate=tpl
                                ), row=ri + 1, col=ci + 1)
                            elif chart_type == 'bar':
                                fig.add_trace(go.Bar(
                                    x=p_df[x_col], y=y_num, name=y,
                                    showlegend=show_leg_first, legendgroup=y,
                                    marker_color=_cat_colors[yi % len(_cat_colors)]
                                ), row=ri + 1, col=ci + 1)
            _subplot_height = max(400, min(n_rows_sp * 280, 2200))
            _subplot_width = max(350 * n_cols_sp, 600) if n_cols_sp > 1 else None
            _fig_layout = dict(
                height=_subplot_height,
                template='plotly_white', hovermode='closest',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Inter, Arial, sans-serif'),
            )
            if _subplot_width:
                _fig_layout['width'] = _subplot_width
            fig.update_layout(**_fig_layout)
            fig.update_xaxes(showgrid=False, showline=False)
            fig.update_yaxes(showgrid=False, showline=False)
            if x_col == 'LotNo':
                fig.update_xaxes(type='category', tickangle=-90)
            # Suppress per-subplot x-axis titles so 'LotNo' doesn't appear
            # in the middle of faceted panels
            for _ax_key in list(fig.layout.to_plotly_json().keys()):
                if _ax_key.startswith('xaxis'):
                    fig.layout[_ax_key]['title'] = None
        elif not _use_subplots:
            # Build figure (single panel) — skip when _stack_y already created fig
            fig = go.Figure()


        try:
            import plotly.colors as pcolors
            cat_colors = getattr(pcolors.qualitative, _palette_name, pcolors.qualitative.Plotly) * 10
            sym_styles = [_marker_symbol] * 90 if _marker_symbol != 'auto' else ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'star', 'hexagram'] * 10
            _run_single = not _use_subplots  # Skip single-panel chart build if subplots already built

            if _run_single and chart_type == 'scatter':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    _ov_color, _ov_symbol, _ov_dash = _get_series_override(i)
                    _i_symbol = _ov_symbol if _ov_symbol != 'auto' else sym_styles[i % len(sym_styles)]
                    if unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            c_data, tpl = get_hover_data(sub, y)
                            legend_name = str(cat)
                            _j_color = _ov_color or cat_colors[j % len(cat_colors)]
                            fig.add_trace(go.Scatter(
                                x=sub[x_col], y=sub[y], mode='markers', name=legend_name, meta=y,
                                legendgroup=legend_name, showlegend=(i==0),
                                marker=dict(color=_j_color, symbol=_i_symbol, size=sub[size_col].fillna(_marker_size) if size_col and size_col in sub.columns else _marker_size, opacity=_marker_opacity),
                                customdata=c_data, hovertemplate=tpl
                            ))
                    else:
                        c_data, tpl = get_hover_data(df, y)
                        _i_color = _ov_color or cat_colors[i % len(cat_colors)]
                        fig.add_trace(go.Scatter(
                            x=df[x_col], y=df[y], mode='markers',
                            name=y, marker=dict(color=_i_color, symbol=_i_symbol, size=df[size_col].fillna(_marker_size) if size_col and size_col in df.columns else _marker_size, opacity=_marker_opacity),
                            customdata=c_data, hovertemplate=tpl
                        ))
                if len(y_cols) > 1 and unique_cats:
                    for i, y in enumerate(y_cols):
                        _ov_color_i, _ov_sym_i, _ = _get_series_override(i)
                        _i_sym = _ov_sym_i if _ov_sym_i != 'auto' else sym_styles[i % len(sym_styles)]
                        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name=f"Shape: {y}", marker=dict(color='gray', symbol=_i_sym, size=10), showlegend=True))

            elif _run_single and chart_type == 'line':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    _ov_color, _ov_symbol, _ov_dash = _get_series_override(i)
                    _i_symbol = _ov_symbol if _ov_symbol != 'auto' else sym_styles[i % len(sym_styles)]
                    _i_dash = _ov_dash if _ov_dash != 'auto' else ['solid', 'dash', 'dot', 'dashdot'][i % 4]
                    if unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat].sort_values(x_col)
                            c_data, tpl = get_hover_data(sub, y)
                            legend_name = str(cat)
                            _j_color = _ov_color or cat_colors[j % len(cat_colors)]
                            fig.add_trace(go.Scatter(
                                x=sub[x_col], y=sub[y], mode='lines+markers', name=legend_name, meta=y,
                                legendgroup=legend_name, showlegend=(i==0),
                                marker=dict(color=_j_color, symbol=_i_symbol, size=max(2, _marker_size - 2)), line=dict(color=_j_color, width=_line_width, dash=_i_dash),
                                customdata=c_data, hovertemplate=tpl
                            ))
                    else:
                        srt = df.sort_values(x_col) if x_col != 'LotNo' else df
                        c_data, tpl = get_hover_data(srt, y)
                        _i_color = _ov_color or cat_colors[i % len(cat_colors)]
                        fig.add_trace(go.Scatter(
                            x=srt[x_col], y=srt[y], mode='lines+markers',
                            name=y, marker=dict(color=_i_color, symbol=_i_symbol, size=max(2, _marker_size - 2)), line=dict(color=_i_color, width=_line_width, dash=_i_dash),
                            customdata=c_data, hovertemplate=tpl
                        ))
                if len(y_cols) > 1 and unique_cats:
                    for i, y in enumerate(y_cols):
                        _ov_color_i, _ov_sym_i, _ov_dash_i = _get_series_override(i)
                        _i_sym = _ov_sym_i if _ov_sym_i != 'auto' else sym_styles[i % len(sym_styles)]
                        _i_dsh = _ov_dash_i if _ov_dash_i != 'auto' else ['solid', 'dash', 'dot', 'dashdot'][i % 4]
                        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines+markers', name=f"Line: {y}", marker=dict(color='gray', symbol=_i_sym, size=8), line=dict(color='gray', dash=_i_dsh), showlegend=True))

            elif _run_single and chart_type == 'bar':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    _ov_color, _ov_symbol, _ov_dash = _get_series_override(i)
                    if unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            legend_name = str(cat)
                            _j_color = _ov_color or cat_colors[j % len(cat_colors)]
                            fig.add_trace(go.Bar(x=sub[x_col], y=sub[y], name=legend_name, legendgroup=legend_name, showlegend=(i==0), marker_color=_j_color, meta=y))
                    else:
                        _i_color = _ov_color or cat_colors[i % len(cat_colors)]
                        fig.add_trace(go.Bar(x=df[x_col], y=df[y], name=y, meta=y, marker_color=_i_color))

            elif _run_single and chart_type == 'box':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    if group_x_col and group_x_col in df.columns:
                        fig.add_trace(go.Box(x=df[group_x_col], y=df[y], name=y, boxmean='sd', meta=y))
                    elif unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            legend_name = str(cat)
                            fig.add_trace(go.Box(y=sub[y], name=legend_name, legendgroup=legend_name, showlegend=(i==0), marker_color=cat_colors[j % len(cat_colors)], boxmean='sd', meta=y))
                    else:
                        fig.add_trace(go.Box(y=df[y], name=y, boxmean='sd', meta=y))

            elif _run_single and chart_type == 'histogram':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    if unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            legend_name = str(cat)
                            fig.add_trace(go.Histogram(x=sub[y], name=legend_name, legendgroup=legend_name, showlegend=(i==0), marker_color=cat_colors[j % len(cat_colors)], opacity=0.7, meta=y))
                    else:
                        fig.add_trace(go.Histogram(x=df[y], name=y, opacity=0.7, meta=y))
                fig.update_layout(barmode='overlay')

                # Histogram overlays (toggleable):
                # Normal Curve + Cpk stats → enabled by Fit=OLS
                # USL/LSL vertical lines   → enabled by Spec SL checkbox
                fig.update_layout(yaxis_title='Count')
                if not unique_cats and len(y_cols) == 1:
                    _y0 = y_cols[0]
                    _yv = f64_series(df[_y0]).dropna()
                    _usl_col, _lsl_col = f'{_y0}_USL', f'{_y0}_LSL'
                    _usl_v = pd.to_numeric(df[_usl_col], errors='coerce').dropna().iloc[0] if _usl_col in df.columns and not df[_usl_col].dropna().empty else None
                    _lsl_v = pd.to_numeric(df[_lsl_col], errors='coerce').dropna().iloc[0] if _lsl_col in df.columns and not df[_lsl_col].dropna().empty else None

                    # Normal Curve + Cpk (Fit → OLS)
                    if trendline == 'ols' and len(_yv) > 5:
                        _mu = _yv.mean()
                        _sig = sanitize_sigma(_yv.std(ddof=1), _mu)
                        if _sig > 0:
                            _x_range = np.linspace(_mu - 4 * _sig, _mu + 4 * _sig, 200)
                            _pdf = (1 / (_sig * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((_x_range - _mu) / _sig) ** 2)
                            _nbins = min(50, max(10, int(np.sqrt(len(_yv)))))
                            _bw = (_yv.max() - _yv.min()) / _nbins if _yv.max() != _yv.min() else 1
                            _pdf_scaled = _pdf * len(_yv) * _bw
                            fig.add_trace(go.Scatter(x=_x_range, y=_pdf_scaled, mode='lines',
                                name='Normal Curve', line=dict(color='#FF6600', width=2.5),
                                hoverinfo='skip'))
                            # Cpk stats annotation
                            _cpk_parts = []
                            if _usl_v is not None: _cpk_parts.append((_usl_v - _mu) / (3 * _sig))
                            if _lsl_v is not None: _cpk_parts.append((_mu - _lsl_v) / (3 * _sig))
                            _cpk = min(_cpk_parts) if _cpk_parts else None
                            _cp = (_usl_v - _lsl_v) / (6 * _sig) if _usl_v is not None and _lsl_v is not None else None
                            _ann = [f"N={len(_yv)}  Mean={_mu:.4g}  Std={_sig:.4g}"]
                            if _cp is not None: _ann.append(f"Cp={_cp:.3f}")
                            if _cpk is not None: _ann.append(f"Cpk={_cpk:.3f}")
                            fig.add_annotation(text='<br>'.join(_ann), xref='paper', yref='paper',
                                x=0.98, y=0.98, showarrow=False, font=dict(size=11, color='#333'),
                                bgcolor='rgba(255,255,255,0.85)', bordercolor='#ccc', borderwidth=1,
                                borderpad=6, align='right', xanchor='right', yanchor='top')

                    # Spec vertical lines on histogram (controlled by Spec checkboxes)
                    if spec_toggles:
                        if 'sl' in spec_toggles:
                            if _usl_v is not None:
                                fig.add_vline(x=_usl_v, line_dash='dash', line_color='red', line_width=2,
                                    annotation_text='USL', annotation_position='top right')
                            if _lsl_v is not None:
                                fig.add_vline(x=_lsl_v, line_dash='dash', line_color='red', line_width=2,
                                    annotation_text='LSL', annotation_position='top left')
                        if 'mean' in spec_toggles and len(_yv) > 0:
                            fig.add_vline(x=_yv.mean(), line_dash='solid', line_color='#616161', line_width=1.5,
                                annotation_text='CL', annotation_position='top')
                        if 'cl' in spec_toggles:
                            _ucl_col, _lcl_col = f'{_y0}_UCL', f'{_y0}_LCL'
                            _ucl_v = pd.to_numeric(df[_ucl_col], errors='coerce').dropna().iloc[0] if _ucl_col in df.columns and not df[_ucl_col].dropna().empty else None
                            _lcl_v = pd.to_numeric(df[_lcl_col], errors='coerce').dropna().iloc[0] if _lcl_col in df.columns and not df[_lcl_col].dropna().empty else None
                            if _ucl_v is not None:
                                fig.add_vline(x=_ucl_v, line_dash='dot', line_color='#e53935', line_width=1.5,
                                    annotation_text='UCL', annotation_position='top right')
                            if _lcl_v is not None:
                                fig.add_vline(x=_lcl_v, line_dash='dot', line_color='#e53935', line_width=1.5,
                                    annotation_text='LCL', annotation_position='top left')
                        if '3s1y' in spec_toggles and len(_yv) > 5:
                            _mu_h = _yv.mean() if trendline != 'ols' else _mu
                            _sig_h = sanitize_sigma(_yv.std(ddof=1), _mu_h) if trendline != 'ols' else _sig
                            fig.add_vline(x=_mu_h + 3 * _sig_h, line_dash='dashdot', line_color='#ff9800', line_width=1.5,
                                annotation_text='+3σ(1Y)', annotation_position='top right')
                            fig.add_vline(x=_mu_h - 3 * _sig_h, line_dash='dashdot', line_color='#ff9800', line_width=1.5,
                                annotation_text='-3σ(1Y)', annotation_position='top left')
                        if '3s2y' in spec_toggles and len(_yv) > 5:
                            _mu_h = _yv.mean() if trendline != 'ols' else _mu
                            _sig_h = sanitize_sigma(_yv.std(ddof=1), _mu_h) if trendline != 'ols' else _sig
                            fig.add_vline(x=_mu_h + 3 * _sig_h, line_dash='dashdot', line_color='#009688', line_width=1.5,
                                annotation_text='+3σ(2Y)', annotation_position='top right')
                            fig.add_vline(x=_mu_h - 3 * _sig_h, line_dash='dashdot', line_color='#009688', line_width=1.5,
                                annotation_text='-3σ(2Y)', annotation_position='top left')
                        if '6s1y' in spec_toggles and len(_yv) > 5:
                            _mu_h = _yv.mean() if trendline != 'ols' else _mu
                            _sig_h = sanitize_sigma(_yv.std(ddof=1), _mu_h) if trendline != 'ols' else _sig
                            fig.add_vline(x=_mu_h + 6 * _sig_h, line_dash='longdash', line_color='#6A1B9A', line_width=1.5,
                                annotation_text='+6σ(1Y)', annotation_position='top right')
                            fig.add_vline(x=_mu_h - 6 * _sig_h, line_dash='longdash', line_color='#6A1B9A', line_width=1.5,
                                annotation_text='-6σ(1Y)', annotation_position='top left')
                        if '6s2y' in spec_toggles and len(_yv) > 5:
                            _mu_h = _yv.mean() if trendline != 'ols' else _mu
                            _sig_h = sanitize_sigma(_yv.std(ddof=1), _mu_h) if trendline != 'ols' else _sig
                            fig.add_vline(x=_mu_h + 6 * _sig_h, line_dash='longdashdot', line_color='#37474F', line_width=1.5,
                                annotation_text='+6σ(2Y)', annotation_position='top right')
                            fig.add_vline(x=_mu_h - 6 * _sig_h, line_dash='longdashdot', line_color='#37474F', line_width=1.5,
                                annotation_text='-6σ(2Y)', annotation_position='top left')

            elif _run_single and chart_type == 'violin':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    if group_x_col and group_x_col in df.columns:
                        for gval in sorted(df[group_x_col].dropna().unique()):
                            sub = df[df[group_x_col] == gval]
                            fig.add_trace(go.Violin(y=sub[y], name=f"{y} [{gval}]", box_visible=True, meanline_visible=True, meta=y))
                    elif unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            legend_name = str(cat)
                            fig.add_trace(go.Violin(y=sub[y], name=legend_name, legendgroup=legend_name, showlegend=(i==0), line_color=cat_colors[j % len(cat_colors)], box_visible=True, meanline_visible=True, meta=y))
                    else:
                        fig.add_trace(go.Violin(y=df[y], name=y, box_visible=True, meanline_visible=True, meta=y))

            elif _run_single and chart_type == 'bubble':
                unique_cats = sorted(df[color_col].dropna().unique()) if color_col and color_col in df.columns else []
                for i, y in enumerate(y_cols):
                    if y not in df.columns: continue
                    has_size = size_col and size_col in df.columns
                    sz_series = df[size_col].fillna(6) if has_size else pd.Series([10]*len(df), index=df.index)
                    sz_max = max(pd.to_numeric(sz_series, errors='coerce').max(), 1)
                    sref = 2. * sz_max / (40. ** 2)
                    if unique_cats:
                        for j, cat in enumerate(unique_cats):
                            sub = df[df[color_col] == cat]
                            sub_sz = sub[size_col].fillna(6) if has_size else 10
                            c_data, tpl = get_hover_data(sub, y)
                            legend_name = str(cat)
                            fig.add_trace(go.Scatter(
                                x=sub[x_col], y=sub[y], mode='markers',
                                name=legend_name, legendgroup=legend_name, showlegend=(i==0),
                                marker=dict(color=cat_colors[j % len(cat_colors)], symbol=sym_styles[i % len(sym_styles)], size=sub_sz, sizemode='area', sizeref=sref, opacity=0.6),
                                customdata=c_data, hovertemplate=tpl
                            ))
                    else:
                        c_data, tpl = get_hover_data(df, y)
                        fig.add_trace(go.Scatter(
                            x=df[x_col], y=df[y], mode='markers', name=y, meta=y,
                            marker=dict(symbol=sym_styles[i % len(sym_styles)], size=sz_series, sizemode='area', sizeref=sref, opacity=0.6),
                            customdata=c_data, hovertemplate=tpl
                        ))

            elif _run_single and chart_type == 'heatmap':
                if len(y_cols) > 1:
                    # Multi-Y heatmap: X=LotNo, Y=CoAItem, Color=normalized value
                    _hm_data = []
                    _hm_y_labels = []
                    for y in y_cols:
                        if y not in df.columns: continue
                        vals = f64_series(df[y])
                        # Z-score normalize per CoAItem for comparable color scale
                        _m = vals.mean()
                        _s = sanitize_sigma(vals.std(ddof=1), _m)
                        _hm_data.append(((vals - _m) / _s if _s > 0 else vals * 0).values)
                        _hm_y_labels.append(sym_map.get(y, y))
                    if _hm_data:
                        fig.add_trace(go.Heatmap(
                            z=_hm_data, x=[str(v) for v in df[x_col]],
                            y=_hm_y_labels, colorscale='RdBu_r', zmid=0,
                            hoverongaps=False, colorbar_title='Z-Score'
                        ))
                        fig.update_layout(yaxis=dict(dtick=1))
                else:
                    y = y_cols[0] if y_cols else None
                    if y and y in df.columns:
                        pivot = df.pivot_table(index=y, columns=x_col, aggfunc='size', fill_value=0)
                        if color_col and color_col in df.columns:
                            pivot = df.pivot_table(index=color_col, columns=x_col, values=y, aggfunc='mean', fill_value=0)
                        fig.add_trace(go.Heatmap(
                            z=pivot.values, x=[str(c) for c in pivot.columns], y=[str(r) for r in pivot.index],
                            colorscale='Viridis', hoverongaps=False
                        ))

            elif _run_single and chart_type == 'correlation':
                # Correlation Matrix: requires 2+ Y columns
                _corr_cols = [y for y in y_cols if y in df.columns]
                if len(_corr_cols) >= 2:
                    _corr_df = df[_corr_cols].apply(pd.to_numeric, errors='coerce')
                    _corr_mat = _corr_df.corr()
                    _labels = [sym_map.get(c, c) for c in _corr_mat.columns]
                    # Annotate R values on the heatmap
                    _annot_text = [[f"{v:.3f}" for v in row] for row in _corr_mat.values]
                    fig.add_trace(go.Heatmap(
                        z=_corr_mat.values, x=_labels, y=_labels,
                        colorscale='RdBu_r', zmid=0, zmin=-1, zmax=1,
                        text=_annot_text, texttemplate='%{text}', textfont=dict(size=12),
                        hoverongaps=False, colorbar_title='R'
                    ))
                    fig.update_layout(yaxis=dict(dtick=1, autorange='reversed'),
                                      xaxis=dict(dtick=1))

            elif _run_single and chart_type == 'pareto':
                # Pareto: X categorical, Y numeric. Aggregate by X (sum), sort desc,
                # add cumulative percentage line on Y2, plus 80% reference line.
                _y = y_cols[0] if y_cols else None
                if _y and _y in df.columns and x_col in df.columns:
                    _agg = pd.to_numeric(df[_y], errors='coerce').groupby(df[x_col]).sum().sort_values(ascending=False)
                    _agg = _agg.dropna()
                    if not _agg.empty:
                        _total = _agg.sum() or 1.0
                        _cum_pct = (_agg.cumsum() / _total * 100).clip(upper=100)
                        _x_str = [str(v) for v in _agg.index]
                        fig.add_trace(go.Bar(x=_x_str, y=_agg.values, name=sym_map.get(_y, _y),
                                             marker_color='#4C9ED9'))
                        fig.add_trace(go.Scatter(x=_x_str, y=_cum_pct.values, name='Cumulative %',
                                                 mode='lines+markers', yaxis='y2',
                                                 line=dict(color='#FF6F00', width=2),
                                                 marker=dict(size=6, color='#FF6F00')))
                        fig.add_shape(type='line', x0=-0.5, x1=len(_x_str) - 0.5,
                                      y0=80, y1=80, yref='y2', xref='x',
                                      line=dict(color='#888', dash='dash', width=1))
                        fig.add_annotation(x=len(_x_str) - 1, y=80, yref='y2',
                                           text='80%', showarrow=False, font=dict(color='#888'),
                                           xanchor='right', yanchor='bottom')
                        fig.update_layout(
                            yaxis=dict(title=sym_map.get(_y, _y)),
                            yaxis2=dict(title='Cumulative %', overlaying='y', side='right',
                                        range=[0, 105], showgrid=False),
                        )

            # ⭕ Outlier auto-highlight: ring points with |z-score| > 3 per Y series.
            # Uses df_full (pre-LTTB) so outliers aren't lost in downsampling.
            if (_run_single and 'gb_outlier_highlight' in user_perms
                    and chart_type in ('scatter', 'line', 'bar') and x_col in df_full.columns):
                for y in y_cols:
                    if y not in df_full.columns:
                        continue
                    s = f64_series(df_full[y])
                    if s.dropna().empty:
                        continue
                    sd = sanitize_sigma(s.std(ddof=1), s.mean())
                    if pd.isna(sd) or sd <= 0:
                        continue
                    z = (s - s.mean()) / sd
                    mask = z.abs() > 3
                    if mask.any():
                        fig.add_trace(go.Scatter(
                            x=df_full.loc[mask, x_col], y=s.loc[mask],
                            mode='markers', name=f'⭕ Outlier [{sym_map.get(y, y)}]',
                            marker=dict(color='rgba(0,0,0,0)', size=14,
                                        line=dict(color='#D50000', width=2.5)),
                            hovertemplate=f'<b>{sym_map.get(y, y)}</b>: %{{y}}<br>%{{x}}<extra></extra>'
                        ))

            # Trendlines (rolling / OLS / LOWESS) — single-panel
            if _run_single and chart_type in ('scatter', 'line'):
                if trendline == 'rolling':
                    _render_rolling_trendline(fig, df, x_col, y_cols, sym_map, ma_window)
                elif trendline == 'lowess':
                    _render_lowess_trendline(fig, df, x_col, y_cols, sym_map)
                # OLS / forecast handled in their own blocks below for annotation/perm specifics.

            # Trendlines for subplot mode (rolling / LOWESS only — OLS has per-panel annotation logic below)
            if _use_subplots and chart_type in ('scatter', 'line') and trendline in ('rolling', 'lowess'):
                if _stack_y:
                    for yi, y in enumerate(y_cols):
                        _panel_df = df  # stack-Y uses full df, one Y per subplot row
                        if trendline == 'rolling':
                            _render_rolling_trendline(fig, _panel_df, x_col, [y], sym_map, ma_window, row=yi + 1, col=1)
                        else:
                            _render_lowess_trendline(fig, _panel_df, x_col, [y], sym_map, row=yi + 1, col=1)
                else:
                    for ri, ry_val in enumerate(gy_vals):
                        for ci, cx_val in enumerate(gx_vals):
                            p_df = df.copy()
                            if gy_col: p_df = p_df[p_df[gy_col] == ry_val]
                            if gx_col: p_df = p_df[p_df[gx_col] == cx_val]
                            if p_df.empty:
                                continue
                            if trendline == 'rolling':
                                _render_rolling_trendline(fig, p_df, x_col, y_cols, sym_map, ma_window, row=ri + 1, col=ci + 1)
                            else:
                                _render_lowess_trendline(fig, p_df, x_col, y_cols, sym_map, row=ri + 1, col=ci + 1)

            # OLS trendline — single-panel mode aggregates per-Y annotations into one corner box
            if _run_single and trendline == 'ols' and chart_type in ('scatter', 'line'):
                ols_annotation_lines = _render_ols_trendline(fig, df, x_col, y_cols, mode='single')
                if ols_annotation_lines:
                    fig.add_annotation(
                        text="<br>".join(ols_annotation_lines), align='left',
                        xref='paper', yref='paper', x=0.01, y=0.99,
                        xanchor='left', yanchor='top', showarrow=False,
                        bgcolor='rgba(255,255,255,0.85)', bordercolor='#90CAF9',
                        borderwidth=1, borderpad=6,
                        font=dict(size=11, family='Consolas, monospace', color='#1a1a2e'),
                    )

            # OLS trendline — subplot modes (per-panel annotations handled inside helper)
            if _use_subplots and trendline == 'ols' and chart_type in ('scatter', 'line'):
                if _stack_y:
                    for yi, y in enumerate(y_cols):
                        _render_ols_trendline(fig, df, x_col, [y], row=yi + 1, col=1, mode='stack_y')
                else:
                    for ri, ry_val in enumerate(gy_vals):
                        for ci, cx_val in enumerate(gx_vals):
                            p_df = df.copy()
                            if gy_col: p_df = p_df[p_df[gy_col] == ry_val]
                            if gx_col: p_df = p_df[p_df[gx_col] == cx_val]
                            if p_df.empty:
                                continue
                            _render_ols_trendline(fig, p_df, x_col, y_cols, row=ri + 1, col=ci + 1, mode='group_xy')

            # Forecast trendline (single-panel scatter/line; uses utils.forecast_series).
            # Permission + horizon handled inside helper.
            if _run_single and trendline == 'forecast' and chart_type in ('scatter', 'line'):
                _render_forecast_trendline(fig, df, x_col, y_cols, sym_map, user_perms)

            # Spec lines (UCL/LCL/USL/LSL/Mean/±3σ/±6σ) — all 3 modes share `_render_spec_lines_for_y`.
            # Sigma cache built ONCE per build so the 1Y/2Y baseline slice is reused across panels.
            if spec_toggles and chart_type in ('scatter', 'line'):
                _sigma_cache = _build_sigma_cache(df_stat, y_cols, spec_toggles)
                if _run_single:
                    for y in y_cols:
                        _render_spec_lines_for_y(fig, df, x_col, y, spec_toggles, _sigma_cache)
                elif _stack_y:
                    for yi, y in enumerate(y_cols):
                        _render_spec_lines_for_y(fig, df, x_col, y, spec_toggles, _sigma_cache, row=yi + 1, col=1)
                elif _use_subplots:
                    for ri, ry_val in enumerate(gy_vals):
                        for ci, cx_val in enumerate(gx_vals):
                            p_df = df.copy()
                            if gy_col: p_df = p_df[p_df[gy_col] == ry_val]
                            if gx_col: p_df = p_df[p_df[gx_col] == cx_val]
                            if p_df.empty:
                                continue
                            for y in y_cols:
                                _render_spec_lines_for_y(fig, p_df, x_col, y, spec_toggles, _sigma_cache, row=ri + 1, col=ci + 1)



        except Exception as e:
            import traceback
            traceback.print_exc()
            fig = go.Figure()
            fig.update_layout(title=f"⚠️ Error building graph: {str(e)}")
            error_occurred = True
        else:
            error_occurred = False

        # Custom titles from axis config
        axis_config = axis_config or {}
        custom_chart_title = axis_config.get('chart_title', '') or ''
        custom_x_title = axis_config.get('x', {}).get('title', '') or ''
        custom_y_title = axis_config.get('y', {}).get('title', '') or ''
        show_caption = axis_config.get('show_caption', False)

        # Layout — JMP-style
        y_title_auto = ', '.join([y for y in y_cols]) if len(y_cols) <= 3 else f"{len(y_cols)} variables"
        if chart_type in ('histogram', 'correlation'):
            x_title = custom_x_title if custom_x_title else (', '.join([sym_map.get(y, y) for y in y_cols[:3]]) if y_cols else 'Value')
        else:
            x_title = custom_x_title if custom_x_title else x_col
        y_title = custom_y_title if custom_y_title else y_title_auto
        n_traces = len(fig.data)
        # Smart legend: position from style config, auto-vertical for many traces
        _leg_font_size = _legend_size
        if _legend_pos == 'right' or n_traces > 15:
            legend_cfg = dict(
                orientation='v', yanchor='top', y=1.0, xanchor='left', x=1.1 if y2_cols else 1.02,
                font=dict(size=min(_leg_font_size, 9) if n_traces > 30 else (min(_leg_font_size, 10) if n_traces > 15 else _leg_font_size)),
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#e2e8f0', borderwidth=1,
                tracegroupgap=1 if n_traces > 30 else 2,
                itemclick='toggle', itemdoubleclick='toggleothers',
            )
            margin_r = 280 if n_traces > 30 else (220 if y2_cols else 160)
        elif _legend_pos == 'bottom':
            legend_cfg = dict(
                orientation='h', yanchor='top', y=-0.35, xanchor='center', x=0.5,
                font=dict(size=_leg_font_size),
            )
            margin_r = 60 if y2_cols else 40
        else:  # top
            legend_cfg = dict(
                orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5,
                font=dict(size=_leg_font_size),
            )
            margin_r = 60 if y2_cols else 40
        auto_title = f"<b>{y_title}</b> vs <b>{x_title}</b>  <span style='font-size:12px;color:#888'>(N={len(df)})</span>"
        final_title = f"<b>{custom_chart_title}</b>" if custom_chart_title else auto_title
        if not error_occurred:
            _layout_kw = dict(
                title=dict(text=final_title, font=dict(size=16, color=COLOR_PRIMARY), x=0.5, xanchor='center'),
                hovermode='closest',
            )
            if not _stack_y and not _use_subplots:
                _layout_kw['xaxis_title'] = x_title
                if chart_type == 'histogram':
                    _layout_kw['yaxis_title'] = 'Count'
                elif chart_type == 'correlation':
                    pass  # No axis titles for correlation matrix
                else:
                    _layout_kw['yaxis_title'] = y_title if len(y_cols) == 1 else 'Value'
            # Calculate dynamic height once. For default single-chart mode we let the figure
            # auto-fill the user-resizable wrapper (no explicit height); only stacked-Y / subplots
            # need explicit height because each panel demands vertical space.
            _explicit_height = None
            if _stack_y:
                _explicit_height = max(480, len(y_cols) * 220)
                _margin_b = 60 # Less bottom margin for stacked charts
            elif _use_subplots:
                _explicit_height = _subplot_height
                _margin_b = 80
            else:
                _margin_b = 120 if n_traces <= 15 else 50

            _layout_extra = {} if _explicit_height is None else {'height': _explicit_height}
            fig.update_layout(
                **_layout_kw,
                hoverlabel=dict(bgcolor='#ffffff', bordercolor='#90CAF9', font_size=12, font_color='#333',
                                font_family='Consolas, monospace'),
                template='plotly_white',
                legend=legend_cfg,
                margin=dict(l=50, r=margin_r, t=55, b=_margin_b, autoexpand=True),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Inter, Arial, sans-serif'),
                autosize=True,
                **_layout_extra,
            )
            _x_fontsize = (axis_config or {}).get('x', {}).get('tick_fontsize', 11)
            _y_fontsize = (axis_config or {}).get('y', {}).get('tick_fontsize', 11)
            fig.update_xaxes(showgrid=False, showline=False, tickfont=dict(size=_x_fontsize, color='#333'), tickangle=-45, automargin=True)
            fig.update_yaxes(showgrid=False, showline=False, tickfont=dict(size=_y_fontsize, color='#333'), automargin=True)

        # Y2 Dual Axis: route Y2 traces to secondary axis
        if y2_cols and chart_type in ('scatter', 'line', 'bubble', 'bar'):
            y1_title = ', '.join([y for y in y_cols if y not in y2_cols])
            y2_title = ', '.join(y2_cols)
            fig.update_layout(
                yaxis_title=y1_title or 'Value',
                yaxis2=dict(
                    title=dict(text=y2_title, font=dict(color='#E65100')),
                    overlaying='y', side='right', showgrid=False,
                    tickfont=dict(color='#E65100')
                ),
                margin=dict(r=margin_r)
            )
            for trace in fig.data:
                y2_match = getattr(trace, 'meta', None)
                if not y2_match:
                    tname = getattr(trace, 'name', '') or ''
                    # Match by exact name fallback
                    for y2 in y2_cols:
                        if y2 == tname or tname.startswith(f"{y2} ") or tname.startswith(f"{y2}_") or f'[{y2}]' in tname:
                            y2_match = y2
                            break
                if y2_match in y2_cols:
                    trace.update(yaxis='y2')
            fig.update_yaxes(autorange=True)
        if x_col == 'LotNo' and chart_type not in ('histogram', 'correlation', 'heatmap'):
            n_lots = df['LotNo'].nunique()
            # Show all LotNo labels up to 60; beyond that show every Nth to prevent overlap
            if n_lots <= 60:
                _lot_dtick = 1
            elif n_lots <= 200:
                _lot_dtick = max(1, n_lots // 40)
            else:
                _lot_dtick = max(1, n_lots // 60)
            _x_fs_lot = (axis_config or {}).get('x', {}).get('tick_fontsize', 11)
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=df['LotNo'].tolist(),
                             dtick=_lot_dtick, tickangle=-90, tickfont=dict(size=_x_fs_lot))

        # Apply axis config (JMP-style) from modal settings — config structure: {which, x:{...}, y:{...}}
        axis_config = axis_config or {}
        for which_ax in ('x', 'y', 'y2'):
            ax_conf = axis_config.get(which_ax, {})
            if not ax_conf:
                continue
            ax_update = {}
            if ax_conf.get('dtick'):
                ax_update['dtick'] = ax_conf['dtick']
            if ax_conf.get('nticks'):
                ax_update['nticks'] = ax_conf['nticks']
            if ax_conf.get('format') not in (None, ''):
                ax_update['tickformat'] = ax_conf['format']
            grid_style = ax_conf.get('grid_style', 'solid')
            if grid_style == 'none':
                ax_update['showgrid'] = False
            else:
                ax_update['showgrid'] = True
                ax_update['griddash'] = grid_style
            _title_fs = ax_conf.get('title_fontsize', 14)
            if ax_conf.get('title'):
                ax_update['title'] = {'text': ax_conf['title'], 'font': {'size': _title_fs}}
            elif ax_conf.get('title_fontsize'):
                ax_update['title'] = {'font': {'size': _title_fs}}
            if ax_conf.get('tick_fontsize'):
                ax_update['tickfont'] = dict(size=ax_conf['tick_fontsize'], color='#333')
            if ax_update:
                if which_ax == 'y2':
                    existing_y2 = fig.layout.yaxis2.to_plotly_json() if hasattr(fig.layout, 'yaxis2') and fig.layout.yaxis2 else {}
                    fig.update_layout(yaxis2={**existing_y2, **ax_update})
                elif which_ax == 'y':
                    fig.update_yaxes(**ax_update)
                else:
                    fig.update_xaxes(**ax_update)

        # Apply reference lines from modal
        ref_lines = ref_lines or []
        for ref in ref_lines:
            ref_axis = ref.get('axis', 'y')
            ref_color = ref.get('color', '#e53935')
            ref_style = ref.get('style', 'dash')
            ref_label = ref.get('label', '')
            if ref_axis == 'x':
                fig.add_vline(x=ref['value'], line_dash=ref_style,
                              line_color=ref_color, line_width=2,
                              annotation_text=ref_label, annotation_position='top left',
                              annotation_font_color=ref_color, annotation_font_size=11)
            elif ref_axis == 'y2':
                # Y2 reference line — use shape with yref='y2'
                fig.add_shape(type='line', yref='y2', y0=ref['value'], y1=ref['value'],
                              x0=0, x1=1, xref='paper',
                              line=dict(color=ref_color, dash=ref_style, width=2))
                if ref_label:
                    fig.add_annotation(text=ref_label, yref='y2', y=ref['value'],
                                       x=1.02, xref='paper', showarrow=False,
                                       font=dict(size=11, color=ref_color), xanchor='left')
            else:
                fig.add_hline(y=ref['value'], line_dash=ref_style,
                              line_color=ref_color, line_width=2,
                              annotation_text=ref_label, annotation_position='top left',
                              annotation_font_color=ref_color, annotation_font_size=11)

        # Statistics Caption Box (JMP-style summary annotation)
        if show_caption and chart_type in ('scatter', 'line', 'bar', 'box', 'violin', 'histogram'):
            caption_lines = []
            for y in y_cols[:4]:  # Max 4 series in caption
                y_vals = f64_series(df[y]).dropna()
                if len(y_vals) == 0:
                    continue
                n_val = len(y_vals)
                mean_val = y_vals.mean()
                std_val = y_vals.std(ddof=1)
                min_val = y_vals.min()
                max_val = y_vals.max()
                median_val = y_vals.median()
                caption_lines.append(
                    f"<b>{y}</b>  N={n_val}  Mean={mean_val:.4g}  Std={std_val:.4g}  "
                    f"Min={min_val:.4g}  Median={median_val:.4g}  Max={max_val:.4g}"
                )
            if caption_lines:
                fig.add_annotation(
                    text="<br>".join(caption_lines),
                    align='left', xref='paper', yref='paper',
                    x=0.99, y=0.01, xanchor='right', yanchor='bottom',
                    showarrow=False,
                    bgcolor='rgba(245,247,250,0.92)',
                    bordercolor=COLOR_BORDER, borderwidth=1, borderpad=8,
                    font=dict(size=11, family='Consolas, monospace', color=COLOR_TEXT)
                )

        # Preserve user toggled legend/visibility states from the lightweight store
        # (populated clientside by gb_capture_trace_state on every restyle event).
        # Store schema: {trace_name: {'v': bool visible, 'l': bool showlegend}}
        if trace_state_store and isinstance(trace_state_store, dict):
            for t in fig.data:
                state = trace_state_store.get(t.name)
                if not state:
                    continue
                t.visible = True if state.get('v', True) else 'legendonly'
                t.showlegend = bool(state.get('l', True))

        # Build data preview table
        preview_cols = [x_col] + y_cols
        if color_col and color_col in df.columns: preview_cols.append(color_col)
        if size_col and size_col in df.columns: preview_cols.append(size_col)
        if group_x_col and group_x_col in df.columns and group_x_col not in preview_cols: preview_cols.append(group_x_col)
        if group_y_col and group_y_col in df.columns and group_y_col not in preview_cols: preview_cols.append(group_y_col)
        # VariableInfo items marked `vie:<group>:<item>` (Export axis) — preserve in built_data
        # so the GB Excel export can include them. gb_export_data picks them up via the same prefix.
        _vie_prefix_gb = f'vie:{group}:'
        for _p in user_perms:
            if isinstance(_p, str) and _p.startswith(_vie_prefix_gb):
                _item = _p[len(_vie_prefix_gb):]
                if _item and _item in df.columns and _item not in preview_cols:
                    preview_cols.append(_item)
        
        # Inject spec limits for export parity
        if spec_toggles and chart_type in ('scatter', 'line'):
            for y in y_cols:
                if 'cl' in spec_toggles:
                    if f"{y}_UCL" in df.columns: preview_cols.append(f"{y}_UCL")
                    if f"{y}_LCL" in df.columns: preview_cols.append(f"{y}_LCL")
                if 'sl' in spec_toggles:
                    if f"{y}_USL" in df.columns: preview_cols.append(f"{y}_USL")
                    if f"{y}_LSL" in df.columns: preview_cols.append(f"{y}_LSL")
                if '3s1y' in spec_toggles and '製造日期' in df_stat.columns:
                    max_d = df_stat['製造日期'].max()
                    s_1y = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=365))]
                    m1y, std1y = band_stats(s_1y[y])
                    if pd.notna(m1y) and pd.notna(std1y):
                        df[f"{y}_3s1y_UP"] = m1y+3*std1y
                        df[f"{y}_3s1y_DN"] = m1y-3*std1y
                        preview_cols.extend([f"{y}_3s1y_UP", f"{y}_3s1y_DN"])
                if '3s2y' in spec_toggles and '製造日期' in df_stat.columns:
                    max_d = df_stat['製造日期'].max()
                    s_2y = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=730))]
                    m2y, std2y = band_stats(s_2y[y])
                    if pd.notna(m2y) and pd.notna(std2y):
                        df[f"{y}_3s2y_UP"] = m2y+3*std2y
                        df[f"{y}_3s2y_DN"] = m2y-3*std2y
                        preview_cols.extend([f"{y}_3s2y_UP", f"{y}_3s2y_DN"])
                if '6s1y' in spec_toggles and '製造日期' in df_stat.columns:
                    max_d = df_stat['製造日期'].max()
                    s_1y6 = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=365))]
                    m1y6, std1y6 = band_stats(s_1y6[y])
                    if pd.notna(m1y6) and pd.notna(std1y6):
                        df[f"{y}_6s1y_UP"] = m1y6+6*std1y6
                        df[f"{y}_6s1y_DN"] = m1y6-6*std1y6
                        preview_cols.extend([f"{y}_6s1y_UP", f"{y}_6s1y_DN"])
                if '6s2y' in spec_toggles and '製造日期' in df_stat.columns:
                    max_d = df_stat['製造日期'].max()
                    s_2y6 = df_stat[df_stat['製造日期'] >= (max_d - pd.Timedelta(days=730))]
                    m2y6, std2y6 = band_stats(s_2y6[y])
                    if pd.notna(m2y6) and pd.notna(std2y6):
                        df[f"{y}_6s2y_UP"] = m2y6+6*std2y6
                        df[f"{y}_6s2y_DN"] = m2y6-6*std2y6
                        preview_cols.extend([f"{y}_6s2y_UP", f"{y}_6s2y_DN"])
                if 'mean' in spec_toggles:
                    _mv = display_mean(df[y])
                    if pd.notna(_mv):
                        df[f"{y}_Mean"] = _mv
                        preview_cols.append(f"{y}_Mean")

        preview_cols = list(dict.fromkeys([c for c in preview_cols if c in df.columns]))

        # float32 cache → shortest-repr float64 so the preview table and the Excel/CSV
        # export show 0.99 instead of 0.990000009536743 (built once, serves both).
        _clean_preview = strip_float32_noise(df[preview_cols])
        table_data = _clean_preview.head(500).to_dict('records')
        table_columns = [{'name': c, 'id': c} for c in preview_cols]

        # Stack Y warning if requested but blocked
        if _stack_y_requested and not _stack_y:
            reasons = []
            if group_x_col or group_y_col: reasons.append('clear GroupX/GroupY')
            if chart_type not in ('scatter', 'line', 'bar'): reasons.append('use scatter/line/bar')
            fig.add_annotation(
                text=f"⚠️ Stack Y disabled: {', '.join(reasons) if reasons else 'check settings'}",
                xref='paper', yref='paper', x=0.5, y=1.02, showarrow=False,
                font=dict(size=11, color='#E65100'), bgcolor='#FFF3E0', bordercolor='#FFB74D',
                borderwidth=1, borderpad=4)

        # Export data (store for download) — A4 lazy optimization:
        # Only serialize the (potentially MB-sized) records when the user actually has
        # the gb_export perm. Otherwise store a tiny truthy sentinel that still satisfies
        # downstream "has-built" checks in gb_apply_time_preset / gb_auto_build_on_apply.
        if 'gb_export' in user_perms:
            export_data = _clean_preview.to_dict('records')
        else:
            export_data = [{'__has_built__': True}]

        # Zone sync info for clientside drop-zone chip population
        _zone_sync = {
            'gb-drop-x': x_col,
            'gb-drop-y': y_cols,
            'gb-drop-y2': y2_cols or [],
            'gb-drop-color': color_col,
            'gb-drop-size': size_col,
            'gb-drop-group-x': group_x_col,
            'gb-drop-group-y': group_y_col,
            '_chart_type': chart_type,
            '_trendline': trendline,
            '_date_group': date_group,
        }

        # Inner Plotly graph always fills the wrapper; wrapper itself auto-grows for
        # stacked-Y / subplots so the entire chart is visible without a vertical scrollbar.
        # User can still drag-resize the wrapper after the build for fine tuning.
        if error_occurred:
            _graph_style = {'height': '480px'}
            _wrap_style = _wrapper_style(480)
        else:
            _graph_style = {'height': '100%', 'width': '100%'}
            _wrap_style = _wrapper_style(_explicit_height if _explicit_height else 480)
        if _use_subplots and _subplot_width:
            _graph_style['minWidth'] = f'{_subplot_width}px'
        return fig, _graph_style, table_data, table_columns, export_data, _zone_sync, _wrap_style

    # ── Export Data & Chart ──
    @app.callback(
        [Output('gb-download-data', 'data'),
         Output('gb-export-excel-status', 'children')],
        [Input('gb-btn-export-done', 'n_clicks')],
        [State('gb-built-data', 'data'), State('group-dropdown', 'value'), State('actual-role', 'data'),
         State('gb-chart-type', 'value'), State('gb-x-axis', 'value'), State('gb-y-axis', 'value'),
         State('role-permissions', 'data')],
        prevent_initial_call=True
    )
    def gb_export_data(n_clicks, built_data, group, role, chart_type, x_col, y_cols, perms):
        status_done = ''
        if not built_data: return dash.no_update, status_done
        # Permission check: gb_export required
        user_perms = perms.get(role, []) if perms else []
        if 'gb_export' not in user_perms:
            return dash.no_update, status_done
        raw_data = built_data.get('df_dict', []) if isinstance(built_data, dict) else built_data
        df = pd.DataFrame(raw_data)
        write_audit_log(role, 'EXPORT_GRAPH_BUILDER', f"Graph Builder · {len(df)} rows", product=group)

        # Apply Manager-defined Export Configuration (EXPORT_GB_OPTS):
        # - expgb_data: include source X/Y/Color/Group columns
        # - expgb_cl/sl/3s1y/3s2y: include limit columns
        # - expgb_chart: embed Excel chart
        # Walk user_perms in order so configured ordering drives column order.
        y_cols_list = y_cols if isinstance(y_cols, list) else ([y_cols] if y_cols else [])
        data_cols = []
        if x_col and x_col in df.columns:
            data_cols.append(x_col)
        for y in y_cols_list:
            if y in df.columns and y not in data_cols:
                data_cols.append(y)

        def _limit_cols(suffix_pairs):
            return [f"{y}{sfx}" for y in y_cols_list for sfx in suffix_pairs if f"{y}{sfx}" in df.columns]

        included = []
        seen = set()
        # Default: if user_perms has no expgb_* set yet (legacy roles), fall back to all-columns export
        has_any = any(isinstance(p, str) and p.startswith('expgb_') for p in user_perms)
        if has_any:
            for p in user_perms:
                if p == 'expgb_data':
                    for c in data_cols:
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_cl':
                    for c in _limit_cols(['_UCL', '_LCL']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_sl':
                    for c in _limit_cols(['_USL', '_LSL']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_3s1y':
                    for c in _limit_cols(['_3s1y_UP', '_3s1y_DN']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_3s2y':
                    for c in _limit_cols(['_3s2y_UP', '_3s2y_DN']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_6s1y':
                    for c in _limit_cols(['_6s1y_UP', '_6s1y_DN']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_6s2y':
                    for c in _limit_cols(['_6s2y_UP', '_6s2y_DN']):
                        if c not in seen: included.append(c); seen.add(c)
                elif p == 'expgb_mean':
                    for c in _limit_cols(['_Mean']):
                        if c not in seen: included.append(c); seen.add(c)
            # VariableInfo items the role marked `vie:<group>:<item>` — append after Manager-ordered
            # data/limit columns. Items must exist in df (they were persisted via preview_cols in build).
            _vie_prefix = f'vie:{group}:'
            for p in user_perms:
                if isinstance(p, str) and p.startswith(_vie_prefix):
                    _item = p[len(_vie_prefix):]
                    if _item and _item in df.columns and _item not in seen:
                        included.append(_item); seen.add(_item)
            df = df[included] if included else df.iloc[:, :0]
        embed_chart = ('expgb_chart' in user_perms) if has_any else True

        import io
        xlsx_buf = io.BytesIO()
        try:
            with pd.ExcelWriter(xlsx_buf, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Chart_Data', index=False)

                # Build native Excel chart if it's scatter or line AND user permits chart embed
                if embed_chart and chart_type in ('scatter', 'line') and x_col in df.columns:
                    workbook = writer.book
                    worksheet = writer.sheets['Chart_Data']
                    
                    # Excel 'scatter' charts only support numeric X axes. If X is categorical, force 'line'.
                    excel_chart_tp = 'scatter' if chart_type == 'scatter' else 'line'
                    if excel_chart_tp == 'scatter' and not pd.api.types.is_numeric_dtype(df[x_col]):
                        excel_chart_tp = 'line'
                        
                    chart = workbook.add_chart({'type': excel_chart_tp})
                    row_count = len(df)
                    
                    df_cols = list(df.columns)
                    y_cols = [y for y in (y_cols if isinstance(y_cols, list) else [y_cols]) if y in df_cols]
                    x_idx = df_cols.index(x_col)
                    
                    colors = ['#4C9ED9', '#e53935', '#43a047', '#ff9800', '#9c27b0', '#795548']
                    
                    for i, y in enumerate(y_cols):
                        y_idx = df_cols.index(y)
                        series_dict = {
                            'name': ['Chart_Data', 0, y_idx],
                            'categories': ['Chart_Data', 1, x_idx, row_count, x_idx],
                            'values': ['Chart_Data', 1, y_idx, row_count, y_idx]
                        }
                        if chart_type == 'scatter':
                            series_dict['marker'] = {'type': 'circle', 'size': 5, 'border': {'color': colors[i % len(colors)]}, 'fill': {'color': colors[i % len(colors)]}}
                            if excel_chart_tp == 'line':
                                series_dict['line'] = {'none': True} # Hide the connecting line
                        else:
                            series_dict['line'] = {'color': colors[i % len(colors)], 'width': 1.5}
                            series_dict['marker'] = {'type': 'circle', 'size': 4, 'border': {'color': colors[i % len(colors)]}, 'fill': {'color': 'white'}}
                        
                        chart.add_series(series_dict)

                        # Plot Limit Series
                        limits = {
                            f"{y}_UCL": {'color': '#e53935', 'dash': 'dash'}, f"{y}_LCL": {'color': '#e53935', 'dash': 'dash'},
                            f"{y}_USL": {'color': 'red', 'dash': 'solid'}, f"{y}_LSL": {'color': 'red', 'dash': 'solid'},
                            f"{y}_Mean": {'color': '#616161', 'dash': 'solid'},
                            f"{y}_3s1y_UP": {'color': '#ff9800', 'dash': 'round_dot'}, f"{y}_3s1y_DN": {'color': '#ff9800', 'dash': 'round_dot'},
                            f"{y}_3s2y_UP": {'color': '#009688', 'dash': 'dash_dot'}, f"{y}_3s2y_DN": {'color': '#009688', 'dash': 'dash_dot'},
                            f"{y}_6s1y_UP": {'color': '#6A1B9A', 'dash': 'long_dash'}, f"{y}_6s1y_DN": {'color': '#6A1B9A', 'dash': 'long_dash'},
                            f"{y}_6s2y_UP": {'color': '#37474F', 'dash': 'long_dash_dot'}, f"{y}_6s2y_DN": {'color': '#37474F', 'dash': 'long_dash_dot'}
                        }
                        for lim_col, style in limits.items():
                            if lim_col in df_cols:
                                idx_lim = df_cols.index(lim_col)
                                chart.add_series({
                                    'name': ['Chart_Data', 0, idx_lim],
                                    'categories': ['Chart_Data', 1, x_idx, row_count, x_idx],
                                    'values': ['Chart_Data', 1, idx_lim, row_count, idx_lim],
                                    'line': {'color': style['color'], 'width': 1.5, 'dash_type': style['dash']} if excel_chart_tp == 'scatter' else {'color': style['color'], 'width': 1.5, 'dash_type': style['dash']},
                                    'marker': {'type': 'none'}
                                })
                    
                    y_title = ', '.join([y for y in y_cols]) if len(y_cols) <= 3 else f"{len(y_cols)} variables"
                    chart.set_title({'name': f"Graph Builder: {y_title} vs {x_col}"})
                    chart.set_x_axis({'name': x_col})
                    chart.set_y_axis({'name': y_title if len(y_cols) == 1 else 'Value'})
                    chart.set_size({'width': 1000, 'height': 450})
                    chart.set_legend({'position': 'top'})
                    worksheet.insert_chart('G2', chart)
                    
        except ImportError:
            with pd.ExcelWriter(xlsx_buf, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Chart_Data', index=False)
                
        xlsx_buf.seek(0)
        _template = get_filename_template(user_perms)
        _fname = build_export_filename(_template, group or 'Export', 'GraphBuilder', 'xlsx', role=role)
        return dcc.send_bytes(xlsx_buf.getvalue(), _fname), status_done

    # ── Reset All ──
    @app.callback(
        [Output('gb-x-axis', 'value', allow_duplicate=True),
         Output('gb-y-axis', 'value', allow_duplicate=True),
         Output('gb-y2-axis', 'value', allow_duplicate=True),
         Output('gb-color', 'value', allow_duplicate=True),
         Output('gb-size', 'value', allow_duplicate=True),
         Output('gb-group-x', 'value', allow_duplicate=True),
         Output('gb-group-y', 'value', allow_duplicate=True),
         Output('gb-trendline', 'value', allow_duplicate=True),
         Output('gb-date-group', 'value', allow_duplicate=True),
         Output('gb-chart-type', 'value', allow_duplicate=True),
         Output('gb-filter-count', 'data', allow_duplicate=True),
         Output('gb-ref-lines-store', 'data', allow_duplicate=True),
         Output('gb-graph', 'figure', allow_duplicate=True),
         Output('gb-graph', 'style', allow_duplicate=True),
         Output('gb-y-display-mode', 'value', allow_duplicate=True),
         Output('gb-built-data', 'data', allow_duplicate=True),
         Output('gb-data-table', 'data', allow_duplicate=True),
         Output('gb-data-table', 'columns', allow_duplicate=True),
         Output('gb-spec-checklist', 'value', allow_duplicate=True),
         Output('gb-axis-config', 'data', allow_duplicate=True),
         Output('gb-style-config', 'data', allow_duplicate=True),
         Output('gb-trace-state-store', 'data', allow_duplicate=True),
         Output('gb-legend-checklist', 'value', allow_duplicate=True)],
        Input('gb-btn-reset-all', 'n_clicks'),
        prevent_initial_call=True
    )
    def gb_reset_all(n):
        fig = go.Figure()
        fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        default_axis_config = {
            'which': 'y',
            'x': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'y': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'y2': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'chart_title': '', 'show_caption': False
        }
        default_style_config = {
            'marker_size': 6, 'marker_opacity': 0.7, 'marker_symbol': 'auto',
            'line_width': 1.5, 'line_dash': 'solid',
            'legend_pos': 'bottom', 'legend_size': 11,
            'series_overrides': [],
            'palette': 'Plotly'
        }
        return (None, [], [], None, None, None, None, 'none', 'none', 'scatter',
                0, [], fig, {'height': '480px'}, 'overlay', [], [], [], [], default_axis_config, default_style_config,
                {}, [])

    # Clientside: clear JS drop zone chips + restore placeholders + reset button highlights on reset
    app.clientside_callback(
        """
        function(n) {
            if(n) {
                ['gb-drop-x','gb-drop-y','gb-drop-y2','gb-drop-color','gb-drop-size','gb-drop-group-x','gb-drop-group-y'].forEach(function(id) {
                    var z = document.getElementById(id);
                    if(z) {
                        z.querySelectorAll('.gb-zone-chip').forEach(function(c){c.remove()});
                        var ph = z.querySelector('.gb-zone-placeholder');
                        if(ph) ph.style.display = '';
                    }
                });
                // Reset chart type buttons (scatter = active)
                var typeMap = {'gb-type-scatter':'#005baa','gb-type-line':'','gb-type-bar':'','gb-type-box':'','gb-type-histogram':'','gb-type-violin':'','gb-type-bubble':'','gb-type-heatmap':'','gb-type-pareto':'','gb-type-correlation':''};
                Object.keys(typeMap).forEach(function(id) {
                    var b = document.getElementById(id);
                    if(b) { var active = typeMap[id]; b.style.backgroundColor = active ? '#005baa' : '#fff'; b.style.color = active ? '#fff' : '#333'; b.style.borderColor = active ? '#005baa' : '#e2e8f0'; }
                });
                // Reset fit buttons (none = active)
                var fitMap = {'gb-fit-none':'#7B1FA2','gb-fit-ols':'','gb-fit-rolling':'','gb-fit-lowess':'','gb-fit-fcst':''};
                Object.keys(fitMap).forEach(function(id) {
                    var b = document.getElementById(id);
                    if(b) { var active = fitMap[id]; b.style.backgroundColor = active ? '#7B1FA2' : '#fff'; b.style.color = active ? '#fff' : '#333'; b.style.borderColor = active ? '#7B1FA2' : '#e2e8f0'; }
                });
                // Reset date group buttons (none = active)
                var dgMap = {'gb-dg-none':'#E65100','gb-dg-w':'','gb-dg-m':'','gb-dg-q':''};
                Object.keys(dgMap).forEach(function(id) {
                    var b = document.getElementById(id);
                    if(b) { var active = dgMap[id]; b.style.backgroundColor = active ? '#E65100' : '#fff'; b.style.color = active ? '#fff' : '#333'; b.style.borderColor = active ? '#E65100' : '#e2e8f0'; }
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-btn-reset-all', 'data-dummy'),
        Input('gb-btn-reset-all', 'n_clicks'),
        prevent_initial_call=True
    )

    # ── Done / Edit Mode Toggle (JMP-like) ──
    # In Done mode: hide left settings panel, only show chart + edit bar
    @app.callback(
        [Output('gb-palette-sidebar', 'style'),
         Output('gb-zone-group-x', 'style'),
         Output('gb-zone-y', 'style'),
         Output('gb-zone-y2', 'style'),
         Output('gb-zone-x', 'style'),
         Output('gb-zone-group-y', 'style'),
         Output('gb-right-panel', 'style'),
         Output('gb-chart-toolbar', 'style'),
         Output('gb-controls-bar', 'style'),
         Output('gb-action-bar', 'style'),
         Output('gb-edit-bar', 'style'),
         Output('gb-view-mode', 'data'),
         Output('gb-data-preview-container', 'style', allow_duplicate=True),
         Output('gb-data-preview-details', 'open'),
         Output('gb-filter-section', 'style', allow_duplicate=True)],
        [Input('gb-btn-done', 'n_clicks'),
         Input('gb-btn-edit', 'n_clicks')],
        [State('gb-view-mode', 'data')],
        prevent_initial_call=True
    )
    def gb_toggle_done_edit(done_clicks, edit_clicks, mode):
        from dash import ctx
        tid = ctx.triggered_id
        HIDE = {'display': 'none'}
        card_style_local = {'backgroundColor': '#ffffff', 'padding': '20px', 'borderRadius': '4px', 'boxShadow': 'none', 'border': '1px solid #e2e8f0', 'marginBottom': '15px'}
        if tid == 'gb-btn-done':
            # Done mode: hide everything except chart + edit bar + data preview
            return (
                HIDE,  # palette sidebar
                HIDE,  # group x
                HIDE,  # y zone
                HIDE,  # y2 zone
                HIDE,  # x zone
                HIDE,  # group y
                HIDE,  # right panel (color/size)
                HIDE,  # chart toolbar
                HIDE,  # controls bar
                HIDE,  # action bar
                {'display': 'flex', 'padding': '8px 0', 'marginBottom': '6px', 'gap': '8px', 'alignItems': 'center'},  # edit bar
                'done',
                {**card_style_local, 'padding': '16px'},  # data preview (keep visible)
                True,  # Auto-expand the table inside details
                HIDE,  # filter section
            )
        else:
            # Edit mode: restore all panels
            toolbar_style = {'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
                             'flexWrap': 'wrap', 'gap': '4px', 'padding': '6px 10px',
                             'backgroundColor': '#f5f6f8', 'borderRadius': '6px 6px 0 0',
                             'borderBottom': f'1px solid {COLOR_BORDER}'}
            y2_edit_style = {'flex': '0 0 90px', 'display': 'flex', 'flexDirection': 'column'}
            return (
                {'flex': '0 0 160px', 'minWidth': '145px'},  # palette sidebar
                {'marginBottom': '4px'},  # group x
                {'flex': '0 0 110px', 'display': 'flex', 'flexDirection': 'column'},  # y zone
                y2_edit_style,  # y2 zone
                {'marginBottom': '4px'},  # x zone
                {'marginBottom': '8px'},  # group y
                {'flex': '0 0 100px', 'paddingTop': '38px'},  # right panel
                toolbar_style,  # chart toolbar
                {'display': 'flex', 'flexDirection': 'column', 'gap': '0',
                 'padding': '8px 12px', 'backgroundColor': '#fafbfc', 'borderRadius': '4px',
                 'border': f'1px solid {COLOR_BORDER}', 'marginBottom': '10px'},  # controls bar (matches layout default)
                {'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '10px'},  # action bar
                HIDE,  # edit bar
                'edit',
                {**card_style_local, 'padding': '16px'},  # data preview
                False,  # Auto-collapse the table inside details
                {'backgroundColor': '#fafbfc', 'borderBottom': f'1px solid {COLOR_BORDER}', 'fontSize': '12px'},  # filter section
            )

    # Export UI feedback handled by server-side callback children output

    # ── Compute PNG filename stem (server-side) ──
    @app.callback(
        Output('gb-export-fname-stem', 'data'),
        [Input('actual-role', 'data'),
         Input('role-permissions', 'data'),
         Input('group-dropdown', 'value')],
        prevent_initial_call=False
    )
    def gb_compute_export_stem(role, perms, group):
        user_perms = (perms or {}).get(role, []) if perms else []
        template = get_filename_template(user_perms)
        fname = build_export_filename(template, group or 'Export', 'GraphBuilder', 'png', role=role)
        return fname[:-4] if fname.lower().endswith('.png') else fname

    # ── Export Chart as PNG (clientside) ──
    app.clientside_callback(
        """
        function(n1, n2, stem) {
            if (!n1 && !n2) return window.dash_clientside.no_update;
            var fname = stem || ('GraphBuilder_Chart_' + new Date().toISOString().slice(0,10));
            setTimeout(function() {
                var wrapper = document.getElementById('gb-graph');
                var graphEl = wrapper ? wrapper.querySelector('.js-plotly-plot') : null;
                if (!graphEl) graphEl = wrapper;
                if (graphEl) {
                    var w = (graphEl._fullLayout && graphEl._fullLayout.width) ? graphEl._fullLayout.width : (graphEl.clientWidth || 1600);
                    var h = (graphEl._fullLayout && graphEl._fullLayout.height) ? graphEl._fullLayout.height : (graphEl.clientHeight || 800);
                    try {
                        window.Plotly.downloadImage(graphEl, {
                            format: 'png', width: w, height: h,
                            filename: fname
                        });
                    } catch(e) {
                        window.Plotly.toImage(graphEl, {format: 'png', width: w, height: h}).then(function(url) {
                            var a = document.createElement('a');
                            a.href = url;
                            a.download = fname + '.png';
                            a.click();
                        });
                    }
                }
            }, 500);
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-view-mode', 'data', allow_duplicate=True),
        [Input('gb-btn-export-chart', 'n_clicks'),
         Input('gb-btn-export-png', 'n_clicks')],
        [State('gb-export-fname-stem', 'data')],
        prevent_initial_call=True
    )

    # ── Copy to Clipboard (clientside) ──
    # Uses Plotly.toImage → canvas blob → clipboard.write / fallback download
    app.clientside_callback(
        """
        function(n, stem) {
            if (!n) return window.dash_clientside.no_update;
            var wrapper = document.getElementById('gb-graph');
            var graphEl = wrapper ? wrapper.querySelector('.js-plotly-plot') : null;
            if (!graphEl) graphEl = wrapper;
            if (!graphEl) return window.dash_clientside.no_update;

            var w = (graphEl._fullLayout && graphEl._fullLayout.width) ? graphEl._fullLayout.width : (graphEl.clientWidth || 1600);
            var h = (graphEl._fullLayout && graphEl._fullLayout.height) ? graphEl._fullLayout.height : (graphEl.clientHeight || 800);
            var fname = stem || ('GraphBuilder_Chart_' + new Date().toISOString().slice(0,10));

            function fallbackDownload(dataUrl) {
                var a = document.createElement('a');
                a.href = dataUrl;
                a.download = fname + '.png';
                a.click();
                window.ToastHelper.showInlineBadge('gb-clipboard-toast', 'Downloaded as PNG (clipboard needs HTTPS)', '#FB8C00');
            }

            window.Plotly.toImage(graphEl, {format: 'png', width: w, height: h}).then(function(dataUrl) {
                window.ClipboardHelper.copyImage(
                    dataUrl,
                    function() { window.ToastHelper.showInlineBadge('gb-clipboard-toast', 'Copied to clipboard!', '#43A047'); },
                    function() { fallbackDownload(dataUrl); }
                );
            }).catch(function() {
                window.ToastHelper.showInlineBadge('gb-clipboard-toast', 'Error generating image', '#e53935');
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-clipboard-toast', 'style', allow_duplicate=True),
        Input('gb-btn-clipboard', 'n_clicks'),
        [State('gb-export-fname-stem', 'data')],
        prevent_initial_call=True
    )

    # ── Style Modal Toggle (open/close) ──
    @app.callback(
        [Output('gb-style-modal-backdrop', 'style'),
         Output('gb-style-config', 'data'),
         Output('gb-style-marker-size', 'value'),
         Output('gb-style-marker-opacity', 'value'),
         Output('gb-style-marker-symbol', 'value'),
         Output('gb-style-line-width', 'value'),
         Output('gb-style-line-dash', 'value'),
         Output('gb-style-palette', 'value'),
         Output('gb-style-legend-pos', 'value'),
         Output('gb-style-legend-size', 'value')]
        + [Output(f'gb-ss-row-{i}', 'style', allow_duplicate=True) for i in range(6)]
        + [Output(f'gb-ss-{i}-label', 'children', allow_duplicate=True) for i in range(6)]
        + [Output(f'gb-ss-{i}-color', 'value', allow_duplicate=True) for i in range(6)]
        + [Output(f'gb-ss-{i}-symbol', 'value', allow_duplicate=True) for i in range(6)]
        + [Output(f'gb-ss-{i}-dash', 'value', allow_duplicate=True) for i in range(6)],
        [Input('gb-btn-style', 'n_clicks'),
         Input('gb-style-modal-close', 'n_clicks'),
         Input('gb-style-modal-apply', 'n_clicks')],
        [State('gb-style-config', 'data'),
         State('gb-style-marker-size', 'value'),
         State('gb-style-marker-opacity', 'value'),
         State('gb-style-marker-symbol', 'value'),
         State('gb-style-line-width', 'value'),
         State('gb-style-line-dash', 'value'),
         State('gb-style-palette', 'value'),
         State('gb-y-axis', 'value'),
         State('gb-y2-axis', 'value')]
        + [State(f'gb-ss-{i}-color', 'value') for i in range(6)]
        + [State(f'gb-ss-{i}-symbol', 'value') for i in range(6)]
        + [State(f'gb-ss-{i}-dash', 'value') for i in range(6)]
        + [State('gb-style-legend-pos', 'value'), State('gb-style-legend-size', 'value')],
        prevent_initial_call=True
    )
    def gb_style_modal_toggle(open_clicks, close_clicks, apply_clicks,
                               config, m_size, m_opacity, m_symbol,
                               l_width, l_dash, palette,
                               y_cols_val, y2_cols_val,
                               *ss_args_and_leg):
        from dash import ctx
        tid = ctx.triggered_id
        SHOW = {
            'display': 'flex', 'position': 'fixed', 'top': '0', 'left': '0',
            'width': '100%', 'height': '100%', 'backgroundColor': 'rgba(0,0,0,0.5)',
            'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'
        }
        HIDE = {'display': 'none'}
        ROW_SHOW = {'display': 'flex', 'gap': '6px', 'alignItems': 'center', 'marginBottom': '5px'}
        ROW_HIDE = {'display': 'none', 'gap': '6px', 'alignItems': 'center', 'marginBottom': '5px'}
        NU = dash.no_update
        config = config or {}
        # Combine Y + Y2 columns for per-series list
        y_list = list(y_cols_val or [])
        y2_list = list(y2_cols_val or [])
        all_series = y_list + [c for c in y2_list if c not in y_list]
        n_series = min(len(all_series), 6)
        # Unpack per-series states (6 colors, 6 symbols, 6 dashes) + legend pos/size
        ss_colors = list(ss_args_and_leg[0:6])
        ss_symbols = list(ss_args_and_leg[6:12])
        ss_dashes = list(ss_args_and_leg[12:18])
        leg_pos_state = ss_args_and_leg[18] if len(ss_args_and_leg) > 18 else None
        leg_size_state = ss_args_and_leg[19] if len(ss_args_and_leg) > 19 else None

        # Per-series no_update fill
        NU6 = [NU] * 6

        if tid == 'gb-btn-style':
            # Open modal: populate global fields from config
            saved_ov = config.get('series_overrides', [])
            row_styles = [ROW_SHOW if i < n_series else ROW_HIDE for i in range(6)]
            labels = [(('⮕ ' if all_series[i] in y2_list else '') + all_series[i]) if i < n_series else f'Series {i+1}' for i in range(6)]
            colors = [(saved_ov[i].get('color', '') if i < len(saved_ov) else '') for i in range(6)]
            symbols = [(saved_ov[i].get('symbol', 'auto') if i < len(saved_ov) else 'auto') for i in range(6)]
            dashes = [(saved_ov[i].get('dash', 'auto') if i < len(saved_ov) else 'auto') for i in range(6)]
            return (SHOW, NU,
                    config.get('marker_size', 6), config.get('marker_opacity', 0.7),
                    config.get('marker_symbol', 'auto'),
                    config.get('line_width', 1.5), config.get('line_dash', 'solid'),
                    config.get('palette', 'Plotly'),
                    config.get('legend_pos', 'bottom'), config.get('legend_size', 11),
                    *row_styles, *labels, *colors, *symbols, *dashes)

        elif tid == 'gb-style-modal-apply':
            # Build new config from current form values
            new_config = dict(config)  # shallow copy
            new_config['marker_size'] = m_size or 6
            new_config['marker_opacity'] = m_opacity or 0.7
            new_config['marker_symbol'] = m_symbol or 'auto'
            new_config['line_width'] = l_width or 1.5
            new_config['line_dash'] = l_dash or 'solid'
            new_config['palette'] = palette or 'Plotly'
            new_config['legend_pos'] = leg_pos_state or 'bottom'
            new_config['legend_size'] = leg_size_state or 11
            new_config['series_overrides'] = [
                {'color': ss_colors[i] or '', 'symbol': ss_symbols[i] or 'auto', 'dash': ss_dashes[i] or 'auto'}
                for i in range(6)
            ]
            # Only update store if something actually changed — avoids unnecessary rebuild
            config_changed = (new_config != config)
            return (HIDE, new_config if config_changed else NU, NU, NU, NU, NU, NU, NU, NU, NU,
                    *NU6, *NU6, *NU6, *NU6, *NU6)

        else:  # close
            return (HIDE, NU, NU, NU, NU, NU, NU, NU, NU, NU,
                    *NU6, *NU6, *NU6, *NU6, *NU6)

    # ── Axis Modal Toggle (open/close) ──
    @app.callback(
        [Output('gb-axis-modal-backdrop', 'style'),
         Output('gb-axis-modal-title', 'children'),
         Output('gb-axis-config', 'data'),
         Output('gb-axis-dtick', 'value'),
         Output('gb-axis-nticks', 'value'),
         Output('gb-axis-format', 'value'),
         Output('gb-axis-grid-style', 'value'),
         Output('gb-custom-chart-title', 'value'),
         Output('gb-axis-custom-title', 'value'),
         Output('gb-axis-title-label', 'children'),
         Output('gb-show-caption', 'value'),
         Output('gb-axis-tick-fontsize', 'value'),
         Output('gb-axis-title-fontsize', 'value')],
        [Input('gb-btn-axis-y', 'n_clicks'),
         Input('gb-btn-axis-x', 'n_clicks'),
         Input('gb-btn-axis-y2', 'n_clicks'),
         Input('gb-axis-modal-close', 'n_clicks'),
         Input('gb-axis-modal-apply', 'n_clicks')],
        [State('gb-axis-config', 'data'),
         State('gb-axis-dtick', 'value'),
         State('gb-axis-nticks', 'value'),
         State('gb-axis-format', 'value'),
         State('gb-axis-grid-style', 'value'),
         State('gb-custom-chart-title', 'value'),
         State('gb-axis-custom-title', 'value'),
         State('gb-show-caption', 'value'),
         State('gb-axis-tick-fontsize', 'value'),
         State('gb-axis-title-fontsize', 'value')],
        prevent_initial_call=True
    )
    def gb_axis_modal_toggle(y_clicks, x_clicks, y2_clicks, close_clicks, apply_clicks,
                              config, dtick, nticks, fmt, grid_style,
                              chart_title, axis_title, show_caption, tick_fontsize, title_fontsize):
        from dash import ctx
        tid = ctx.triggered_id

        if not any([y_clicks, x_clicks, y2_clicks, close_clicks, apply_clicks]):
            raise dash.exceptions.PreventUpdate
        SHOW = {
            'display': 'flex', 'position': 'fixed', 'top': '0', 'left': '0',
            'width': '100%', 'height': '100%', 'backgroundColor': 'rgba(0,0,0,0.5)',
            'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'
        }
        HIDE = {'display': 'none'}
        NU = dash.no_update

        if tid in ('gb-btn-axis-y', 'gb-btn-axis-x', 'gb-btn-axis-y2'):
            which_ax = 'y2' if tid == 'gb-btn-axis-y2' else ('y' if tid == 'gb-btn-axis-y' else 'x')
            config = config or {'which': which_ax, 'x': {}, 'y': {}, 'y2': {}, 'chart_title': '', 'show_caption': False}
            if 'y2' not in config: config['y2'] = {}
            config['which'] = which_ax
            ax_conf = config.get(which_ax, {})
            ax_labels = {'y': '🏷️ Y-Axis Title:', 'x': '🏷️ X-Axis Title:', 'y2': '🏷️ Y2-Axis Title:'}
            ax_lbl = ax_labels.get(which_ax, '🏷️ Axis Title:')
            return (
                SHOW, f"📏 {which_ax.upper()}-Axis Settings & Reference Lines", config,
                ax_conf.get('dtick'), ax_conf.get('nticks', 10),
                ax_conf.get('format', ''), ax_conf.get('grid_style', 'solid'),
                config.get('chart_title', ''),
                ax_conf.get('title', ''),
                ax_lbl,
                ['show'] if config.get('show_caption') else [],
                ax_conf.get('tick_fontsize', 11),
                ax_conf.get('title_fontsize', 14)
            )

        elif tid == 'gb-axis-modal-apply':
            import copy
            old_config = config or {'which': 'y', 'x': {}, 'y': {}, 'chart_title': '', 'show_caption': False}
            new_config = copy.deepcopy(old_config)
            which_ax = new_config.get('which', 'y')
            if which_ax not in new_config:
                new_config[which_ax] = {}
            new_config[which_ax]['dtick'] = dtick
            new_config[which_ax]['nticks'] = nticks
            new_config[which_ax]['format'] = fmt or ''
            new_config[which_ax]['grid_style'] = grid_style or 'solid'
            new_config[which_ax]['title'] = axis_title or ''
            new_config[which_ax]['tick_fontsize'] = tick_fontsize or 11
            new_config[which_ax]['title_fontsize'] = title_fontsize or 14
            new_config['chart_title'] = chart_title or ''
            new_config['show_caption'] = bool(show_caption)
            config_changed = (new_config != old_config)
            return HIDE, NU, new_config if config_changed else NU, NU, NU, NU, NU, NU, NU, NU, NU, NU, NU

        else:  # close
            return HIDE, NU, config or NU, NU, NU, NU, NU, NU, NU, NU, NU, NU, NU

    # ── Reference Line Management ──
    @app.callback(
        [Output('gb-ref-lines-store', 'data'),
         Output('gb-ref-lines-list', 'children')],
        [Input('gb-ref-line-add', 'n_clicks'),
         Input({'type': 'gb-delete-ref-line', 'index': dash.ALL}, 'n_clicks'),
         Input('gb-axis-config', 'data')],
        [State('gb-ref-line-value', 'value'),
         State('gb-ref-line-label', 'value'),
         State('gb-ref-line-color', 'value'),
         State('gb-ref-line-style', 'value'),
         State('gb-ref-lines-store', 'data')],
        prevent_initial_call=True
    )
    def gb_manage_ref_lines(add_clicks, del_clicks_list, config, value, label, color, style, existing):
        from dash import ctx
        tid = ctx.triggered_id
        
        config = config or {}
        which_ax = config.get('which', 'y')
        existing = existing or []

        if isinstance(tid, dict) and tid.get('type') == 'gb-delete-ref-line':
            del_idx = tid.get('index')
            if del_idx is not None and del_idx < len(existing):
                existing.pop(del_idx)
        elif tid == 'gb-ref-line-add' and value is not None:
            existing.append({
                'value': value,
                'label': label or f'{which_ax.upper()}={value}',
                'color': color or '#e53935',
                'style': style or 'dash',
                'axis': which_ax
            })
            
        # Build visual list FOR CURRENT AXIS
        items = []
        for i, ref in enumerate(existing):
            if ref.get('axis', 'y') != which_ax: continue
            items.append(html.Div([
                html.Span(f"● {ref['label']} = {ref['value']}", style={'fontSize': '12px', 'color': ref['color'], 'fontWeight': 'bold'}),
                html.Span(f" ({ref['style']})", style={'fontSize': '10px', 'color': '#999', 'marginLeft': '4px'}),
                html.Button("🗑️", id={'type': 'gb-delete-ref-line', 'index': i}, style={'marginLeft': 'auto', 'background': 'none', 'border': 'none', 'cursor': 'pointer', 'fontSize': '12px', 'padding': '0'})
            ], style={'display': 'flex', 'alignItems': 'center', 'padding': '4px 8px', 'backgroundColor': '#fff', 'border': '1px solid #e0e0e0', 'borderRadius': '4px', 'marginBottom': '4px'}))
            
        return existing, items

    # ── Auto-Build on Apply: trigger build when Style / Axis config stores change ──
    # Routes through `gb-rebuild-signal` (single consolidated rebuild source) instead of
    # bumping gb-btn-build.n_clicks. Build callback listens to both — direct click + signal.
    @app.callback(
        Output('gb-rebuild-signal', 'data', allow_duplicate=True),
        [Input('gb-style-config', 'data'),
         Input('gb-axis-config', 'data')],
        [State('gb-built-data', 'data'),
         State('gb-rebuild-signal', 'data')],
        prevent_initial_call=True
    )
    def gb_auto_build_on_apply(style_cfg, axis_cfg, built_data, current_signal):
        # Only auto-build if a graph was previously built
        if not built_data:
            raise dash.exceptions.PreventUpdate
        return (current_signal or 0) + 1

    # ── Auto-Build on Filter change ──
    # Filter inputs are debounced (commit on blur/Enter) — bumping the rebuild signal here
    # re-runs the build callback so the user doesn't have to click Build after each filter edit.
    @app.callback(
        Output('gb-rebuild-signal', 'data', allow_duplicate=True),
        [Input({'type': 'gb-filter-col', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-min', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-max', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-str', 'index': ALL}, 'value')],
        [State('gb-built-data', 'data'),
         State('gb-rebuild-signal', 'data')],
        prevent_initial_call=True
    )
    def gb_auto_build_on_filter(_fcol, _fmin, _fmax, _fstr, built_data, current_signal):
        if not built_data:
            raise dash.exceptions.PreventUpdate
        return (current_signal or 0) + 1

    # ── Server-side filter encoder ──
    # Maintains a base64-encoded JSON of all non-empty filter rows in `gb-filter-encoded`.
    # Share Link and Save Config clientside callbacks read this single string instead of
    # trying to receive pattern-matching State arrays directly (which can misbehave in
    # clientside callbacks across Dash versions).
    @app.callback(
        Output('gb-filter-encoded', 'data'),
        [Input({'type': 'gb-filter-col', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-min', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-max', 'index': ALL}, 'value'),
         Input({'type': 'gb-filter-str', 'index': ALL}, 'value')],
    )
    def gb_encode_filters(fcols, fmins, fmaxs, fstrs):
        import base64
        rows = []
        for i in range(len(fcols or [])):
            c = fcols[i] if fcols else None
            if not c:
                continue
            mn = fmins[i] if (fmins and i < len(fmins)) else None
            mx = fmaxs[i] if (fmaxs and i < len(fmaxs)) else None
            s = fstrs[i] if (fstrs and i < len(fstrs)) else None
            if (mn in (None, '')) and (mx in (None, '')) and (not s):
                continue
            rows.append({'c': c, 'mn': mn, 'mx': mx, 's': s})
        if not rows:
            return ''
        return base64.b64encode(json.dumps(rows, ensure_ascii=False).encode('utf-8')).decode('ascii')

    # ── Populate Match dropdown options when Column is picked ──
    # MATCH scopes the output to the same row's Match dropdown only. Options come from the
    # source df's distinct values for that column, restricted to the currently-selected date
    # range so the dropdown only offers values that actually exist in that window.
    #
    # Wildcard support: dcc.Dropdown only lets users pick from `options`, so when the user
    # types a glob like `A-97*` or `*-9*` in the search box, we inject it as a synthetic
    # option (prefixed with ) so it becomes pickable. Already-selected wildcard values
    # are also preserved so they don't vanish on re-render.
    @app.callback(
        Output({'type': 'gb-filter-str', 'index': MATCH}, 'options'),
        [Input({'type': 'gb-filter-col', 'index': MATCH}, 'value'),
         Input({'type': 'gb-filter-str', 'index': MATCH}, 'search_value'),
         Input('group-dropdown', 'value'),
         Input('gb-date-picker-range', 'start_date'),
         Input('gb-date-picker-range', 'end_date')],
        State({'type': 'gb-filter-str', 'index': MATCH}, 'value'),
        prevent_initial_call=True
    )
    def gb_populate_filter_str_options(col, search_value, group, start_date_str, end_date_str, current_value):
        if not col or not group:
            return []
        try:
            from app.models.data_loader import load_db_data
            df_stat, *_ = load_db_data(group, output_base_dir, rule_config)
            if df_stat is None or df_stat.empty or col not in df_stat.columns:
                return []
            # Restrict to the selected date window before extracting distinct values.
            if '製造日期' in df_stat.columns and (start_date_str or end_date_str):
                dates = pd.to_datetime(df_stat['製造日期'], errors='coerce')
                mask = pd.Series(True, index=df_stat.index)
                if start_date_str:
                    mask &= dates >= pd.to_datetime(start_date_str)
                if end_date_str:
                    mask &= dates <= pd.to_datetime(end_date_str)
                df_stat = df_stat[mask]
                if df_stat.empty and not (search_value or current_value):
                    return []
            # Distinct, non-null, string-coerced values, sorted for stable UX.
            vals = df_stat[col].dropna().astype(str).str.strip() if not df_stat.empty else pd.Series(dtype=str)
            vals = sorted({v for v in vals if v})
            # Cap to avoid mega-dropdowns on high-cardinality columns (e.g. LotNo).
            if len(vals) > 2000:
                vals = vals[:2000]
            options = [{'label': v, 'value': v} for v in vals]
            existing = {o['value'] for o in options}

            # Inject already-selected wildcard / unknown values so they stay visible.
            if current_value:
                selected = current_value if isinstance(current_value, list) else [current_value]
                for v in selected:
                    if v and v not in existing:
                        options.insert(0, {'label': f'🔍 {v}', 'value': v})
                        existing.add(v)

            # Inject the currently-typed wildcard pattern so the user can click to add it.
            if search_value and '*' in search_value and search_value not in existing:
                options.insert(0, {'label': f'🔍 Pattern: {search_value}', 'value': search_value})

            return options
        except Exception:
            return []

    # ── Sync legend UI from style-config store (for URL param loading) ──
    app.clientside_callback(
        """
        function(cfg) {
            if (!cfg) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            return [cfg.legend_pos || 'bottom', cfg.legend_size || 11];
        }
        """,
        [Output('gb-style-legend-pos', 'value', allow_duplicate=True),
         Output('gb-style-legend-size', 'value', allow_duplicate=True)],
        Input('gb-style-config', 'data'),
        prevent_initial_call=True
    )
    # ── Share Link: encode current settings into URL and copy to clipboard ──
    app.clientside_callback(
        """
        function(n, x_col, y_cols, y2_cols, chart_type, trendline, color_col, size_col,
                 date_group, group_x, group_y, y_mode, ma_win,
                 start_date, end_date, spec_toggles, style_cfg, axis_cfg, group, fig,
                 cur_leg_pos, cur_leg_size, filt_encoded) {
            if (!n) return '';
            var params = new URLSearchParams();
            if (group) params.set('product', group);
            params.set('page', 'graph-builder');
            if (x_col) params.set('x', x_col);
            if (y_cols && y_cols.length) params.set('y', y_cols.join(','));
            if (y2_cols && y2_cols.length) params.set('y2', y2_cols.join(','));
            if (chart_type) params.set('chart', chart_type);
            if (trendline && trendline !== 'none') params.set('fit', trendline);
            if (color_col) params.set('color', color_col);
            if (size_col) params.set('size', size_col);
            if (date_group && date_group !== 'none') params.set('dg', date_group);
            if (group_x) params.set('gx', group_x);
            if (group_y) params.set('gy', group_y);
            if (y_mode && y_mode !== 'overlay') params.set('ymode', y_mode);
            if (ma_win && ma_win !== 20) params.set('ma', ma_win);
            if (start_date) params.set('start', start_date);
            if (end_date) params.set('end', end_date);
            if (spec_toggles && spec_toggles.length) params.set('specs', spec_toggles.join(','));
            // Inject current legend pos/size from UI into style before encoding
            var styleCopy = style_cfg ? JSON.parse(JSON.stringify(style_cfg)) : {};
            if (cur_leg_pos) styleCopy.legend_pos = cur_leg_pos;
            if (cur_leg_size) styleCopy.legend_size = cur_leg_size;
            if (Object.keys(styleCopy).length) params.set('style', btoa(JSON.stringify(styleCopy)));
            if (axis_cfg) params.set('axis', btoa(JSON.stringify(axis_cfg)));
            // Filters: pre-encoded server-side into a single base64 string for reliability.
            if (filt_encoded) params.set('filt', filt_encoded);
            // Encode legend visibility state from current figure
            if (fig && fig.data) {
                var lgndState = {};
                var hasState = false;
                fig.data.forEach(function(t, i) {
                    var vis = (t.visible === undefined || t.visible === true);
                    var leg = (t.showlegend === undefined || t.showlegend === true);
                    if (!vis || !leg) {
                        lgndState[i] = {v: vis, l: leg};
                        hasState = true;
                    }
                });
                if (hasState) params.set('lgnd', btoa(JSON.stringify(lgndState)));
            }
            var url = window.location.origin + window.location.pathname + '?' + params.toString();

            window.ClipboardHelper.copyText(url, function() {
                window.ToastHelper.showInline('gb-share-toast', 'Link copied!', '#2E7D32');
            });
            return '';
        }
        """,
        Output('gb-share-toast', 'children'),
        Input('gb-btn-share', 'n_clicks'),
        [State('gb-x-axis', 'value'), State('gb-y-axis', 'value'), State('gb-y2-axis', 'value'),
         State('gb-chart-type', 'value'), State('gb-trendline', 'value'), State('gb-color', 'value'),
         State('gb-size', 'value'),
         State('gb-date-group', 'value'), State('gb-group-x', 'value'), State('gb-group-y', 'value'),
         State('gb-y-display-mode', 'value'), State('gb-ma-window', 'value'),
         State('gb-date-picker-range', 'start_date'), State('gb-date-picker-range', 'end_date'),
         State('gb-spec-checklist', 'value'), State('gb-style-config', 'data'), State('gb-axis-config', 'data'),
         State('group-dropdown', 'value'), State('gb-graph', 'figure'),
         State('gb-style-legend-pos', 'value'), State('gb-style-legend-size', 'value'),
         State('gb-filter-encoded', 'data')],
        prevent_initial_call=True
    )

    # ── Save current config to localStorage ──
    app.clientside_callback(
        """
        function(n, x_col, y_cols, y2_cols, chart_type, trendline, color_col, size_col,
                 date_group, group_x, group_y, y_mode, ma_win,
                 start_date, end_date, spec_toggles, style_cfg, axis_cfg, group, fig,
                 cur_leg_pos, cur_leg_size, filt_encoded) {
            if (!n) return window.dash_clientside.no_update;
            var name = window.prompt('Save config as:');
            if (!name) return window.dash_clientside.no_update;
            name = name.trim();
            if (!name) return window.dash_clientside.no_update;

            var params = new URLSearchParams();
            if (group) params.set('product', group);
            params.set('page', 'graph-builder');
            if (x_col) params.set('x', x_col);
            if (y_cols && y_cols.length) params.set('y', y_cols.join(','));
            if (y2_cols && y2_cols.length) params.set('y2', y2_cols.join(','));
            if (chart_type) params.set('chart', chart_type);
            if (trendline && trendline !== 'none') params.set('fit', trendline);
            if (color_col) params.set('color', color_col);
            if (size_col) params.set('size', size_col);
            if (date_group && date_group !== 'none') params.set('dg', date_group);
            if (group_x) params.set('gx', group_x);
            if (group_y) params.set('gy', group_y);
            if (y_mode && y_mode !== 'overlay') params.set('ymode', y_mode);
            if (ma_win && ma_win !== 20) params.set('ma', ma_win);
            if (start_date) params.set('start', start_date);
            if (end_date) params.set('end', end_date);
            if (spec_toggles && spec_toggles.length) params.set('specs', spec_toggles.join(','));
            var styleCopy = style_cfg ? JSON.parse(JSON.stringify(style_cfg)) : {};
            if (cur_leg_pos) styleCopy.legend_pos = cur_leg_pos;
            if (cur_leg_size) styleCopy.legend_size = cur_leg_size;
            if (Object.keys(styleCopy).length) params.set('style', btoa(JSON.stringify(styleCopy)));
            if (axis_cfg) params.set('axis', btoa(JSON.stringify(axis_cfg)));
            // Filters: pre-encoded server-side into a single base64 string for reliability.
            if (filt_encoded) params.set('filt', filt_encoded);

            try {
                var key = 'jmp_gb_configs';
                var raw = window.localStorage.getItem(key);
                var cfgs = raw ? JSON.parse(raw) : {};
                cfgs[name] = params.toString();
                window.localStorage.setItem(key, JSON.stringify(cfgs));
                window.ToastHelper.showInline('gb-config-toast', '💾 Saved "' + name + '"', '#5E35B1');
            } catch (e) {
                window.ToastHelper.showInline('gb-config-toast', '❌ Save failed', '#e53935');
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-config-toast', 'children'),
        Input('gb-btn-save-config', 'n_clicks'),
        [State('gb-x-axis', 'value'), State('gb-y-axis', 'value'), State('gb-y2-axis', 'value'),
         State('gb-chart-type', 'value'), State('gb-trendline', 'value'), State('gb-color', 'value'),
         State('gb-size', 'value'),
         State('gb-date-group', 'value'), State('gb-group-x', 'value'), State('gb-group-y', 'value'),
         State('gb-y-display-mode', 'value'), State('gb-ma-window', 'value'),
         State('gb-date-picker-range', 'start_date'), State('gb-date-picker-range', 'end_date'),
         State('gb-spec-checklist', 'value'), State('gb-style-config', 'data'), State('gb-axis-config', 'data'),
         State('group-dropdown', 'value'), State('gb-graph', 'figure'),
         State('gb-style-legend-pos', 'value'), State('gb-style-legend-size', 'value'),
         State('gb-filter-encoded', 'data')],
        prevent_initial_call=True
    )

    # ── Refresh saved-configs dropdown from localStorage (triggered by save/delete or page load) ──
    app.clientside_callback(
        """
        function(saveClicks, deleteClicks) {
            try {
                var raw = window.localStorage.getItem('jmp_gb_configs');
                var cfgs = raw ? JSON.parse(raw) : {};
                var names = Object.keys(cfgs).sort();
                return names.map(function(n) { return {label: n, value: n}; });
            } catch (e) {
                return [];
            }
        }
        """,
        Output('gb-saved-configs', 'options'),
        [Input('gb-btn-save-config', 'n_clicks'),
         Input('gb-btn-delete-config', 'n_clicks')]
    )

    # ── Load config: navigate to saved URL ──
    app.clientside_callback(
        """
        function(name) {
            if (!name) return window.dash_clientside.no_update;
            try {
                var raw = window.localStorage.getItem('jmp_gb_configs');
                var cfgs = raw ? JSON.parse(raw) : {};
                var qs = cfgs[name];
                if (qs) {
                    window.location.href = window.location.origin + window.location.pathname + '?' + qs;
                }
            } catch (e) {}
            return window.dash_clientside.no_update;
        }
        """,
        Output('gb-saved-configs', 'search_value'),
        Input('gb-saved-configs', 'value'),
        prevent_initial_call=True
    )

    # ── Delete selected config ──
    app.clientside_callback(
        """
        function(n, name) {
            if (!n || !name) return window.dash_clientside.no_update;
            if (!window.confirm('Delete config "' + name + '"?')) {
                return window.dash_clientside.no_update;
            }
            try {
                var raw = window.localStorage.getItem('jmp_gb_configs');
                var cfgs = raw ? JSON.parse(raw) : {};
                delete cfgs[name];
                window.localStorage.setItem('jmp_gb_configs', JSON.stringify(cfgs));
                window.ToastHelper.showInline('gb-config-toast', '🗑️ Deleted "' + name + '"', '#757575');
            } catch (e) {}
            return null;
        }
        """,
        Output('gb-saved-configs', 'value'),
        Input('gb-btn-delete-config', 'n_clicks'),
        State('gb-saved-configs', 'value'),
        prevent_initial_call=True
    )



    # Step 2: When column options are populated (gb-x-axis options change), apply stored URL params
    # The clientside URL parser fires instantly before server round-trips, so gb-url-params
    # is always available by the time this callback fires.
    @app.callback(
        [Output('gb-x-axis', 'value', allow_duplicate=True),
         Output('gb-y-axis', 'value', allow_duplicate=True),
         Output('gb-y2-axis', 'value', allow_duplicate=True),
         Output('gb-group-x', 'value', allow_duplicate=True),
         Output('gb-group-y', 'value', allow_duplicate=True),
         Output('gb-color', 'value', allow_duplicate=True),
         Output('gb-size', 'value', allow_duplicate=True),
         Output('gb-chart-type', 'value', allow_duplicate=True),
         Output('gb-trendline', 'value', allow_duplicate=True),
         Output('gb-date-group', 'value', allow_duplicate=True),
         Output('gb-y-display-mode', 'value', allow_duplicate=True),
         Output('gb-ma-window', 'value', allow_duplicate=True),
         Output('gb-date-picker-range', 'start_date', allow_duplicate=True),
         Output('gb-date-picker-range', 'end_date', allow_duplicate=True),
         Output('gb-spec-checklist', 'value', allow_duplicate=True),
         Output('gb-style-config', 'data', allow_duplicate=True),
         Output('gb-axis-config', 'data', allow_duplicate=True),
         Output('gb-url-params', 'data', allow_duplicate=True),
         Output('gb-lgnd-pending', 'data', allow_duplicate=True),
         Output('gb-style-legend-pos', 'value', allow_duplicate=True),
         Output('gb-style-legend-size', 'value', allow_duplicate=True),
         Output('gb-filter-container', 'children', allow_duplicate=True),
         Output('gb-filter-count', 'data', allow_duplicate=True),
         Output('gb-rebuild-signal', 'data', allow_duplicate=True)],
        Input('gb-x-axis', 'options'),
        [State('gb-url-params', 'data'), State('gb-rebuild-signal', 'data'),
         State('group-dropdown', 'value'),
         State('role-permissions', 'data'), State('actual-role', 'data')],
        prevent_initial_call=True
    )
    def gb_apply_url_params(x_options, url_params, current_signal, group, perms, role):

        if not url_params or not x_options:
            raise dash.exceptions.PreventUpdate
        import json, base64
        NU = dash.no_update
        p = url_params

        y_val = p['y'].split(',') if 'y' in p else NU
        y2_val = p['y2'].split(',') if 'y2' in p else NU
        spec_val = p['spec'].split(',') if 'spec' in p else NU
        ma_val = int(p['ma']) if 'ma' in p else NU

        style_cfg = NU
        if 'style' in p:
            try: style_cfg = json.loads(base64.b64decode(p['style']))
            except Exception: pass
        axis_cfg = NU
        if 'axis' in p:
            try: axis_cfg = json.loads(base64.b64decode(p['axis']))
            except Exception: pass

        lgnd_pending = NU
        if 'lgnd' in p:
            try:
                import json as _j, base64 as _b
                lgnd_pending = _j.loads(_b.b64decode(p['lgnd']))
            except Exception: pass

        # Extract legend_pos/legend_size from decoded style_cfg for direct UI sync
        leg_pos_val = NU
        leg_size_val = NU
        if style_cfg is not NU and isinstance(style_cfg, dict):
            leg_pos_val = style_cfg.get('legend_pos', NU)
            leg_size_val = style_cfg.get('legend_size', NU)

        # Filter rows — decode the `filt` JSON-b64 list and rebuild the container children.
        filter_children = NU
        filter_count_out = NU
        if 'filt' in p:
            try:
                rows = json.loads(base64.b64decode(p['filt']))
                if isinstance(rows, list) and rows:
                    col_opts = _gb_filter_col_opts(group, perms, role)
                    filter_children = []
                    for i, r in enumerate(rows, start=1):
                        filter_children.append(_gb_build_filter_row(
                            idx=i,
                            col_opts=col_opts,
                            col_val=r.get('c'),
                            min_val=r.get('mn'),
                            max_val=r.get('mx'),
                            str_val=r.get('s'),
                        ))
                    filter_count_out = len(rows)
            except Exception:
                pass

        return (
            p.get('x', NU),       # 1. x-axis
            y_val,                # 2. y-axis
            y2_val,               # 3. y2-axis
            p.get('gx', NU),      # 4. group-x
            p.get('gy', NU),      # 5. group-y
            p.get('color', NU),   # 6. color
            p.get('size', NU),    # 7. size
            p.get('chart', NU),   # 8. chart-type
            p.get('fit', NU),     # 9. trendline
            p.get('dg', NU),      # 10. date-group
            p.get('ymode', NU),   # 11. y-display-mode
            ma_val,               # 12. ma-window
            p.get('start', p.get('sd', NU)),  # 13. start_date
            p.get('end', p.get('ed', NU)),    # 14. end_date
            spec_val,             # 15. spec-checklist
            style_cfg,            # 16. style-config
            axis_cfg,             # 17. axis-config
            None,                 # 18. Clear url-params (one-shot)
            lgnd_pending,         # 19. lgnd-pending (applied after build by zone-sync)
            leg_pos_val,          # 20. legend-pos UI
            leg_size_val,         # 21. legend-size UI
            filter_children,      # 22. gb-filter-container.children (restored filter rows)
            filter_count_out,     # 23. gb-filter-count.data (so next + Add gets a fresh idx)
            (current_signal or 0) + 1,  # 24. Bump rebuild signal (A3 consolidated trigger)
        )

    # Step 3: Sync visual drop-zone chips after every build
    app.clientside_callback(
        """
        function(zone_sync, lgnd_pending) {
            if (!zone_sync || !Object.keys(zone_sync).length) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            setTimeout(function() {
                // Populate each drop zone directly from server-computed values
                Object.keys(zone_sync).forEach(function(zoneId) {
                    var val = zone_sync[zoneId];
                    if (!val) return;
                    var values = Array.isArray(val) ? val : [val];
                    var zone = document.getElementById(zoneId);
                    if (!zone) return;
                    // Check existing chips
                    var existing = [];
                    zone.querySelectorAll('.gb-zone-chip').forEach(function(c) {
                        existing.push(c.getAttribute('data-var'));
                    });
                    values.forEach(function(v) {
                        if (v && typeof v === 'string' && existing.indexOf(v) === -1) {
                            if (window.gbAddVarToZoneNoSync) {
                                window.gbAddVarToZoneNoSync(zoneId, v);
                            }
                        }
                    });
                });
                // Sync button highlights using server-provided values
                if (window.gbSyncButtonHighlightsDirect) {
                    window.gbSyncButtonHighlightsDirect(
                        zone_sync._chart_type, zone_sync._trendline, zone_sync._date_group
                    );
                }
                // Apply legend visibility from pending store (decoded in gb_apply_url_params)
                if (lgnd_pending && typeof lgnd_pending === 'object') {
                    var graphEl = document.getElementById('gb-graph');
                    var plotEl = graphEl ? graphEl.querySelector('.js-plotly-plot') : null;
                    if (!plotEl) plotEl = graphEl;
                    if (plotEl && plotEl.data) {
                        Object.keys(lgnd_pending).forEach(function(idxStr) {
                            var idx = parseInt(idxStr);
                            var st = lgnd_pending[idxStr];
                            if (!isNaN(idx) && idx < plotEl.data.length) {
                                Plotly.restyle(plotEl, {
                                    visible: st.v ? true : 'legendonly',
                                    showlegend: st.l
                                }, [idx]);
                            }
                        });
                    }
                }
            }, 300);
            // Clear lgnd-pending after use (one-shot)
            return [window.dash_clientside.no_update, null];
        }
        """,
        [Output('gb-url-params', 'data', allow_duplicate=True),
         Output('gb-lgnd-pending', 'data', allow_duplicate=True)],
        Input('gb-zone-sync', 'data'),
        State('gb-lgnd-pending', 'data'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Open modal and populate trace list ──
    app.clientside_callback(
        """
        function(n, fig) {
            if (!n) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            if (!fig || !fig.data || !fig.data.length) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            var SHOW = {
                'display': 'flex', 'position': 'fixed', 'top': '0', 'left': '0',
                'width': '100%', 'height': '100%', 'backgroundColor': 'rgba(0,0,0,0.5)',
                'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'
            };
            window._gbLegendTraces = [];
            var i = 0;
            fig.data.forEach(function(trace, idx) {
                // Do not skip spec lines; allow user to toggle them via the manager
                var name = trace.name || ('Trace ' + idx);
                var visible = (trace.visible === undefined || trace.visible === true) ? true : false;
                var showleg = (trace.showlegend === undefined || trace.showlegend === true) ? true : false;
                var color = '#333';
                if (trace.marker && trace.marker.color && typeof trace.marker.color === 'string') color = trace.marker.color;
                else if (trace.line && trace.line.color) color = trace.line.color;
                
                var str_i = String(i).padStart(4, '0'); // Zero pad to ensure Dash pattern match ALL sorting is safe
                window._gbLegendTraces.push({id_idx: str_i, traceIdx: idx, name: name, visible: visible, showlegend: showleg, color: color});
                i++;
            });
            return [SHOW, window._gbLegendTraces];
        }
        """,
        [Output('gb-legend-modal-backdrop', 'style'),
         Output('gb-legend-traces-store', 'data')],
        Input('gb-btn-legend-mgr', 'n_clicks'),
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Render checkboxes from traces data (server-side for DOM generation) ──
    @app.callback(
        Output('gb-legend-items-container', 'children'),
        Input('gb-legend-traces-store', 'data'),
        prevent_initial_call=True
    )
    def render_legend_items(traces_data):
        if not traces_data:
            raise dash.exceptions.PreventUpdate
        items = []
        for t in traces_data:
            idx_str = t['id_idx']
            name = t['name']
            visible = t['visible']
            showleg = t.get('showlegend', True)
            color = t.get('color', '#333')
            
            # Value array based on boolean state
            val_arr = []
            if visible: val_arr.append('vis')
            if showleg: val_arr.append('leg')
            
            items.append(
                html.Label([
                    dcc.Checklist(
                        id={'type': 'gb-legend-check', 'index': idx_str},
                        options=[{'label': '👀 Graph', 'value': 'vis'}, {'label': '🏷️ Legend', 'value': 'leg'}],
                        value=val_arr,
                        inline=True,
                        style={'display': 'inline-flex', 'marginRight': '8px', 'gap': '4px', 'flexShrink': '0'},
                        inputStyle={'cursor': 'pointer', 'marginRight': '2px'},
                        labelStyle={'fontSize': '11px', 'cursor': 'pointer', 'color': '#666'}
                    ),
                    html.Span('●', style={'color': color, 'marginRight': '6px', 'fontSize': '14px', 'marginLeft': '4px', 'flexShrink': '0'}),
                    html.Span(name, style={'fontSize': '12px', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap', 'flex': '1'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'cursor': 'pointer',
                          'padding': '4px 8px', 'borderRadius': '4px', 'backgroundColor': '#f9f9f9',
                          'border': '1px solid #eee', 'minWidth': '0'})
            )
        return items

    # ── Legend Manager: Close modal ──
    app.clientside_callback(
        """
        function(n) {
            return {'display': 'none'};
        }
        """,
        Output('gb-legend-modal-backdrop', 'style', allow_duplicate=True),
        Input('gb-legend-modal-close', 'n_clicks'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Toggle individual trace visibility ──
    app.clientside_callback(
        """
        function() {
            var args = Array.from(arguments);
            var fig_data = args[args.length - 1]; // State is last
            var checks = args[0]; // ALL returns an array in args[0]
            if (!fig_data || !fig_data.data || !window._gbLegendTraces) return window.dash_clientside.no_update;
            
            var newFig = JSON.parse(JSON.stringify(fig_data));
            var validTraces = window._gbLegendTraces;
            
            if (checks && checks.length === validTraces.length) {
                checks.forEach(function(val_arr, i) {
                    var traceIdx = validTraces[i].traceIdx;
                    var isVis = val_arr && val_arr.includes('vis');
                    var isLeg = val_arr && val_arr.includes('leg');
                    newFig.data[traceIdx].visible = isVis ? true : 'legendonly';
                    newFig.data[traceIdx].showlegend = isLeg;
                });
            }
            return newFig;
        }
        """,
        Output('gb-graph', 'figure', allow_duplicate=True),
        [Input({'type': 'gb-legend-check', 'index': ALL}, 'value')],
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Select All ──
    app.clientside_callback(
        """
        function(n, fig) {
            if (!n || !fig || !fig.data) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            var newFig = JSON.parse(JSON.stringify(fig));
            var newStore = [];
            newFig.data.forEach(function(t, idx) { 
                t.visible = true; 
                t.showlegend = true; 
                var name = t.name || ('Trace ' + idx);
                var color = t.marker && t.marker.color ? t.marker.color : (t.line && t.line.color ? t.line.color : '#333');
                if (Array.isArray(color)) color = color[0];
                newStore.push({
                    'id_idx': idx,
                    'traceIdx': idx,
                    'name': name,
                    'visible': true,
                    'showlegend': true,
                    'color': color
                });
            });
            window._gbLegendTraces = newStore;
            return [newFig, newStore];
        }
        """,
        [Output('gb-graph', 'figure', allow_duplicate=True),
         Output('gb-legend-traces-store', 'data', allow_duplicate=True)],
        Input('gb-legend-select-all', 'n_clicks'),
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Deselect All ──
    app.clientside_callback(
        """
        function(n, fig) {
            if (!n || !fig || !fig.data) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            var newFig = JSON.parse(JSON.stringify(fig));
            var newStore = [];
            newFig.data.forEach(function(t, idx) { 
                t.visible = 'legendonly'; 
                t.showlegend = false; 
                var name = t.name || ('Trace ' + idx);
                var color = t.marker && t.marker.color ? t.marker.color : (t.line && t.line.color ? t.line.color : '#333');
                if (Array.isArray(color)) color = color[0];
                newStore.push({
                    'id_idx': idx,
                    'traceIdx': idx,
                    'name': name,
                    'visible': false,
                    'showlegend': false,
                    'color': color
                });
            });
            window._gbLegendTraces = newStore;
            return [newFig, newStore];
        }
        """,
        [Output('gb-graph', 'figure', allow_duplicate=True),
         Output('gb-legend-traces-store', 'data', allow_duplicate=True)],
        Input('gb-legend-deselect-all', 'n_clicks'),
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )

    # ── Legend Manager: Instant visual update for Legend Pos/Size ──
    app.clientside_callback(
        """
        function(pos, size, fig) {
            if (!fig || !fig.layout) return window.dash_clientside.no_update;
            var newFig = JSON.parse(JSON.stringify(fig));
            var leg = newFig.layout.legend || {};
            var margin = newFig.layout.margin || {l: 50, r: 40, t: 55, b: 50};
            var isY2 = newFig.data && newFig.data.some(function(d) { return d.yaxis === 'y2'; });
            var baseRight = isY2 ? 60 : 40;

            leg.font = leg.font || {};
            if (size) {
                leg.font.size = size;
            }
            
            if (pos === 'top') {
                leg.orientation = 'h'; leg.yanchor = 'bottom'; leg.y = 1.02; leg.xanchor = 'center'; leg.x = 0.5;
                margin.r = baseRight; 
            } else if (pos === 'bottom') {
                leg.orientation = 'h'; leg.yanchor = 'top'; leg.y = -0.35; leg.xanchor = 'center'; leg.x = 0.5;
                margin.r = baseRight; 
                margin.b = Math.max(margin.b || 0, 120);
            } else if (pos === 'right') {
                leg.orientation = 'v'; leg.yanchor = 'top'; leg.y = 1.0; leg.xanchor = 'left'; leg.x = (isY2 ? 1.1 : 1.02);
                margin.r = Math.max(margin.r || 0, 160);
            }
            
            newFig.layout.legend = leg;
            newFig.layout.margin = margin;
            return newFig;
        }
        """,
        Output('gb-graph', 'figure', allow_duplicate=True),
        [Input('gb-style-legend-pos', 'value'), Input('gb-style-legend-size', 'value')],
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )

    # ── Capture legend toggle state into a lightweight store ──
    # Fires on every user legend click (restyleData). Builds {name: {v, l}} keeping only
    # traces whose state differs from default — keeps the payload tiny so Build callbacks
    # don't have to round-trip the entire figure.
    app.clientside_callback(
        """
        function(restyleData, fig) {
            if (!fig || !fig.data) return window.dash_clientside.no_update;
            var state = {};
            fig.data.forEach(function(t) {
                if (!t || !t.name) return;
                var visDefault = (t.visible === undefined || t.visible === true);
                var legDefault = (t.showlegend === undefined || t.showlegend === true);
                if (!visDefault || !legDefault) {
                    state[t.name] = {v: visDefault, l: legDefault};
                }
            });
            return state;
        }
        """,
        Output('gb-trace-state-store', 'data'),
        Input('gb-graph', 'restyleData'),
        State('gb-graph', 'figure'),
        prevent_initial_call=True
    )
