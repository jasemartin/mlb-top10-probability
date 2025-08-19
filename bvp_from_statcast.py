from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from pybaseball import statcast_batter

CACHE_PATH = Path("data/bvp_cache.parquet")

def _events_to_hits(ev: pd.Series) -> int:
    return int(ev.isin(["single", "double", "triple", "home_run"]).sum())

def _load_cache():
    if CACHE_PATH.exists():
        try:
            df = pd.read_parquet(CACHE_PATH)
            for col in ["ab"]:
                if col not in df.columns:
                    df[col] = pd.NA
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["batter_id","pitcher_id","pa","ab","avg","woba","hr","asof"])

def _save_cache(df: pd.DataFrame):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(CACHE_PATH, index=False)
    except Exception:
        pass

def bvp_for_pair(batter_id: int, pitcher_id: int, days_back: int = 730, refresh_days: int = 3) -> dict:
    cache = _load_cache()
    if not cache.empty:
        mask = (cache["batter_id"] == batter_id) & (cache["pitcher_id"] == pitcher_id)
        if mask.any():
            row = cache[mask].iloc[0]
            try:
                if (date.today() - pd.to_datetime(row["asof"]).date()).days < refresh_days:
                    return dict(pa=int(row["pa"]), ab=int(row["ab"] or 0),
                                avg=float(row["avg"]) if pd.notna(row["avg"]) else float("nan"),
                                woba=float(row["woba"]) if pd.notna(row["woba"]) else float("nan"),
                                hr=int(row["hr"]))
            except Exception:
                pass

    end = date.today()
    start = end - timedelta(days=days_back)
    df = statcast_batter(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), batter_id)
    if df is None or df.empty:
        result = {"pa": 0, "ab": 0, "avg": float("nan"), "woba": float("nan"), "hr": 0}
    else:
        pair = df[df["pitcher"] == pitcher_id]
        if pair.empty:
            result = {"pa": 0, "ab": 0, "avg": float("nan"), "woba": float("nan"), "hr": 0}
        else:
            pa = len(pair)
            ev = pair["events"].fillna("")
            bb = (ev == "walk").sum()
            hbp = (ev == "hit_by_pitch").sum()
            sf = (ev == "sac_fly").sum()
            ab = max(0, pa - (bb + hbp + sf))
            hits = _events_to_hits(ev)
            hr = int((ev == "home_run").sum())
            avg = float(hits / ab) if ab > 0 else float("nan")
            woba = float(np.nanmean(pair["estimated_woba_using_speedangle"])) if "estimated_woba_using_speedangle" in pair.columns else float("nan")
            result = {"pa": int(pa), "ab": int(ab), "avg": avg, "woba": woba, "hr": hr}

    new_row = pd.DataFrame([{**result, "batter_id": int(batter_id), "pitcher_id": int(pitcher_id), "asof": pd.Timestamp(date.today())}])
    if not cache.empty:
        mask = (cache["batter_id"] == batter_id) & (cache["pitcher_id"] == pitcher_id)
        if mask.any():
            cache.loc[mask, new_row.columns] = new_row.iloc[0]
        else:
            cache = pd.concat([cache, new_row], ignore_index=True)
    else:
        cache = new_row
    _save_cache(cache)
    return result

def blend_bvp_into_features(feats: dict, bvp: dict, max_weight: float = 0.4, include_hr_barrel_boost: bool = True):
    """
    Blend Statcast-derived BvP summary into rolling features.
    - Weighted blend of AVG -> b_xba and wOBA -> b_xwoba
    - Optional small barrel-rate boost for notable HR history
    """
    pa = float(bvp.get("pa", 0) or 0)
    ab = float(bvp.get("ab", 0) or 0)
    if pa <= 0:
        return feats

    # Heavier weight if AB >= 12, otherwise cap by max_weight scaled by PA
    w = 0.5 if ab >= 12 else min(max_weight, pa / 10.0)

    def _tf(v):
        try:
            f = float(v)
            return f if f == f else None  # filter NaN
        except Exception:
            return None

    avg = _tf(bvp.get("avg"))
    woba = _tf(bvp.get("woba"))
    if avg is not None and feats.get("b_xba") is not None:
        feats["b_xba"] = (1 - w) * feats["b_xba"] + w * avg
    if woba is not None and feats.get("b_xwoba") is not None:
        feats["b_xwoba"] = (1 - w) * feats["b_xwoba"] + w * woba

    # Optional: modest bump to barrel rate for multiple prior HR vs this pitcher
    if include_hr_barrel_boost:
        hr_val = _tf(bvp.get("hr")) or 0.0
        b_bar = feats.get("b_barrel")
        try:
            if hr_val >= 2 and b_bar is not None and b_bar == b_bar:  # not NaN
                feats["b_barrel"] = b_bar + min(0.03, hr_val * 0.003)
        except Exception:
            pass

    return feats