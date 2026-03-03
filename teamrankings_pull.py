import re
import time
from datetime import datetime, timezone

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
}

def _normalize_team(name: str) -> str:
    s = (name or "").lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[\.\'’]", "", s)
    s = re.sub(r"\s+", " ", s)
    # common abbrev normalization
    s = s.replace("st ", "state ")
    s = s.replace("st-", "state ")
    s = s.replace("st.", "state")
    return s

# Optional aliases for stubborn mismatches
ALIASES = {
    "iu indy": "iupuI",   # example — adjust to your naming conventions if needed
}

def _fetch_stat(url: str) -> pd.DataFrame:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    # TeamRankings pages typically have a single main stats table
    tables = pd.read_html(r.text)
    if not tables:
        raise RuntimeError(f"No tables found at {url}")
    df = tables[0].copy()
    # Expect columns like: "Team", "2025-26" or "Stat"
    df.columns = [str(c).strip() for c in df.columns]
    if "Team" not in df.columns:
        # sometimes it's "Team" with whitespace
        team_col = next((c for c in df.columns if c.lower() == "team"), None)
        if not team_col:
            raise RuntimeError(f"Could not find Team column at {url}. cols={df.columns.tolist()}")
        df.rename(columns={team_col: "Team"}, inplace=True)

    # pick the first non-Team numeric column as the stat value
    value_col = next((c for c in df.columns if c != "Team"), None)
    if not value_col:
        raise RuntimeError(f"No value column found at {url}")

    out = df[["Team", value_col]].copy()
    out.rename(columns={value_col: "Value"}, inplace=True)
    out["Value"] = pd.to_numeric(out["Value"], errors="coerce")
    out = out.dropna(subset=["Value"]).reset_index(drop=True)
    out["Team_norm"] = out["Team"].map(_normalize_team)
    return out

def build_teamrankings_csv():
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    merged = None
    for col, url in URLS.items():
        stat_df = _fetch_stat(url)
        stat_df = stat_df[["Team_norm", "Value"]].rename(columns={"Value": col})
        if merged is None:
            merged = stat_df
        else:
            merged = merged.merge(stat_df, on="Team_norm", how="outer")

        # be polite to the site
        time.sleep(1.0)

    if merged is None or merged.empty:
        raise RuntimeError("No TeamRankings data merged.")

    # keep a representative display name (optional)
    merged.insert(0, "Team", merged["Team_norm"])
    merged["Pulled_At_UTC"] = pulled_at

    # clean up
    merged.to_csv(OUTFILE, index=False, lineterminator="\n", encoding="utf-8")
    print(f"✅ Wrote {OUTFILE} with {len(merged)} teams. Pulled_At_UTC={pulled_at}")

if __name__ == "__main__":
    build_teamrankings_csv()