from __future__ import annotations
import requests
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

from fetch_data import get_batter_statcast_window, get_pitcher_statcast_window
from features import batter_rolling_features, pitcher_rolling_features, platoon_advantage
from baseline_rules import prob_hit, prob_hr, prob_total_bases, prob_pitcher_k_ge
from bvp_from_statcast import bvp_for_pair, blend_bvp_into_features

STATSAPI = "https://statsapi.mlb.com/api/v1"

def get_schedule_with_probables(dt: str) -> List[dict]:
    url = f"{STATSAPI}/schedule?sportId=1&date={dt}&hydrate=probablePitcher,team,person"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    data = r.json()
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    return games

def get_team_active_roster(team_id: int) -> List[dict]:
    url = f"{STATSAPI}/teams/{team_id}/roster?rosterType=active"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return (r.json() or {}).get("roster", [])

def collect_daily_candidates(dt: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    games = get_schedule_with_probables(dt)
    hitter_rows, pitcher_rows = [], []
    for g in games:
        home = g["teams"]["home"]; away = g["teams"]["away"]
        home_id = home["team"]["id"]; away_id = away["team"]["id"]
        home_pp = (home.get("probablePitcher") or {}).get("id")
        away_pp = (away.get("probablePitcher") or {}).get("id")
        if home_pp: pitcher_rows.append({"pitcher_id": home_pp, "team_id": home_id, "opponent_team_id": away_id})
        if away_pp: pitcher_rows.append({"pitcher_id": away_pp, "team_id": away_id, "opponent_team_id": home_id})
        for tid, oid, opp_pp in [(home_id, away_id, away_pp), (away_id, home_id, home_pp)]:
            roster = get_team_active_roster(tid)
            for r in roster:
                if ((r.get("position") or {}).get("type") == "P"):
                    continue
                person = (r.get("person") or {})
                pid = person.get("id"); full = person.get("fullName")
                bats = (person.get("batSide") or {}).get("code")
                if not pid:
                    continue
                hitter_rows.append({
                    "batter_id": pid, "batter_name": full, "bat_side": bats,
                    "team_id": tid, "opponent_team_id": oid, "opp_prob_pitcher_id": opp_pp
                })
    return (pd.DataFrame(hitter_rows).drop_duplicates(subset=["batter_id"]),
            pd.DataFrame(pitcher_rows).drop_duplicates(subset=["pitcher_id"]))

def compute_hitters_board(hitters_df: pd.DataFrame, lookback_days: int, park_multi: float = 1.0) -> pd.DataFrame:
    rows = []
    for _, row in hitters_df.iterrows():
        b_id = int(row["batter_id"])
        opp_pp = int(row["opp_prob_pitcher_id"]) if pd.notna(row["opp_prob_pitcher_id"]) else None
        try:
            bdf = get_batter_statcast_window(b_id, lookback_days)
            bfeats = batter_rolling_features(bdf)
            pfeats, p_throws = {}, None
            if opp_pp:
                pdf = get_pitcher_statcast_window(opp_pp, lookback_days)
                pfeats = pitcher_rolling_features(pdf)
                if "p_throws" in pdf.columns and pdf["p_throws"].notna().any():
                    p_throws = str(pdf["p_throws"].dropna().mode().iloc[0])
            feats = {**bfeats, **pfeats, "park_multi": park_multi}
            feats["platoon_adv"] = platoon_advantage(row.get("bat_side"), p_throws)

            # Statcast-derived BvP (consolidated)
            if opp_pp:
                bvp = bvp_for_pair(b_id, opp_pp, days_back=730, refresh_days=3)
                feats = blend_bvp_into_features(feats, bvp, max_weight=0.4)

            rows.append({
                "batter_id": b_id, "batter_name": row.get("batter_name"),
                "p_hit": prob_hit(feats),
                "p_hr": prob_hr(feats),
                "p_tb1": prob_total_bases(feats, 1),
                "p_tb2": prob_total_bases(feats, 2),
                "p_tb3": prob_total_bases(feats, 3),
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

def compute_pitchers_board(pitchers_df: pd.DataFrame, lookback_days: int, park_k_multi: float = 1.0, opp_k_vs_hand: float = 0.22) -> pd.DataFrame:
    rows = []
    for _, row in pitchers_df.iterrows():
        pid = int(row["pitcher_id"])
        try:
            pdf = get_pitcher_statcast_window(pid, lookback_days)
            pfeats = pitcher_rolling_features(pdf)
            k_feats = {
                "p_k_per_pa": pfeats.get("p_k_per_pa", np.nan),
                "p_pa_per_game": pfeats.get("p_pa_per_game", 24.0),
                "opp_k_vs_hand": opp_k_vs_hand,
                "park_k_multi": park_k_multi,
                "role_starter": 1
            }
            rows.append({"pitcher_id": pid, "p_6plusK": prob_pitcher_k_ge(k_feats, k_threshold=6)})
        except Exception:
            continue
    return pd.DataFrame(rows)

def daily_top10(dt: str, lookback_days: int = 30, park_multi: float = 1.0, park_k_multi: float = 1.0, opp_k_vs_hand: float = 0.22) -> Dict[str, pd.DataFrame]:
    hitters_df, pitchers_df = collect_daily_candidates(dt)
    hitters_board = compute_hitters_board(hitters_df, lookback_days, park_multi)
    pitchers_board = compute_pitchers_board(pitchers_df, lookback_days, park_k_multi, opp_k_vs_hand)
    out = {}
    if not hitters_board.empty:
        out["hit"] = hitters_board.sort_values("p_hit", ascending=False).head(10).reset_index(drop=True)
        out["hr"]  = hitters_board.sort_values("p_hr",  ascending=False).head(10).reset_index(drop=True)
        out["tb1"] = hitters_board.sort_values("p_tb1", ascending=False).head(10).reset_index(drop=True)
        out["tb2"] = hitters_board.sort_values("p_tb2", ascending=False).head(10).reset_index(drop=True)
        out["tb3"] = hitters_board.sort_values("p_tb3", ascending=False).head(10).reset_index(drop=True)
    if not pitchers_board.empty:
        out["k6"]  = pitchers_board.sort_values("p_6plusK", ascending=False).head(10).reset_index(drop=True)
    return out