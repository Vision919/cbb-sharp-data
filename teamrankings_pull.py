import re
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

# TeamRankings stat pages (NCAA men's)
URLS = {
    "TR_3P_Rate": "https://www.teamrankings.com/ncaa-basketball/stat/three-point-rate",
    "TR_ORB_Pct": "https://www.teamrankings.com/ncaa-basketball/stat/offensive-rebounding-pct",
    "TR_TOV_PerPoss": "https://www.teamrankings.com/ncaa-basketball/stat/turnovers-per-possession",
}

OUTFILE = "teamrankings_live.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    )
}

def _normalize_team(name: str) -> str:
    s = (name or "").lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[\.\'’]", "", s)
    s = re.sub(r"\s+", " ", s)

    # normalize common abbreviations
    # note: keep this conservative; too aggressive can break names
    s = s.replace(" st ", " state ")
    s = s.replace(" st-", " state ")
    s = s.replace(" st.", " state")

    return s.strip()

# Optional aliases for stubborn mismatches (normalized -> normalized)
ALIASES = {
    # "iu indy": "iupui",  # example if you ever need it
}

def _pick_season_col(df: pd.DataFrame) -> str:
    """
    TeamRankings tables usually look like:
      Rank | Team | 2025-26 | Last 3 | Last 1 | Home | Away | 2024-25 ...
    We want the season col, not Rank, not Team.
    """
    cols = [str(c).strip() for c in df.columns]

    # common season header patterns
    # prefer current season columns first
    preferred_patterns = [
        r"^2025-26$",
        r"^2025$",
        r"^2026$",
        r"^2024-25$",
        r"^2024$",
        r"^2023-24$",
        r"^2023$",
    ]
    for pat in preferred_patterns:
        for c in cols:
            if re.match(pat, c):
                return c

    # fallback: first column that looks like a year or season and is not Rank/Team
    for c in cols:
        if c.lower() in {"rank", "team"}:
            continue
        if re.match(r"^\d{4}(-\d{2})?$", c):
            return c

    # final fallback: first non-rank, non-team numeric-ish column
    for c in cols:
        if c.lower() in {"rank", "team"}:
            continue
        return c

    raise RuntimeError(f"No suitable season/stat column found. cols={cols}")

def _to_float_value(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None

    # remove commas
    s = s.replace(",", "")

    # common non-values
    if s.lower() in {"nan", "none", "-", "—"}:
        return None

    # handle percent like "54.1%"
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return None

    # plain numeric
    try:
        return float(s)
    except ValueError:
        return None

def _maybe_convert_percent_stat(stat_key: str, series: pd.Series) -> pd.Series:
    """
    We want:
      - 3P Rate and ORB% stored as decimal (0.541)
      - TOV per poss stored as numeric (e.g., 0.19)
    TeamRankings sometimes presents percent stats as 54.1 (implied %) or 54.1%.
    We'll:
      - if any value > 1.5 on percent-stat pages, assume it's in percent units and divide by 100
    """
    percent_stats = {"TR_3P_Rate", "TR_ORB_Pct"}
    if stat_key not in percent_stats:
        return series

    # if the page already had %, we already converted to decimal in _to_float_value
    # but if the page returns "54.1" (no %), it's still > 1 and needs /100
    # Heuristic: if median > 1.5, treat as percent units.
    s = series.dropna()
    if s.empty:
        return series

    if s.median() > 1.5:
        return series / 100.0

    return series

def _fetch_stat(stat_key: str, url: str) -> pd.DataFrame:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    tables = pd.read_html(r.text)
    if not tables:
        raise RuntimeError(f"No tables found at {url}")

    df = tables[0].copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Find Team column robustly
    if "Team" not in df.columns:
        team_col = next((c for c in df.columns if c.lower() == "team"), None)
        if not team_col:
            raise RuntimeError(f"Could not find Team column at {url}. cols={df.columns.tolist()}")
        df.rename(columns={team_col: "Team"}, inplace=True)

    season_col = _pick_season_col(df)

    out = df[["Team", season_col]].copy()
    out.rename(columns={season_col: "Value"}, inplace=True)

    # parse values safely
    out["Value"] = out["Value"].apply(_to_float_value)
    out = out.dropna(subset=["Value"]).reset_index(drop=True)

    # normalize + apply aliases
    out["Team_norm"] = out["Team"].map(_normalize_team)
    out["Team_norm"] = out["Team_norm"].map(lambda t: ALIASES.get(t, t))

    # percent-stat normalization
    out["Value"] = _maybe_convert_percent_stat(stat_key, out["Value"])

    return out[["Team", "Team_norm", "Value"]]

def build_teamrankings_csv():
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    merged = None
    for stat_key, url in URLS.items():
        stat_df = _fetch_stat(stat_key, url)

        stat_df = stat_df[["Team_norm", "Value"]].rename(columns={"Value": stat_key})

        if merged is None:
            merged = stat_df
        else:
            merged = merged.merge(stat_df, on="Team_norm", how="outer")

        time.sleep(1.0)  # be polite

    if merged is None or merged.empty:
        raise RuntimeError("No TeamRankings data merged.")

    merged.insert(0, "Team", merged["Team_norm"])
    merged["Pulled_At_UTC"] = pulled_at

    merged.to_csv(OUTFILE, index=False, lineterminator="\n", encoding="utf-8")
    print(f"✅ Wrote {OUTFILE} with {len(merged)} teams. Pulled_At_UTC={pulled_at}")

if __name__ == "__main__":
    build_teamrankings_csv()