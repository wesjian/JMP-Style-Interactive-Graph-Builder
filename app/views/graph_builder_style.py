"""Shared style constants for the Graph Builder page (layout + callbacks)."""
from app.core.constants import COLOR_PRIMARY

COLOR_BG = "#F8F9FA"
COLOR_TEXT = "#333333"
COLOR_BORDER = "#E0E0E0"

btn_style = {
    'margin': '2px', 'padding': '6px 12px', 'backgroundColor': '#ffffff',
    'border': f'1px solid {COLOR_BORDER}', 'borderRadius': '4px', 'cursor': 'pointer',
    'fontSize': '13px', 'transition': 'all 0.1s ease', 'color': COLOR_TEXT
}

card_style = {
    'backgroundColor': '#ffffff', 'padding': '24px', 'borderRadius': '4px',
    'boxShadow': 'none', 'marginBottom': '24px',
    'border': f'1px solid {COLOR_BORDER}', 'boxSizing': 'border-box', 'width': '100%'
}

section_header = {
    'color': COLOR_PRIMARY, 'borderBottom': '2px solid #eee', 'paddingBottom': '5px',
    'marginBottom': '12px', 'marginTop': '0', 'fontWeight': 'bold', 'fontSize': '15px'
}
