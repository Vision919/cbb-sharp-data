from __future__ import annotations

import os
import io
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# -------------------------
# Config
# -------------------------

# Option A (recommended): local folder where your update_model writes CSVs
DATA_DIR = os.getenv("C:\Users\Brody\Desktop\cbb-sharp-data", os.getcwd())

# Option B: GitHub raw base (fallback)
# Example: https://raw.githubusercontent.com/Vision919/cbb-sharp-data/main
GITHUB_RAW_BASE = os.getenv("SHARP_GITHUB_RAW_BASE", "").rstrip("/")

# Optional simple auth for Actions (recommended)
# Set SHARP_API_KEY on server and set the same key in GPT Action headers.
SHARP_API_KEY = os.getenv("9181", "")

# CSV filenames your pipeline produces
FILES = {
    "kenpom": os.getenv("SHARP_KENPOM_FILE", "kenpom_live.csv"),
    "vegas": os.getenv("SHARP_VEGAS_FILE", "vegas_odds.csv"),
    "players": os.getenv("SHARP_PLAYERS_FILE", "player_stats.csv"),
    "slate": os.getenv("SHARP_SLATE_FILE", "active_slate.csv"),
}

# Cache to avoid re-reading every request
CACHE_TTL_SECONDS = int(os.getenv("SHARP_CACHE_TTL", "30"))


@dataclass
class CacheItem:
    ts: float
    df: pd.DataFrame


_cache: Dict[str, CacheItem] = {}


def _require_api_key(x_api_key: Optional[str]) -> None:
    if not SHARP_API_KEY:
        return  # auth disabled
    if not x_api_key or x_api_key != SHARP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _local_path(key: str) -> str:
    return os.path.join(DATA_DIR, FILES[key])


def _read_csv_local(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _read_csv_github(filename: str) -> pd.DataFrame:
    if not GITHUB_RAW_BASE:
        raise FileNotFoundError("No GitHub base configured and local file missing.")
    # Cache-bust to avoid CDN staleness
    url = f"{GITHUB_RAW_BASE}/{filename}?v={int(time.time())}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    # Let pandas sniff delimiters/quotes normally (your CSVs are standard)
    return pd.read_csv(io.StringIO(r.text))


def _get_df(key: str) -> pd.DataFrame:
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached.ts) < CACHE_TTL_SECONDS:
        return cached.df

    # Try local first
    try:
        df = _read_csv_local(_local_path(key))
    except Exception:
        # Fallback to GitHub raw
        df = _read_csv_github(FILES[key])

    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    _cache[key] = CacheItem(ts=now, df=df)
    return df


def _df_to_records(df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if limit is not None:
        df = df.head(limit)
    # Replace NaN with None for clean JSON
    return df.where(pd.notnull(df), None).to_dict(orient="records")


app = FastAPI(title="Sharp-CBB Data API", version="2.0")

# Allow your Custom GPT / browser origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/sharp/health")
def health(x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_api_key(x_api_key)

    status: Dict[str, Any] = {"ok": True, "data_dir": DATA_DIR, "github_raw_base": GITHUB_RAW_BASE or None}
    for k in FILES:
        lp = _local_path(k)
        status[f"{k}_local_exists"] = os.path.exists(lp)
    return status


@app.get("/sharp/data")
def sharp_data(
    x_api_key: Optional[str] = Header(default=None),
    include_rows: bool = Query(default=True),
    preview_rows: int = Query(default=0, ge=0, le=200),
) -> Dict[str, Any]:
    """
    Returns all four bridges:
      - kenpom
      - vegas
      - players
      - slate

    include_rows=false returns counts + columns only.
    preview_rows>0 returns only N rows per table (debugging).
    """
    _require_api_key(x_api_key)

    payload: Dict[str, Any] = {"ok": True, "generated_at_unix": int(time.time()), "tables": {}}

    for key in ["kenpom", "vegas", "players", "slate"]:
        df = _get_df(key)
        table_info: Dict[str, Any] = {
            "rows": int(df.shape[0]),
            "cols": [str(c) for c in df.columns.tolist()],
        }
        if include_rows:
            limit = preview_rows if preview_rows > 0 else None
            table_info["data"] = _df_to_records(df, limit=limit)
        payload["tables"][key] = table_info

    return payload


@app.get("/sharp/game")
def sharp_game(
    team: str = Query(..., description="Team name fragment; matches Home or Away in vegas table"),
    x_api_key: Optional[str] = Header(default=None),
    max_results: int = Query(default=10, ge=1, le=50),
) -> Dict[str, Any]:
    _require_api_key(x_api_key)

    vegas = _get_df("vegas").copy()

    # Expecting your schema: Home, Away, Vegas_Spread, Bookmaker, Commence_Time
    # (case-insensitive handling)
    cols = {c.lower(): c for c in vegas.columns}
    if "home" not in cols or "away" not in cols:
        raise HTTPException(status_code=500, detail="Vegas CSV must contain Home and Away columns.")

    home_col = cols["home"]
    away_col = cols["away"]

    team_l = team.strip().lower()
    mask = vegas[home_col].astype(str).str.lower().str.contains(team_l) | vegas[away_col].astype(str).str.lower().str.contains(team_l)
    matches = vegas.loc[mask].head(max_results)

    return {
        "ok": True,
        "query": team,
        "matches": _df_to_records(matches),
        "match_count": int(matches.shape[0]),
    }


# Run:
#   pip install fastapi uvicorn pandas requests
#   uvicorn server:app --host 0.0.0.0 --port 8000