# ==========================================
# JMP-Style Interactive Graph Builder — Standalone Entry Point
# ==========================================
# Run: python main.py
# Then open http://localhost:8050 in your browser.
#
# Place your CSV / Excel / Parquet data files in the sample_data/ folder.
# ==========================================

import os
import sys
import logging

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from app.core.constants import COLOR_PRIMARY, COLOR_ACCENT, COLOR_BG, COLOR_TEXT, COLOR_BORDER
from app.views.graph_builder_layout import build_graph_builder_layout
from app.views.page_graph_builder import register_graph_builder_callbacks
from app.models.data_loader import get_available_groups

# ── Configuration ──────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), 'sample_data')
HOST = '0.0.0.0'
PORT = 8050

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('JMP-GraphBuilder')

# ── Default rule config (all rules enabled) ──
DEFAULT_RULE_CONFIG = {}

# ── Default dash config ──
DEFAULT_DASH_CONFIG = {
    'historyyearstokeep': 2,
    'defaultyaxisunit': 'Value',
    'show_ucl_lcl': True,
    'show_usl_lsl': False,
}

# ── All permissions enabled (no permission gating in standalone mode) ──
ALL_PERMISSIONS = [
    'nav_graph_builder',
    'gb_export', 'gb_export_chart', 'gb_filter', 'gb_trendline',
    'gb_data_preview', 'gb_group_xy', 'gb_subplots',
    'gb_chart_scatter', 'gb_chart_line', 'gb_chart_bar', 'gb_chart_box',
    'gb_chart_histogram', 'gb_chart_violin', 'gb_chart_bubble', 'gb_chart_heatmap',
    'gb_chart_pareto',
    'gb_dual_y', 'gb_edit_titles', 'gb_show_caption', 'gb_ols_stats',
    'allow_custom_reflines', 'gb_share_link', 'gb_clipboard_copy',
    'gb_custom_palette', 'gb_outlier_highlight',
    'show_variable_info', 'show_action_comment', 'view_action_log',
    'fcst_enable', 'fcst_gb',
    'def_fname_dated',
]

# ── OOB items (empty — no detection engine in standalone mode) ──
G_OOB_ITEMS = []
PERM_MAP = {}


def create_app():
    """Create the standalone Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        assets_folder=os.path.join(os.path.dirname(__file__), 'assets'),
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='JMP-Style Interactive Graph Builder',
        update_title='Loading...',
    )

    # ── Shared context (stub for standalone) ──
    shared_ctx = {
        'write_audit_log': lambda *a, **kw: None,
        'G_OOB_ITEMS': G_OOB_ITEMS,
        'PERM_MAP': PERM_MAP,
    }

    # ── App Layout ──
    app.layout = html.Div([
        # Hidden stores for permission/role system (all features unlocked)
        dcc.Store(id='actual-role', data='admin'),
        dcc.Store(id='role-permissions', data={'admin': ALL_PERMISSIONS}),

        # ── Top Navigation Bar ──
        html.Div([
            html.Div([
                html.Span('📊', style={'fontSize': '24px', 'marginRight': '10px'}),
                html.Span('JMP-Style Interactive Graph Builder', style={
                    'fontWeight': '800', 'fontSize': '18px', 'color': '#fff',
                    'letterSpacing': '0.5px',
                }),
            ], style={'display': 'flex', 'alignItems': 'center'}),
            html.Div([
                html.Span('Data Source:', style={
                    'color': 'rgba(255,255,255,0.7)', 'fontSize': '12px',
                    'marginRight': '8px', 'fontWeight': '600',
                }),
                dcc.Dropdown(
                    id='group-dropdown',
                    options=get_available_groups(DATA_DIR),
                    value=None,
                    placeholder='Select a data file...',
                    style={'width': '300px', 'fontSize': '13px'},
                    clearable=True,
                ),
            ], style={'display': 'flex', 'alignItems': 'center'}),
        ], style={
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
            'padding': '10px 24px',
            'background': f'linear-gradient(135deg, {COLOR_PRIMARY}, #1565C0)',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.15)',
        }),

        # ── Graph Builder Layout ──
        build_graph_builder_layout(),

    ], style={'backgroundColor': COLOR_BG, 'minHeight': '100vh', 'fontFamily': "'Inter', 'Segoe UI', sans-serif"})

    # ── Register callbacks ──
    register_graph_builder_callbacks(
        app,
        output_base_dir=DATA_DIR,
        rule_config=DEFAULT_RULE_CONFIG,
        dash_config=DEFAULT_DASH_CONFIG,
        shared_ctx=shared_ctx,
    )

    # ── Auto-refresh dropdown when data files change ──
    @app.callback(
        Output('group-dropdown', 'options'),
        [Input('group-dropdown', 'value')],
        prevent_initial_call=False,
    )
    def refresh_file_list(_):
        return get_available_groups(DATA_DIR)

    return app


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()

    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info(f"📁 Created sample_data/ directory. Place CSV/Excel/Parquet files there.")

    files = get_available_groups(DATA_DIR)
    if not files:
        logger.warning("⚠️  No data files found in sample_data/. Place CSV/Excel/Parquet files there to get started.")

    app = create_app()
    logger.info(f"🚀 JMP-Style Interactive Graph Builder running at http://localhost:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
