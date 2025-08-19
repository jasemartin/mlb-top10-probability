from datetime import date, timedelta
from pybaseball import statcast_batter, statcast_pitcher

# Enable local caching for pybaseball to reduce repeated network calls
try:
    from pybaseball import cache
    cache.enable()
except Exception:
    pass

def fetch_batter_data(batter_id: int, days_back: int = 60):
    end = date.today()
    start = end - timedelta(days=days_back)
    return statcast_batter(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), batter_id)

def fetch_pitcher_data(pitcher_id: int, days_back: int = 60):
    end = date.today()
    start = end - timedelta(days=days_back)
    return statcast_pitcher(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), pitcher_id)

# Functions used by daily_board.py

def get_batter_statcast_window(batter_id: int, lookback_days: int = 60):
    return fetch_batter_data(batter_id, days_back=lookback_days)

def get_pitcher_statcast_window(pitcher_id: int, lookback_days: int = 60):
    return fetch_pitcher_data(pitcher_id, days_back=lookback_days)