"""
Map data processing and auto-zoom calculations.
"""
import pandas as pd
from typing import Dict, Optional, Tuple, List


def calculate_auto_zoom_bounds(
    dfs: Dict[str, pd.DataFrame],
    has_search: bool = False,
    search_margin: float = 0.4,
    filter_margin: float = 0.05
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Calculate map bounds for auto-zoom based on data coordinates.
    
    Args:
        dfs: Dictionary of program -> DataFrame with latitude/longitude columns
        has_search: Whether zoom is for a search (uses search_margin)
        search_margin: Margin multiplier for search results (0.4 = 40%)
        filter_margin: Margin multiplier for filters (0.05 = 5%)
    
    Returns:
        Tuple of ((min_lat, min_lon), (max_lat, max_lon)) or None if no data
    """
    if not isinstance(dfs, dict):
        return None
    
    all_lats = []
    all_lons = []
    
    for program, df in dfs.items():
        if df is None or df.empty:
            continue
        
        if "latitud" not in df.columns or "longitud" not in df.columns:
            continue
        
        lats = pd.to_numeric(df["latitud"], errors="coerce").dropna()
        lons = pd.to_numeric(df["longitud"], errors="coerce").dropna()
        
        all_lats.extend(lats.tolist())
        all_lons.extend(lons.tolist())
    
    if not all_lats or not all_lons:
        return None
    
    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lon, max_lon = min(all_lons), max(all_lons)
    
    # Select margin based on context
    margin = search_margin if has_search else filter_margin
    
    # Calculate margins
    lat_margin = (max_lat - min_lat) * margin if max_lat != min_lat else 2.0
    lon_margin = (max_lon - min_lon) * margin if max_lon != min_lon else 2.0
    
    return (
        (min_lat - lat_margin, min_lon - lon_margin),
        (max_lat + lat_margin, max_lon + lon_margin)
    )


def check_dataframes_have_data(dfs: Dict[str, pd.DataFrame]) -> bool:
    """Check if any dataframe has data."""
    if not isinstance(dfs, dict):
        return False
    return any(df is not None and not df.empty for df in dfs.values())


def filter_out_no_la(dfs: Dict[str, pd.DataFrame], program: str) -> Dict[str, pd.DataFrame]:
    """Filter Erasmus OUT program to exclude LA records (empty link_LA).
    
    Args:
        dfs: Dictionary of program -> DataFrame
        program: Program key to filter (typically PROGRAM_ERASMUS_OUT)
    
    Returns:
        Modified dfs dictionary with filtered program
    """
    if program not in dfs:
        return dfs
    
    df = dfs[program]
    if "link_LA" not in df.columns:
        return dfs
    
    mask = df["link_LA"].isna() | (df["link_LA"].astype(str).str.strip() == "")
    dfs[program] = df[mask]
    
    return dfs
