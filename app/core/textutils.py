from datetime import datetime
import numpy as np
import pandas as pd


def get_param_value(df_params, key_list, default_val=None):
    df_params.iloc[:, 0] = df_params.iloc[:, 0].astype(str).str.strip().str.lower()
    for key in key_list:
        match = df_params[df_params.iloc[:, 0] == key.lower()]
        if not match.empty:
            val = match.iloc[0, 1]
            if pd.isna(val) or str(val).strip().upper() == 'NULL' or str(val).strip() == '': return default_val
            return val
    return default_val

def get_ratio(target_mode, source_array):
    if pd.isna(target_mode) or len(source_array) == 0: return np.nan
    return np.count_nonzero(source_array == target_mode) / len(source_array)

def get_safe_name(name):
    if pd.isna(name): return "Unknown"
    return "".join([c if c not in '\\/*?:"<>|' else '_' for c in str(name)])

def build_date_mask(df, start_date_str, end_date_str, date_col='製造日期'):
    mask = pd.Series(True, index=df.index)
    if start_date_str: mask &= df[date_col] >= pd.Timestamp(start_date_str)
    if end_date_str: mask &= df[date_col] <= pd.Timestamp(end_date_str) + pd.Timedelta(days=1, seconds=-1)
    return mask

def get_filename_template(user_perms):
    """Read def_fname_* from user_perms; returns one of 'simple' / 'dated' / 'full'."""
    for p in (user_perms or []):
        if isinstance(p, str) and p.startswith('def_fname_'):
            return p.replace('def_fname_', '') or 'dated'
    return 'dated'

def build_export_filename(template, group, chart, extension, role=None):
    """Compose export filename per template.
        simple: <group>_<chart>.<ext>
        dated:  <group>_<chart>_<YYYYMMDD>.<ext>
        full:   <role>_<group>_<chart>_<YYYYMMDD_HHMMSS>.<ext>
    Any None/empty component is skipped to keep filenames clean.
    """
    import datetime as _dt
    g = get_safe_name(group) if group else ''
    ch = get_safe_name(chart) if chart else ''
    rl = get_safe_name(role) if role else ''
    parts = []
    if template == 'full':
        if rl: parts.append(rl)
        if g: parts.append(g)
        if ch: parts.append(ch)
        parts.append(_dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
    elif template == 'simple':
        if g: parts.append(g)
        if ch: parts.append(ch)
    else:  # dated (default)
        if g: parts.append(g)
        if ch: parts.append(ch)
        parts.append(_dt.datetime.now().strftime('%Y%m%d'))
    base = '_'.join([p for p in parts if p]) or 'export'
    ext = extension.lstrip('.') if extension else 'bin'
    return f"{base}.{ext}"
