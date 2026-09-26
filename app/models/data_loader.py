# ==========================================
# Data Loader
# ==========================================
# Loads CSV / Excel / Parquet files. Returns a tuple
# (df_stat, df_7d, sym_map, df_chart_config,
# df_action, df_variable_info, round_map).
# The Graph Builder only really needs df_stat and sym_map.

import os
import glob
import logging
import pandas as pd
import numpy as np
from collections import OrderedDict

logger = logging.getLogger('JMP-Interactive-GraphBuilder')

# ── In-memory file cache ──
_FILE_CACHE: OrderedDict = OrderedDict()
_MAX_CACHE = 20


def _empty_result():
    """Return the 7-tuple stub that callers unpack."""
    return pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}


def load_file(file_path):
    """Load a single data file (CSV / Excel / Parquet) into a DataFrame.

    Returns (df, filename_without_ext).
    """
    ext = os.path.splitext(file_path)[1].lower()
    name = os.path.splitext(os.path.basename(file_path))[0]
    if ext in ('.csv', '.tsv'):
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    elif ext in ('.xlsx', '.xls', '.xlsm'):
        df = pd.read_excel(file_path, engine='openpyxl')
    elif ext in ('.parquet', '.pq'):
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
    return df, name


def discover_files(data_dir):
    """Scan a directory for loadable data files. Returns list of (display_name, abs_path)."""
    results = []
    for ext in ('*.csv', '*.xlsx', '*.xls', '*.xlsm', '*.parquet', '*.pq', '*.tsv'):
        for fp in sorted(glob.glob(os.path.join(data_dir, ext))):
            name = os.path.splitext(os.path.basename(fp))[0]
            results.append((name, fp))
    return results


def load_db_data(group_name, data_dir, rule_config=None):
    """Load data for the given group.

    `group_name` is the filename (without extension) that was selected in the UI.
    `data_dir` is the directory containing the data files.
    `rule_config` is ignored in standalone mode.

    Returns the same 7-tuple:
        (df_stat, df_7d, sym_map, df_chart_config, df_action, df_variable_info, round_map)
    """
    if not group_name:
        return _empty_result()

    # Check cache
    cache_key = group_name
    if cache_key in _FILE_CACHE:
        _FILE_CACHE.move_to_end(cache_key)
        return _FILE_CACHE[cache_key]

    # Find the file
    candidates = discover_files(data_dir)
    file_path = None
    for name, fp in candidates:
        if name == group_name:
            file_path = fp
            break
    if file_path is None:
        logger.warning(f"File not found for group: {group_name}")
        return _empty_result()

    try:
        df, _ = load_file(file_path)
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return _empty_result()

    # Auto-detect date column — try '製造日期' first, then common patterns
    date_col = None
    for col_name in ['製造日期', 'Date', 'date', 'Timestamp', 'timestamp', 'DateTime', 'datetime']:
        if col_name in df.columns:
            date_col = col_name
            break
    if date_col is None:
        # Try to find any column with 'date' in the name
        for c in df.columns:
            if 'date' in c.lower() or '日期' in c:
                date_col = c
                break

    if date_col and date_col != '製造日期':
        df['製造日期'] = pd.to_datetime(df[date_col], errors='coerce')
    elif date_col == '製造日期':
        df['製造日期'] = pd.to_datetime(df['製造日期'], errors='coerce')

    # Ensure a LotNo column exists (required by many graph builder features)
    if 'LotNo' not in df.columns:
        lot_candidates = ['Lot', 'lot', 'LotID', 'lot_id', 'ID', 'id', 'Sample', 'sample']
        for lc in lot_candidates:
            if lc in df.columns:
                df['LotNo'] = df[lc].astype(str)
                break
        else:
            df['LotNo'] = [f"Row-{i+1}" for i in range(len(df))]

    # Build sym_map: column → display name (identity map for standalone)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    sym_map = {c: c for c in numeric_cols}

    # Build auxiliary tables
    df_7d = pd.DataFrame()
    df_chart_config = pd.DataFrame({'CoAItem': numeric_cols, 'Symbol': numeric_cols})
    df_action = pd.DataFrame(columns=['LotNo', 'CoAItem', 'Action_Comment', 'Timestamp'])
    df_variable_info = pd.DataFrame()
    round_map = {}

    result = (df, df_7d, sym_map, df_chart_config, df_action, df_variable_info, round_map)

    # Cache
    _FILE_CACHE[cache_key] = result
    _FILE_CACHE.move_to_end(cache_key)
    if len(_FILE_CACHE) > _MAX_CACHE:
        _FILE_CACHE.popitem(last=False)

    return result


def get_available_groups(data_dir):
    """Return list of dropdown options for available data files."""
    files = discover_files(data_dir)
    return [{'label': name, 'value': name} for name, _ in files]
