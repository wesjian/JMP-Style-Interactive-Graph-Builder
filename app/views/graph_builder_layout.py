"""Graph Builder page layout (extracted from page_graph_builder.py).

build_graph_builder_layout() returns the static component tree for the JMP-style graph builder;
all interactivity lives in register_graph_builder_callbacks (page_graph_builder.py)."""
from dash import dcc, html, dash_table

from app.core.constants import COLOR_PRIMARY, COLOR_ACCENT
from app.views.graph_builder_style import COLOR_TEXT, COLOR_BORDER, btn_style, card_style


def build_graph_builder_layout():
    """Build the Graph Builder layout — JMP-style left settings panel + chart area."""

    # ── Shared styles ──
    zone_label = lambda text, color: html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': color,
        'textTransform': 'uppercase', 'letterSpacing': '0.5px',
        'padding': '2px 0', 'userSelect': 'none'
    })

    def _dz(zone_id, placeholder, color, direction='row', min_h='38px', min_w=None):
        """Create a drop zone container."""
        s = {
            'minHeight': min_h, 'border': f'2px dashed {color}45',
            'borderRadius': '4px', 'padding': '4px 6px',
            'backgroundColor': f'{color}06',
            'display': 'flex', 'flexWrap': 'wrap',
            'gap': '3px', 'alignItems': 'center',
            'transition': 'all 0.15s ease',
        }
        if direction == 'column':
            s.update({'flexDirection': 'column', 'alignItems': 'stretch'})
        if min_w:
            s['minWidth'] = min_w
        return html.Div(id=zone_id, className='gb-drop-zone', children=[
            html.Span(placeholder, className='gb-zone-placeholder',
                      style={'color': f'{color}60', 'fontSize': '10px', 'fontStyle': 'italic', 'pointerEvents': 'none'})
        ], style=s)

    # Chart type as icon buttons (no dropdown)
    def _type_btn(label, value, icon):
        return html.Button(f"{icon}", id=f'gb-type-{value}', n_clicks=0,
            title=label,
            style={'padding': '4px 7px', 'fontSize': '14px', 'border': f'1px solid {COLOR_BORDER}',
                   'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff',
                   'transition': 'all 0.15s', 'lineHeight': '1'})

    return html.Div([

        # ── Edit/Export Bar (shown in Done mode) ──
        html.Div([
            html.Button("✏️ Edit Graph", id='gb-btn-edit', n_clicks=0, style={
                'backgroundColor': '#ffffff', 'color': COLOR_TEXT, 'border': f'1px solid {COLOR_BORDER}',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'minWidth': '140px', 'textAlign': 'center',
            }),
            html.Div([
                html.Button("📥 Export Excel", id='gb-btn-export-done', n_clicks=0, style={
                    'backgroundColor': COLOR_PRIMARY, 'color': 'white', 'border': 'none',
                    'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                    'fontWeight': 'bold', 'fontSize': '13px', 'minWidth': '120px', 'textAlign': 'center',
                }),
                dcc.Loading(html.Div(id='gb-export-excel-status', children='', style={'display': 'none'}),
                    type='circle', color=COLOR_PRIMARY, parent_style={'display': 'inline-block', 'verticalAlign': 'middle', 'marginLeft': '4px'}),
            ], style={'display': 'inline-flex', 'alignItems': 'center', 'marginLeft': '8px'}),
            html.Button("📷 Export Chart", id='gb-btn-export-chart', n_clicks=0, style={
                'backgroundColor': COLOR_PRIMARY, 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '120px', 'textAlign': 'center',
            }),
            html.Button("📋 Copy to Clipboard", id='gb-btn-clipboard', n_clicks=0, style={
                'backgroundColor': COLOR_PRIMARY, 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '160px', 'textAlign': 'center',
            }),
            html.Div(id='gb-clipboard-toast', children='', style={'display': 'none'}),
            html.Button("📷 Export PNG", id='gb-btn-export-png', n_clicks=0, style={'display': 'none'}),
            html.Button("🔗 Share Link", id='gb-btn-share', n_clicks=0, style={
                'backgroundColor': COLOR_ACCENT, 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '140px', 'textAlign': 'center',
            }),
            html.Div(id='gb-share-toast', children='', style={'display': 'none'}),
            html.Button("💾 Save Config", id='gb-btn-save-config', n_clicks=0, style={
                'backgroundColor': '#5E35B1', 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px', 'minWidth': '140px', 'textAlign': 'center',
            }),
            dcc.Dropdown(id='gb-saved-configs', options=[], value=None, placeholder='📂 Load saved config...',
                style={'display': 'inline-block', 'width': '220px', 'marginLeft': '8px', 'verticalAlign': 'middle', 'fontSize': '13px'}),
            html.Button("🗑️", id='gb-btn-delete-config', n_clicks=0, title='Delete selected config', style={
                'backgroundColor': '#e0e0e0', 'color': '#555', 'border': 'none',
                'padding': '8px 10px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '4px',
            }),
            html.Div(id='gb-config-toast', children='', style={'display': 'none'}),
        ], id='gb-edit-bar', style={'display': 'none', 'padding': '6px 0', 'marginBottom': '6px'}),

        # ════════════════════════════════════════════════
        # CHART-CENTERED LAYOUT: Variables | DropZones+Chart | Color/Size
        # ════════════════════════════════════════════════
        html.Div(id='gb-config-panel', children=[

            # ━━━ LEFT: Variable Palette ━━━
            html.Div([
                html.Div("📋 Columns", style={
                    'fontWeight': '700', 'fontSize': '12px', 'color': '#fff', 'padding': '6px 8px',
                    'background': f'linear-gradient(135deg, {COLOR_PRIMARY}, #1976D2)',
                    'borderRadius': '6px 6px 0 0', 'letterSpacing': '0.5px',
                }),
                html.Div(id='gb-variable-palette', children=[
                    html.Div("Select a product to load columns...", style={'color': '#bbb', 'fontSize': '11px', 'padding': '20px 8px', 'textAlign': 'center'})
                ], style={
                    'maxHeight': '600px', 'overflowY': 'auto', 'padding': '4px',
                    'backgroundColor': '#fafbfc', 'borderRadius': '0 0 6px 6px',
                    'border': f'1px solid {COLOR_BORDER}', 'borderTop': 'none',
                }),
            ], id='gb-palette-sidebar', style={'flex': '0 0 160px', 'minWidth': '145px'}),

            # ━━━ CENTER: Drop Zones + Chart ━━━
            html.Div([

                html.Div(id='gb-zone-group-x', children=[
                    zone_label('📐 Group X  (Column Panels)', '#7B1FA2'),
                    _dz('gb-drop-group-x', 'Drop variable for column panels...', '#7B1FA2', min_h='32px'),
                ], style={'marginBottom': '4px'}),

                # ── Middle band: Y | Chart | Y2 ──
                html.Div([
                    # Y Axis (left of chart)
                    html.Div(id='gb-zone-y', children=[
                        zone_label('📈 Y', '#005baa'),
                        _dz('gb-drop-y', 'Drop Y variables here (max 6)', '#005baa', direction='column', min_h='100%'),
                    ], style={'flex': '0 0 110px', 'display': 'flex', 'flexDirection': 'column'}),

                    # CHART (center)
                    html.Div([
                        # Chart control bar (compact icons)
                        html.Div(id='gb-chart-toolbar', children=[
                            # Chart type icons
                            html.Div([
                                html.Span("Chart Type", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#888', 'marginRight': '6px', 'whiteSpace': 'nowrap'}),
                                html.Button("⬤", id='gb-type-scatter', n_clicks=0, title='Scatter Plot',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'2px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#E3F2FD', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("📈", id='gb-type-line', n_clicks=0, title='Line Chart',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("📊", id='gb-type-bar', n_clicks=0, title='Bar Chart',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("📦", id='gb-type-box', n_clicks=0, title='Box Plot',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("📉", id='gb-type-histogram', n_clicks=0, title='Histogram',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("🎻", id='gb-type-violin', n_clicks=0, title='Violin Plot',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("◯", id='gb-type-bubble', n_clicks=0, title='Bubble Chart',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1', 'fontWeight': 'bold'}),
                                html.Button("🔥", id='gb-type-heatmap', n_clicks=0, title='Heatmap',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("🏆", id='gb-type-pareto', n_clicks=0, title='Pareto Chart',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                                html.Button("🔗", id='gb-type-correlation', n_clicks=0, title='Correlation Matrix (requires 2+ Y)',
                                    style={'padding': '5px 8px', 'fontSize': '13px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer', 'backgroundColor': '#fff', 'transition': 'all 0.15s', 'lineHeight': '1'}),
                            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '3px'}),
                            # Y Display Mode toggle (Stack Y / Overlay)
                            html.Div(id='gb-y-display-mode-container', children=[
                                html.Span("Display", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#888', 'marginRight': '4px'}),
                                dcc.RadioItems(id='gb-y-display-mode', options=[
                                    {'label': ' ▣ Overlay', 'value': 'overlay'},
                                    {'label': ' ≡ Stack Y', 'value': 'stack_y'},
                                ], value='overlay', inline=True, style={'fontSize': '10px', 'display': 'flex', 'gap': '6px'},
                                inputStyle={'marginRight': '2px'}),
                            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginLeft': '8px'}),
                            html.Div(style={'flex': '1'}),
                            # Axis Config buttons
                            html.Div([
                                html.Span("Axes", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#888', 'marginRight': '4px'}),
                                html.Button("📏 Y", id='gb-btn-axis-y', title='Y Axis Settings', n_clicks=0, style={'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700', 'backgroundColor': '#f0f4ff', 'color': '#1565C0', 'border': '1px solid #90CAF9', 'borderRadius': '4px', 'cursor': 'pointer'}),
                                html.Button("📏 X", id='gb-btn-axis-x', title='X Axis Settings', n_clicks=0, style={'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700', 'backgroundColor': '#FFF3E0', 'color': '#E65100', 'border': '1px solid #FFCC80', 'borderRadius': '4px', 'cursor': 'pointer'}),
                                html.Button("📏 Y2", id='gb-btn-axis-y2', title='Y2 Axis Settings', n_clicks=0, style={'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700', 'backgroundColor': '#FCE4EC', 'color': '#C62828', 'border': '1px solid #EF9A9A', 'borderRadius': '4px', 'cursor': 'pointer'}),
                                html.Button("🎨", id='gb-btn-style', title='Style Settings', n_clicks=0, style={'padding': '4px 7px', 'fontSize': '12px', 'fontWeight': '700', 'backgroundColor': '#F3E5F5', 'color': '#7B1FA2', 'border': '1px solid #CE93D8', 'borderRadius': '4px', 'cursor': 'pointer'}),
                                html.Button("📋", id='gb-btn-legend-mgr', title='Legend Manager: Show/Hide traces', n_clicks=0, style={'padding': '4px 7px', 'fontSize': '12px', 'fontWeight': '700', 'backgroundColor': '#E8F5E9', 'color': '#2E7D32', 'border': '1px solid #A5D6A7', 'borderRadius': '4px', 'cursor': 'pointer'}),
                            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginRight': '12px'}),
                            # Fit / Group controls
                            html.Div([
                                html.Span("Fit", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#888', 'marginRight': '4px'}),
                                html.Button("—", id='gb-fit-none', title='No Fit', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px'}),
                                html.Button("OLS", id='gb-fit-ols', title='Linear OLS', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700'}),
                                html.Button("MA", id='gb-fit-rolling', title='Moving Avg', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700'}),
                                dcc.Input(id='gb-ma-window', type='number', value=20, min=3, max=200, placeholder='MA',
                                    style={'width': '42px', 'padding': '2px 4px', 'fontSize': '10px', 'border': '1px solid #ccc', 'borderRadius': '3px', 'textAlign': 'center'}),
                                html.Button("LO", id='gb-fit-lowess', title='LOWESS', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '10px', 'fontWeight': '700'}),
                                html.Button("🔮", id='gb-fit-fcst', title='Forecast (next N points)', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px', 'fontWeight': '700'}),
                                html.Span("  ", style={'width': '8px'}),
                                html.Span("Group", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#888', 'marginRight': '4px'}),
                                html.Button("—", id='gb-dg-none', title='No grouping', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px'}),
                                html.Button("W", id='gb-dg-w', title='By Week', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px', 'fontWeight': '700'}),
                                html.Button("M", id='gb-dg-m', title='By Month', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px', 'fontWeight': '700'}),
                                html.Button("Q", id='gb-dg-q', title='By Quarter', n_clicks=0, style={**btn_style, 'padding': '4px 7px', 'fontSize': '11px', 'fontWeight': '700'}),
                            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '2px'}),
                        ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'flexWrap': 'wrap', 'gap': '4px',
                                  # zoom:0.9 shrinks just this control bar to ~90% so every option
                                  # (Chart Type / Display / Axes / Fit / Group) stays on ONE line at
                                  # 100% browser zoom. flexWrap stays 'wrap' as a graceful fallback so
                                  # it still reflows (not clips) on very narrow viewports. The chart
                                  # below is a sibling and is unaffected by this local zoom.
                                  'zoom': 0.9,
                                  'padding': '6px 10px', 'backgroundColor': '#f5f6f8', 'borderRadius': '6px 6px 0 0',
                                  'borderBottom': f'1px solid {COLOR_BORDER}'}),

                        # Dynamic Filters (collapsible, near chart)
                        html.Details([
                            html.Summary("🔍 Filters", style={
                                'cursor': 'pointer', 'fontWeight': 'bold', 'color': COLOR_PRIMARY,
                                'fontSize': '11px', 'padding': '2px 10px',
                            }),
                            html.Div([
                                html.Button("+ Add", id='gb-add-filter', style={'backgroundColor': '#17a2b8', 'color': 'white', 'border': 'none', 'padding': '3px 10px', 'borderRadius': '3px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '11px', 'marginBottom': '4px'}),
                                html.Div(id='gb-filter-container', children=[]),
                            ], style={'padding': '4px 10px'}),
                        ], open=False, id='gb-filter-section', style={
                            'backgroundColor': '#fafbfc', 'borderBottom': f'1px solid {COLOR_BORDER}', 'fontSize': '12px'
                        }),

                        # Graph (user-resizable wrapper — both width & height, multiple drags)
                        html.Div([
                            dcc.Loading(type="circle", color=COLOR_PRIMARY, parent_style={'height': '100%', 'width': '100%'}, children=[
                                dcc.Graph(id='gb-graph', config={'displayModeBar': True, 'responsive': True},
                                          style={'height': '100%', 'width': '100%'})
                            ]),
                        ], id='gb-graph-resizer', style={
                            'height': '480px', 'minHeight': '280px',
                            'width': '100%', 'minWidth': '420px',
                            'resize': 'both', 'overflow': 'auto',
                            'border': f'1px dashed {COLOR_BORDER}', 'borderRadius': '4px',
                            'position': 'relative',
                        }),
                    ], style={'flex': '1', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '6px',
                              'backgroundColor': '#fff', 'overflow': 'auto', 'minWidth': '0'}),

                    # Y2 Axis (secondary, right-side)
                    html.Div(id='gb-zone-y2', children=[
                        zone_label('📊 Y2 (Right)', '#E65100'),
                        _dz('gb-drop-y2', 'Y2 axis', '#E65100', direction='column', min_h='100%'),
                    ], style={'flex': '0 0 90px', 'display': 'flex', 'flexDirection': 'column'}),
                ], style={'display': 'flex', 'gap': '4px', 'marginBottom': '4px', 'minHeight': '500px'}),

                html.Div(id='gb-zone-x', children=[
                    zone_label('🏷️ X Axis', '#005baa'),
                    _dz('gb-drop-x', 'Drop X variable here (required)', '#005baa', min_h='34px'),
                ], style={'marginBottom': '4px'}),

                # ── Group Y (bottom) ──
                html.Div(id='gb-zone-group-y', children=[
                    zone_label('📐 Group Y  (Row Panels)', '#7B1FA2'),
                    _dz('gb-drop-group-y', 'Drop variable for row panels...', '#7B1FA2', min_h='32px'),
                ], style={'marginBottom': '8px'}),

            ], style={'flex': '1', 'minWidth': '0'}),

            # ━━━ RIGHT: Color + Size ━━━
            html.Div(id='gb-right-panel', children=[
                zone_label('🎨 Color', '#1565C0'),
                _dz('gb-drop-color', 'Drop color variable', '#1565C0', direction='column', min_h='60px', min_w='80px'),
                html.Div(style={'height': '8px'}),
                zone_label('📏 Size', '#2E7D32'),
                _dz('gb-drop-size', 'Drop size variable', '#2E7D32', direction='column', min_h='60px', min_w='80px'),
            ], style={'flex': '0 0 100px', 'paddingTop': '38px'}),

        ], style={'display': 'flex', 'gap': '8px', 'marginBottom': '10px', 'alignItems': 'flex-start'}),

        # ════════════════════════════════════════════════
        # BOTTOM CONTROLS — 3 organised rows:
        # Row 1: ⏱ Time presets +  Custom date range +  Levels
        # Row 2:  Spec
        # Row 3:  Alarms  (auto-hides for non scatter/line)
        # ════════════════════════════════════════════════
        html.Div(id='gb-controls-bar', children=[
            # ── Row 1: Time ──
            html.Div([
                # Quick presets
                html.Div([
                    html.Label("⏱️ Range:", style={'fontWeight': 'bold', 'fontSize': '11px', 'color': '#555', 'marginRight': '4px', 'whiteSpace': 'nowrap'}),
                    html.Button("All", id="gb-btn-all", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("2Y", id="gb-btn-2y", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("1Y", id="gb-btn-1y", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("6M", id="gb-btn-6m", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("3M", id="gb-btn-3m", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("1M", id="gb-btn-1m", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                    html.Button("7D", id="gb-btn-7d", n_clicks=0, style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'gap': '2px', 'flexWrap': 'wrap',
                          'backgroundColor': '#f8f9fa', 'borderRadius': '6px', 'padding': '3px 8px', 'border': f'1px solid {COLOR_BORDER}'}),

                # Custom date range picker
                html.Div([
                    html.Label("📅 Custom:", style={'fontWeight': 'bold', 'fontSize': '11px', 'color': '#555', 'marginRight': '4px', 'whiteSpace': 'nowrap'}),
                    dcc.DatePickerRange(id='gb-date-picker-range', display_format='YYYY-MM-DD',
                                        clearable=True, with_portal=False,
                                        style={'fontSize': '11px'}),
                    html.Button("✕", id='gb-btn-clear-range', n_clicks=0, title='Clear custom range',
                                style={**btn_style, 'padding': '3px 8px', 'fontSize': '11px', 'marginLeft': '4px',
                                       'color': '#999'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'gap': '2px', 'flexWrap': 'wrap',
                          'backgroundColor': '#f0f7ff', 'borderRadius': '6px', 'padding': '3px 8px', 'border': '1px solid #cce4ff'}),

                # Spacer pushes Levels to the right
                html.Div(style={'flex': '1'}),

                # Group Levels (small, right-aligned)
                html.Div([
                    html.Label("🔢 Levels:", style={'fontSize': '11px', 'fontWeight': '700', 'color': '#7B1FA2', 'marginRight': '4px', 'whiteSpace': 'nowrap'}),
                    dcc.Input(id='gb-group-levels', type='number', value=10, min=2, max=20, step=1,
                              style={'width': '50px', 'fontSize': '11px', 'padding': '3px 4px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'gap': '3px',
                          'backgroundColor': '#faf5ff', 'borderRadius': '6px', 'padding': '3px 8px', 'border': '1px solid #e5d4f0'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'flexWrap': 'wrap', 'marginBottom': '6px'}),

            # ── Row 2: Spec ──
            html.Div(id='gb-spec-toggles-container', children=[
                html.Label("📊 Spec:", style={'fontWeight': 'bold', 'fontSize': '11px', 'color': '#555', 'marginRight': '3px'}),
                dcc.Checklist(id='gb-spec-checklist', options=[
                    {'label': '📏CL', 'value': 'cl'}, {'label': '⚠️SL', 'value': 'sl'},
                    {'label': '📍Mean', 'value': 'mean'},
                    {'label': '📐3σ₁', 'value': '3s1y'}, {'label': '📐3σ₂', 'value': '3s2y'},
                    {'label': '📊6σ₁', 'value': '6s1y'}, {'label': '📊6σ₂', 'value': '6s2y'},
                ], value=[], inline=True,
                inputStyle={'marginRight': '2px', 'marginLeft': '5px'},
                labelStyle={'fontSize': '11px', 'cursor': 'pointer', 'color': '#555', 'fontWeight': '500'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap',
                      'backgroundColor': '#f8f9fa', 'borderRadius': '6px', 'padding': '4px 8px',
                      'border': f'1px solid {COLOR_BORDER}', 'marginBottom': '6px'}),

            # ── Alarms (hidden — no detection engine in standalone mode) ──
            html.Div(id='gb-legend-section', children=[
                dcc.Checklist(id='gb-legend-checklist', options=[], value=[], inline=True),
            ], style={'display': 'none'}),
        ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '0',
                  'padding': '8px 12px', 'backgroundColor': '#fafbfc', 'borderRadius': '4px',
                  'border': f'1px solid {COLOR_BORDER}', 'marginBottom': '10px'}),

        # Build + Actions row
        html.Div(id='gb-action-bar', children=[
            html.Div(style={'flex': '1'}),
            html.Label("Max Series:", style={'fontWeight': '600', 'fontSize': '13px', 'color': COLOR_TEXT, 'marginRight': '6px'}),
            dcc.Dropdown(id='gb-max-series', options=[
                {'label': '10', 'value': 10}, {'label': '20', 'value': 20},
                {'label': '50', 'value': 50}, {'label': 'Unlimited', 'value': 0}
            ], value=20, clearable=False, style={'width': '120px', 'fontSize': '13px', 'marginRight': '10px'}),
            html.Button("🔄 Reset", id='gb-btn-reset-all', n_clicks=0, style={
                'backgroundColor': '#ffffff', 'color': COLOR_TEXT, 'border': f'1px solid {COLOR_BORDER}',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px',
            }),
            html.Button("🔨 Build Graph", id='gb-btn-build', style={
                'backgroundColor': COLOR_PRIMARY, 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'boxShadow': 'none',
                'minWidth': '140px', 'textAlign': 'center',
            }),
            html.Button("✅ Done", id='gb-btn-done', n_clicks=0, style={
                'backgroundColor': COLOR_ACCENT, 'color': 'white', 'border': 'none',
                'padding': '8px 16px', 'borderRadius': '4px', 'cursor': 'pointer',
                'fontWeight': 'bold', 'fontSize': '13px', 'marginLeft': '8px',
                'minWidth': '140px', 'textAlign': 'center',
            }),
            html.Button("Export", id='gb-btn-export', style={'display': 'none'}),
            dcc.Download(id="gb-download-data"),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '10px'}),

        # ── Data Preview Table ──
        html.Div(id='gb-data-preview-container', children=[
            html.Details([
                html.Summary("📋 Data Preview Table", style={
                    'cursor': 'pointer', 'fontWeight': 'bold', 'color': COLOR_PRIMARY, 'fontSize': '14px', 'padding': '6px 0'
                }),
                html.Div([
                    dash_table.DataTable(
                        id='gb-data-table', columns=[], data=[], page_size=15,
                        style_table={'overflowX': 'auto', 'width': '100%'},
                        style_header={'backgroundColor': '#f8fafc', 'color': COLOR_PRIMARY, 'fontWeight': 'bold', 'borderBottom': f'2px solid {COLOR_PRIMARY}', 'textAlign': 'center', 'padding': '8px'},
                        style_data={'backgroundColor': '#fff', 'color': COLOR_TEXT, 'borderBottom': f'1px solid {COLOR_BORDER}', 'padding': '6px'},
                        style_cell={'textAlign': 'center', 'fontSize': '12px', 'maxWidth': '180px', 'whiteSpace': 'normal'},
                        filter_action='native', sort_action='native'
                    )
                ], style={'marginTop': '8px'})
            ], id='gb-data-preview-details', open=False)
        ], style={**card_style, 'padding': '12px'}),

        # ── Hidden Dropdowns (synced by JS, consumed by callbacks) ──
        html.Div([
            dcc.Dropdown(id='gb-x-axis', options=[], value=None, clearable=False),
            dcc.Dropdown(id='gb-y-axis', options=[], value=[], multi=True),
            dcc.Dropdown(id='gb-y2-axis', options=[], value=[], multi=True),
            dcc.Dropdown(id='gb-color', options=[], value=None),
            dcc.Dropdown(id='gb-size', options=[], value=None),
            dcc.Dropdown(id='gb-group-x', options=[], value=None),
            dcc.Dropdown(id='gb-group-y', options=[], value=None),
            dcc.Dropdown(id='gb-chart-type', options=[
                {'label': 'scatter', 'value': 'scatter'}, {'label': 'line', 'value': 'line'},
                {'label': 'bar', 'value': 'bar'}, {'label': 'box', 'value': 'box'},
                {'label': 'histogram', 'value': 'histogram'}, {'label': 'violin', 'value': 'violin'},
                {'label': 'bubble', 'value': 'bubble'}, {'label': 'heatmap', 'value': 'heatmap'},
                {'label': 'correlation', 'value': 'correlation'},
            ], value='scatter', clearable=False),
            dcc.Dropdown(id='gb-trendline', options=[
                {'label': 'none', 'value': 'none'}, {'label': 'ols', 'value': 'ols'},
                {'label': 'rolling', 'value': 'rolling'}, {'label': 'lowess', 'value': 'lowess'},
                {'label': 'forecast', 'value': 'forecast'},
            ], value='none', clearable=False),
            dcc.Dropdown(id='gb-date-group', options=[
                {'label': 'none', 'value': 'none'}, {'label': 'W', 'value': 'W'},
                {'label': 'M', 'value': 'M'}, {'label': 'Q', 'value': 'Q'},
            ], value='none', clearable=False),
        ], style={'display': 'none'}),

        # ── Hidden Stores ──
        dcc.Store(id='gb-filter-count', data=0),
        dcc.Store(id='gb-built-data', data=[]),
        # single rebuild-trigger signal. URL share / style+axis Apply / time preset all
        # bump THIS instead of gb-btn-build.n_clicks → cleaner topology, less abuse of click count.
        dcc.Store(id='gb-rebuild-signal', data=0),
        dcc.Store(id='gb-zone-sync', data={}),
        dcc.Store(id='gb-time-range', data={'preset': '2Y'}),
        dcc.Store(id='gb-view-mode', data='edit'),
        dcc.Store(id='gb-export-fname-stem', data='GraphBuilder_Chart'),
        # Lightweight {trace_name: {v, l}} snapshot of user legend toggles.
        # Avoids round-tripping the full figure (MB-sized) on every Build.
        dcc.Store(id='gb-trace-state-store', data={}),

        # ── Legend Manager ──
        dcc.Store(id='gb-legend-traces-store', data=[]),
        html.Div(id='gb-legend-modal-backdrop', children=[
            html.Div([
                html.Div([
                    html.H4('📋 Legend Manager', style={'margin': '0', 'color': '#2E7D32'}),
                    html.Div([
                        html.Button('✅ Select All', id='gb-legend-select-all', n_clicks=0, style={'padding': '4px 10px', 'fontSize': '11px', 'fontWeight': '700', 'backgroundColor': '#E8F5E9', 'color': '#2E7D32', 'border': '1px solid #A5D6A7', 'borderRadius': '4px', 'cursor': 'pointer', 'marginRight': '4px'}),
                        html.Button('☐ Unselect All', id='gb-legend-deselect-all', n_clicks=0, style={'padding': '4px 10px', 'fontSize': '11px', 'fontWeight': '700', 'backgroundColor': '#FFEBEE', 'color': '#C62828', 'border': '1px solid #EF9A9A', 'borderRadius': '4px', 'cursor': 'pointer', 'marginRight': '12px'}),
                        html.Button('×', id='gb-legend-modal-close', n_clicks=0, style={'background': 'none', 'border': 'none', 'fontSize': '22px', 'cursor': 'pointer', 'color': '#999'}),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'borderBottom': f'1px solid {COLOR_BORDER}', 'paddingBottom': '10px', 'marginBottom': '10px'}),
                
                html.Div([
                    html.Div([
                        html.Label('Position:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Dropdown(id='gb-style-legend-pos', options=[
                            {'label': '⬆ Top', 'value': 'top'}, {'label': '⬇ Bottom', 'value': 'bottom'},
                            {'label': '➡ Right', 'value': 'right'},
                        ], value='bottom', clearable=False, style={'flex': '1', 'fontSize': '12px'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'width': '180px'}),
                    html.Div([
                        html.Label('Font Size:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '65px'}),
                        html.Div(dcc.Slider(id='gb-style-legend-size', min=8, max=16, step=1, value=11, marks={8: '8', 11: '11', 14: '14', 16: '16'}, tooltip={'placement': 'bottom', 'always_visible': False}), style={'flex': '1', 'padding': '0 15px'}),
                    ], style={'display': 'flex', 'flex': '1', 'marginLeft': '10px', 'alignItems': 'center'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px', 'paddingBottom': '10px', 'borderBottom': f'1px solid {COLOR_BORDER}'}),

                html.Div(id='gb-legend-items-container', children=[], style={
                    'maxHeight': '400px', 'overflowY': 'auto', 'display': 'grid',
                    'gridTemplateColumns': 'repeat(auto-fill, minmax(260px, 1fr))', 'gap': '6px',
                }),
            ], style={'backgroundColor': 'white', 'borderRadius': '10px', 'padding': '20px', 'width': '700px', 'maxWidth': '95vw',
                      'boxShadow': '0 8px 32px rgba(0,0,0,0.3)', 'maxHeight': '80vh', 'overflow': 'auto'}),
        ], style={'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%',
                  'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'}),

        # ── Axis Config Modal (JMP-style) ──
        html.Div(id='gb-axis-modal-backdrop', children=[
            html.Div([
                html.Div([
                    html.H4(id='gb-axis-modal-title', children='📏 Axis Settings', style={'margin': '0', 'color': COLOR_PRIMARY}),
                    html.Button('×', id='gb-axis-modal-close', n_clicks=0, style={'background': 'none', 'border': 'none', 'fontSize': '22px', 'cursor': 'pointer', 'color': '#999'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'borderBottom': f'1px solid {COLOR_BORDER}', 'paddingBottom': '10px', 'marginBottom': '15px'}),
                # ── Title Editing ──
                html.Div([
                    html.Label('📝 Chart Title:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Input(id='gb-custom-chart-title', type='text', placeholder='Auto-generated (leave blank)', style={'width': '100%', 'padding': '6px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'marginTop': '4px', 'boxSizing': 'border-box'}),
                ], style={'marginBottom': '12px'}),
                html.Div([
                    html.Label(id='gb-axis-title-label', children='🏷️ Axis Title:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Input(id='gb-axis-custom-title', type='text', placeholder='Auto (column name)', style={'width': '100%', 'padding': '6px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'marginTop': '4px', 'boxSizing': 'border-box'}),
                ], style={'marginBottom': '12px', 'paddingBottom': '12px', 'borderBottom': f'1px solid {COLOR_BORDER}'}),
                # Tick Increment
                html.Div([
                    html.Label('Tick Increment (dtick):', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Input(id='gb-axis-dtick', type='number', placeholder='Auto', style={'width': '100%', 'padding': '6px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Number of Ticks
                html.Div([
                    html.Label('Max Ticks (nticks):', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Input(id='gb-axis-nticks', type='number', value=10, min=2, max=50, style={'width': '100%', 'padding': '6px 8px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Number Format
                html.Div([
                    html.Label('Number Format:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Dropdown(id='gb-axis-format', options=[
                        {'label': 'Auto', 'value': ''},
                        {'label': '0.1 (.1f)', 'value': '.1f'},
                        {'label': '0.01 (.2f)', 'value': '.2f'},
                        {'label': '0.001 (.3f)', 'value': '.3f'},
                        {'label': 'Integer (d)', 'value': 'd'},
                        {'label': 'Percent (%)', 'value': '.1%'},
                        {'label': 'Scientific (.2e)', 'value': '.2e'},
                    ], value='', clearable=False, style={'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Grid Line Style
                html.Div([
                    html.Label('Grid Line Style:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    dcc.Dropdown(id='gb-axis-grid-style', options=[
                        {'label': 'Solid', 'value': 'solid'},
                        {'label': 'Dash', 'value': 'dash'},
                        {'label': 'Dot', 'value': 'dot'},
                        {'label': 'None (hide)', 'value': 'none'},
                    ], value='solid', clearable=False, style={'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Tick Font Size
                html.Div([
                    html.Label('🔤 Tick Font Size:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    html.Div(dcc.Slider(id='gb-axis-tick-fontsize', min=8, max=16, step=1, value=11,
                                        marks={8: '8', 10: '10', 11: '11', 13: '13', 16: '16'},
                                        tooltip={'placement': 'bottom', 'always_visible': False}),
                             style={'padding': '0 10px', 'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Axis Title Font Size
                html.Div([
                    html.Label('🔠 Axis Title Font Size:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT}),
                    html.Div(dcc.Slider(id='gb-axis-title-fontsize', min=10, max=24, step=1, value=14,
                                        marks={10: '10', 14: '14', 18: '18', 24: '24'},
                                        tooltip={'placement': 'bottom', 'always_visible': False}),
                             style={'padding': '0 10px', 'marginTop': '4px'}),
                ], style={'marginBottom': '12px'}),
                # Caption Box toggle
                html.Div([
                    dcc.Checklist(id='gb-show-caption', options=[
                        {'label': ' 📊 Show Statistics Caption Box', 'value': 'show'}
                    ], value=[], inline=True,
                    inputStyle={'marginRight': '6px'},
                    labelStyle={'fontSize': '13px', 'fontWeight': '600', 'color': COLOR_PRIMARY, 'cursor': 'pointer'}),
                ], style={'marginBottom': '12px', 'paddingTop': '8px', 'borderTop': f'1px solid {COLOR_BORDER}'}),
                # Reference Lines
                html.Div([
                    html.Label('➕ Add Reference Line:', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': COLOR_TEXT, 'marginBottom': '6px'}),
                    html.Div([
                        dcc.Input(id='gb-ref-line-value', type='number', placeholder='Value', style={'width': '80px', 'padding': '4px 6px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'fontSize': '12px'}),
                        dcc.Input(id='gb-ref-line-label', type='text', placeholder='Label', style={'width': '80px', 'padding': '4px 6px', 'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'fontSize': '12px'}),
                        dcc.Dropdown(id='gb-ref-line-color', options=[
                            {'label': '🟥 Red', 'value': '#e53935'}, {'label': '🟦 Blue', 'value': '#1E88E5'},
                            {'label': '🟩 Green', 'value': '#43A047'}, {'label': '🟨 Orange', 'value': '#FB8C00'},
                            {'label': '⬛ Black', 'value': '#333333'},
                        ], value='#e53935', clearable=False, style={'width': '120px', 'fontSize': '12px'}),
                        dcc.Dropdown(id='gb-ref-line-style', options=[
                            {'label': 'Dash', 'value': 'dash'}, {'label': 'Solid', 'value': 'solid'},
                            {'label': 'Dot', 'value': 'dot'}, {'label': 'DashDot', 'value': 'dashdot'},
                        ], value='dash', clearable=False, style={'width': '100px', 'fontSize': '12px'}),
                        html.Button('➕ Add', id='gb-ref-line-add', n_clicks=0, style={'backgroundColor': '#43A047', 'color': 'white', 'border': 'none', 'padding': '4px 10px', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '12px'}),
                    ], style={'display': 'flex', 'gap': '6px', 'alignItems': 'center', 'flexWrap': 'wrap'}),
                    html.Div(id='gb-ref-lines-list', children=[], style={'marginTop': '8px'}),
                ], style={'marginBottom': '15px'}),
                # Apply button
                html.Div([
                    html.Button('✅ Apply Settings', id='gb-axis-modal-apply', n_clicks=0, style={
                        'backgroundColor': COLOR_PRIMARY, 'color': 'white', 'border': 'none',
                        'padding': '8px 20px', 'borderRadius': '6px', 'cursor': 'pointer',
                        'fontWeight': 'bold', 'fontSize': '13px', 'width': '100%'
                    }),
                ], style={'marginTop': '10px'}),
            ], style={
                'backgroundColor': '#fff', 'borderRadius': '10px', 'padding': '20px', 'width': '380px',
                'boxShadow': '0 8px 30px rgba(0,0,0,0.2)', 'maxHeight': '85vh', 'overflowY': 'auto'
            }),
        ], style={
            'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%',
            'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'
        }),
        dcc.Store(id='gb-axis-config', data={
            'which': 'y',
            'x': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'y': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'y2': {'dtick': None, 'nticks': 10, 'format': '', 'grid_style': 'solid', 'title': '', 'tick_fontsize': 11, 'title_fontsize': 14},
            'chart_title': '', 'show_caption': False
        }),
        dcc.Store(id='gb-ref-lines-store', data=[]),
        dcc.Store(id='gb-url-params', data=None),
        dcc.Store(id='gb-filter-encoded', data=''),  # Server-maintained base64 of current filters; consumed by Share/Save
        dcc.Store(id='gb-lgnd-pending', data=None),  # Legend visibility state pending apply after build
        # Style config store
        dcc.Store(id='gb-style-config', data={
            'marker_size': 6, 'marker_opacity': 0.7, 'marker_symbol': 'auto',
            'line_width': 1.5, 'line_dash': 'solid',
            'legend_pos': 'bottom', 'legend_size': 11,
            'palette': 'Plotly'
        }),
        # ── Style Settings Modal ──
        html.Div(id='gb-style-modal-backdrop', children=[
            html.Div([
                html.Div([
                    html.H4('🎨 Style Settings', style={'margin': '0', 'color': '#7B1FA2'}),
                    html.Button('×', id='gb-style-modal-close', n_clicks=0, style={'background': 'none', 'border': 'none', 'fontSize': '22px', 'cursor': 'pointer', 'color': '#999'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'borderBottom': f'1px solid {COLOR_BORDER}', 'paddingBottom': '10px', 'marginBottom': '15px'}),
                # ── Marker Section ──
                html.Div([
                    html.Label('● Marker', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': '#7B1FA2', 'marginBottom': '8px', 'display': 'block'}),
                    html.Div([
                        html.Label('Size:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Slider(id='gb-style-marker-size', min=2, max=15, step=1, value=6, marks={2: '2', 5: '5', 8: '8', 11: '11', 15: '15'}, tooltip={'placement': 'bottom', 'always_visible': False}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '8px'}),
                    html.Div([
                        html.Label('Opacity:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Slider(id='gb-style-marker-opacity', min=0.1, max=1.0, step=0.05, value=0.7, marks={0.1: '0.1', 0.5: '0.5', 1.0: '1.0'}, tooltip={'placement': 'bottom', 'always_visible': False}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '8px'}),
                    html.Div([
                        html.Label('Symbol:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Dropdown(id='gb-style-marker-symbol', options=[
                            {'label': 'Auto (vary by series)', 'value': 'auto'},
                            {'label': '● Circle', 'value': 'circle'},
                            {'label': '■ Square', 'value': 'square'},
                            {'label': '◆ Diamond', 'value': 'diamond'},
                            {'label': '✚ Cross', 'value': 'cross'},
                            {'label': '✕ X', 'value': 'x'},
                            {'label': '▲ Triangle', 'value': 'triangle-up'},
                        ], value='auto', clearable=False, style={'flex': '1', 'fontSize': '12px'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}),
                ], style={'marginBottom': '15px', 'paddingBottom': '12px', 'borderBottom': f'1px solid {COLOR_BORDER}'}),
                # ── Line Section ──
                html.Div([
                    html.Label('╱ Line', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': '#7B1FA2', 'marginBottom': '8px', 'display': 'block'}),
                    html.Div([
                        html.Label('Width:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Slider(id='gb-style-line-width', min=0.5, max=5, step=0.5, value=1.5, marks={0.5: '0.5', 1.5: '1.5', 3: '3', 5: '5'}, tooltip={'placement': 'bottom', 'always_visible': False}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '8px'}),
                    html.Div([
                        html.Label('Dash:', style={'fontSize': '12px', 'fontWeight': '600', 'color': COLOR_TEXT, 'width': '55px'}),
                        dcc.Dropdown(id='gb-style-line-dash', options=[
                            {'label': '── Solid', 'value': 'solid'},
                            {'label': '- - Dash', 'value': 'dash'},
                            {'label': '··· Dot', 'value': 'dot'},
                            {'label': '-·- DashDot', 'value': 'dashdot'},
                        ], value='solid', clearable=False, style={'flex': '1', 'fontSize': '12px'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}),
                ], style={'marginBottom': '15px', 'paddingBottom': '12px', 'borderBottom': f'1px solid {COLOR_BORDER}'}),

                # ── Color Palette Section ──
                html.Div([
                    html.Label('🎨 Color Palette', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': '#7B1FA2', 'marginBottom': '8px', 'display': 'block'}),
                    dcc.Dropdown(id='gb-style-palette', options=[
                        {'label': 'Plotly (default)', 'value': 'Plotly'},
                        {'label': 'D3', 'value': 'D3'},
                        {'label': 'Set1', 'value': 'Set1'},
                        {'label': 'Set2', 'value': 'Set2'},
                        {'label': 'Pastel1', 'value': 'Pastel1'},
                        {'label': 'Dark2', 'value': 'Dark2'},
                        {'label': 'Safe', 'value': 'Safe'},
                    ], value='Plotly', clearable=False, style={'fontSize': '12px'}),
                ], id='gb-palette-section', style={'marginBottom': '15px', 'paddingBottom': '12px', 'borderBottom': f'1px solid {COLOR_BORDER}'}),
                # ── Per-Series Overrides ──
                html.Div([
                    html.Label('🔧 Per-Series Overrides', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': '#7B1FA2', 'marginBottom': '8px', 'display': 'block'}),
                    html.Div([
                        html.Div(style={'display': 'flex', 'gap': '6px', 'alignItems': 'center', 'marginBottom': '4px', 'fontSize': '11px', 'color': '#888', 'fontWeight': '600'}, children=[
                            html.Span('Series', style={'width': '90px'}),
                            html.Span('Color', style={'width': '120px'}),
                            html.Span('Symbol', style={'width': '110px'}),
                            html.Span('Dash', style={'width': '100px'}),
                        ]),
                    ] + [
                        html.Div(id=f'gb-ss-row-{i}', style={'display': 'none', 'gap': '6px', 'alignItems': 'center', 'marginBottom': '5px'}, children=[
                            html.Span(id=f'gb-ss-{i}-label', children=f'Series {i+1}', style={'fontSize': '12px', 'fontWeight': '500', 'color': COLOR_TEXT, 'width': '90px', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap'}),
                            dcc.Dropdown(id=f'gb-ss-{i}-color',
                                         options=[
                                             {'label': '— default', 'value': ''},
                                             {'label': '🔴 Red', 'value': '#E53935'},
                                             {'label': '🔵 Blue', 'value': '#1E88E5'},
                                             {'label': '🟢 Green', 'value': '#43A047'},
                                             {'label': '🟠 Orange', 'value': '#FB8C00'},
                                             {'label': '🟣 Purple', 'value': '#8E24AA'},
                                             {'label': '🟡 Gold', 'value': '#FDD835'},
                                             {'label': '⬛ Black', 'value': '#212121'},
                                             {'label': '🩵 Cyan', 'value': '#00ACC1'},
                                             {'label': '🩷 Pink', 'value': '#D81B60'},
                                             {'label': '🟤 Brown', 'value': '#6D4C41'},
                                             {'label': '💚 Teal', 'value': '#00897B'},
                                             {'label': '🧡 Coral', 'value': '#FF7043'},
                                         ],
                                         value='', clearable=False, style={'width': '120px', 'fontSize': '11px'}),
                            dcc.Dropdown(id=f'gb-ss-{i}-symbol',
                                         options=[{'label': s, 'value': s} for s in ['auto', 'circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'star']],
                                         value='auto', clearable=False, style={'width': '110px', 'fontSize': '11px'}),
                            dcc.Dropdown(id=f'gb-ss-{i}-dash',
                                         options=[{'label': '— auto', 'value': 'auto'}, {'label': '── solid', 'value': 'solid'}, {'label': '- - dash', 'value': 'dash'}, {'label': '··· dot', 'value': 'dot'}, {'label': '-·- dashdot', 'value': 'dashdot'}, {'label': '— long', 'value': 'longdash'}],
                                         value='auto', clearable=False, style={'width': '100px', 'fontSize': '11px'}),
                        ]) for i in range(6)
                    ], style={'marginBottom': '4px'}),
                ], style={'marginBottom': '15px'}),
                # Apply button
                html.Div([
                    html.Button('✅ Apply Style', id='gb-style-modal-apply', n_clicks=0, style={
                        'backgroundColor': '#7B1FA2', 'color': 'white', 'border': 'none',
                        'padding': '8px 20px', 'borderRadius': '6px', 'cursor': 'pointer',
                        'fontWeight': 'bold', 'fontSize': '13px', 'width': '100%'
                    }),
                ], style={'marginTop': '10px'}),
            ], style={
                'backgroundColor': '#fff', 'borderRadius': '10px', 'padding': '20px', 'width': '380px',
                'boxShadow': '0 8px 30px rgba(0,0,0,0.2)', 'maxHeight': '85vh', 'overflowY': 'auto'
            }),
        ], style={
            'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%',
            'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '9999', 'justifyContent': 'center', 'alignItems': 'center'
        }),

    ], id='page-graph-builder', style={'padding': '10px 2% 0 2%'})
