import requests
import pandas as pd
import subprocess
from datetime import datetime, timedelta, timezone

# =========================
# CONFIGURATION (EDIT THIS)
# =========================

# Keep your API key in-script (as requested)
API_KEY = "2bbe97fa1d5c98b006c9aa75a9f5691c"

SPORT = "basketball_ncaab"
REGIONS = "us"

# Tri-market (Spread + ML + Total)
MARKETS = "h2h,spreads,totals"

ODDS_FORMAT = "american"
DATE_FORMAT = "iso"

# IMPORTANT:
# Use bookmaker KEYS (not titles). Examples: "draftkings", "fanduel", "betonlineag".
# Limiting to ONE book keeps payload smaller and makes results more stable.
BOOKMAKER_KEYS = "draftkings"  # change if you want a different single book

OUTPUT_FILE = "vegas_odds.csv"


def _today_window_utc() -> tuple[str, str]:
    """Return an ISO8601 commenceTimeFrom/To window.

    We pull roughly "today" in UTC, plus a buffer to catch late-night games
    that might spill past midnight in some timezones.
    """
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1, hours=12)  # 36-hour window
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def fetch_vegas_odds() -> pd.DataFrame:
    if not API_KEY or API_KEY.strip() in {"", "PASTE_YOUR_ODDS_API_KEY_HERE"}:
        raise RuntimeError("API_KEY is not set. Paste your Odds API key into API_KEY at the top of the script.")

    commence_from, commence_to = _today_window_utc()

    print("📡 Requesting Live Vegas Odds (single call, filtered to today window)...")
    print(f"🕒 Window (UTC): {commence_from} → {commence_to}")

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        # v4 uses apiKey (capital K) per docs
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
        "dateFormat": DATE_FORMAT,
        "bookmakers": BOOKMAKER_KEYS,
        "commenceTimeFrom": commence_from,
        "commenceTimeTo": commence_to,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Odds API request failed: {e}")

    # Quota logging (monitor credits)
    used = response.headers.get("x-requests-used")
    remaining = response.headers.get("x-requests-remaining")
    last = response.headers.get("x-requests-last")
    print(f"🧾 Quota — used: {used}, remaining: {remaining}, last cost: {last}")

    data = response.json() or []
    rows: list[dict] = []

    for game in data:
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        commence_time = game.get("commence_time")

        books = game.get("bookmakers") or []
        if not books:
            continue

        # Because we limited to a single bookmaker key, there should be 0–1
        book = books[0]

        spread = None
        spread_price_home = None
        spread_price_away = None
        ml_home = None
        ml_away = None
        total_line = None
        over_price = None
        under_price = None

        for market in book.get("markets", []):
            key = market.get("key")

            if key == "spreads":
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    if name == home_team:
                        spread = outcome.get("point")
                        spread_price_home = outcome.get("price")
                    elif name == away_team:
                        spread_price_away = outcome.get("price")

            elif key == "h2h":
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    if name == home_team:
                        ml_home = outcome.get("price")
                    elif name == away_team:
                        ml_away = outcome.get("price")

            elif key == "totals":
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    if name == "Over":
                        total_line = outcome.get("point")
                        over_price = outcome.get("price")
                    elif name == "Under":
                        under_price = outcome.get("price")

        # Row inclusion logic: keep a game if it has either spread OR moneyline
        if spread is None and ml_home is None and ml_away is None:
            continue

        rows.append(
            {
                "Home": home_team,
                "Away": away_team,
                "Vegas_Spread": float(spread) if spread is not None else None,
                "Spread_Price_Home": spread_price_home,
                "Spread_Price_Away": spread_price_away,
                "ML_Home": float(ml_home) if ml_home is not None else None,
                "ML_Away": float(ml_away) if ml_away is not None else None,
                "Total": float(total_line) if total_line is not None else None,
                "Over_Price": over_price,
                "Under_Price": under_price,
                "Bookmaker": book.get("title"),
                "Commence_Time": commence_time,
            }
        )

    if not rows:
        raise RuntimeError("No games returned for the selected window/book/markets.")

    df = pd.DataFrame(rows)
    df = df.sort_values("Commence_Time").reset_index(drop=True)
    print(f"✅ Logged {len(df)} games (tri-market where available).")
    return df


def _preserve_open_lines(df_new: pd.DataFrame) -> pd.DataFrame:
    """Merge in Open_* columns from existing OUTPUT_FILE when available.

    - If OUTPUT_FILE doesn't exist: initialize Open_* from current.
    - If Open_* columns don't exist in the old file (format change): create them.
    """
    merge_cols = ["Home", "Away", "Commence_Time"]
    open_cols = ["Open_Spread", "Open_Total", "Open_ML_Home", "Open_ML_Away", "Open_Pulled_At"]

    try:
        df_old = pd.read_csv(OUTPUT_FILE)
    except Exception:
        df_old = pd.DataFrame()

    # Ensure key columns exist in df_new
    for c in merge_cols:
        if c not in df_new.columns:
            raise RuntimeError(f"Missing required column in new vegas data: {c}")

    if df_old.empty:
        df = df_new.copy()
        for c in open_cols:
            df[c] = None
    else:
        # Ensure old has all merge cols + open cols (reindex adds missing as NaN)
        needed_old = merge_cols + open_cols
        df_old = df_old.reindex(columns=needed_old)

        df = df_new.merge(df_old, on=merge_cols, how="left")

        # Ensure open cols exist after merge
        for c in open_cols:
            if c not in df.columns:
                df[c] = None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["Open_Spread"] = df["Open_Spread"].fillna(df["Vegas_Spread"])
    df["Open_Total"] = df["Open_Total"].fillna(df["Total"])
    df["Open_ML_Home"] = df["Open_ML_Home"].fillna(df["ML_Home"])
    df["Open_ML_Away"] = df["Open_ML_Away"].fillna(df["ML_Away"])
    df["Open_Pulled_At"] = df["Open_Pulled_At"].fillna(now_str)

    return df


def git_push() -> None:
    try:
        subprocess.run(["git", "add", OUTPUT_FILE], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Vegas Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
            check=True,
        )
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("🚀 Vegas Data pushed to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git push skipped/failed: {e}")


if __name__ == "__main__":
    df_new = fetch_vegas_odds()
    df_final = _preserve_open_lines(df_new)

    df_final.to_csv(OUTPUT_FILE, index=False, lineterminator="\n", encoding="utf-8")
    print("📈 Drift tracking enabled (Open vs Current).")

    git_push()
