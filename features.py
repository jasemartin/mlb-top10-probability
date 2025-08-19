"""
Features module with rolling features for batters and pitchers.
This is a stub implementation for testing imports.
"""
import pandas as pd
import numpy as np

def batter_rolling_features(df: pd.DataFrame) -> dict:
    """Extract rolling features for a batter from Statcast data."""
    if df is None or df.empty:
        return {
            "b_xba": np.nan,
            "b_xwoba": np.nan,
            "b_barrel": np.nan,
        }
    
    # Stub implementation - in real version this would calculate rolling averages
    return {
        "b_xba": 0.250,  # Expected batting average
        "b_xwoba": 0.320,  # Expected weighted on-base average  
        "b_barrel": 0.08,  # Barrel rate
    }

def pitcher_rolling_features(df: pd.DataFrame) -> dict:
    """Extract rolling features for a pitcher from Statcast data."""
    if df is None or df.empty:
        return {
            "p_k_per_pa": np.nan,
            "p_pa_per_game": 24.0,
        }
    
    # Stub implementation - in real version this would calculate rolling averages
    return {
        "p_k_per_pa": 0.22,  # Strikeout rate per plate appearance
        "p_pa_per_game": 24.0,  # Plate appearances per game
    }

def platoon_advantage(bat_side: str, p_throws: str) -> float:
    """Calculate platoon advantage based on batter handedness vs pitcher handedness."""
    if not bat_side or not p_throws:
        return 0.0
    
    # Right-handed batter vs left-handed pitcher = advantage
    # Left-handed batter vs right-handed pitcher = advantage  
    # Same handedness = disadvantage
    if (bat_side == "R" and p_throws == "L") or (bat_side == "L" and p_throws == "R"):
        return 0.02  # 2% advantage
    elif bat_side == p_throws:
        return -0.01  # 1% disadvantage
    else:
        return 0.0  # Neutral