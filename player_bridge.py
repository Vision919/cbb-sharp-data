import os
import re
import json
import time
import random
import subprocess
from io import StringIO

import pandas as pd
import requests


PROGRESS_FILE = "scrape_progress.json"
OUTPUT_CSV = "player_stats.csv"

BASE_URL = "https://www.sports-reference.com"
SEASON = 2026

# Be kind to Sports-Reference; randomized delay reduces 429s
DELAY_SECONDS_MIN = 6
DELAY_SECONDS_MAX = 11

# Retry behavior
MAX_RETRIES_PER_CONF = 4
TIMEOUT_SECONDS = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}

CONF_SLUGS = [
    "acc", "sec", "big-12", "big-ten", "big-east", "mwc", "american", "atlantic-10",
    "wcc", "sun-belt", "mac", "cusa", "horizon", "mvc", "maac", "southland", "summit",
    "wac", "big-sky", "big-south", "big-west", "caa", "ivy", "meac", "nec", "ovc",
    "patriot", "southern", "swac", "asun", "america-east"
]


def save_checkpoint(processed_confs: list[str], rows: list[dict]) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed": processed_confs, "rows": rows}, f)


def load_checkpoint() -> tuple[list[str], list[dict]]:
    if not os.path.exists(PROGRESS_FILE):
        return [], []
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        ckpt = json.load(f)
    return ckpt.get("processed", []), ckpt.get("rows", [])


def strip_html_comments(html: str) -> str:
    """
    Sports-Reference frequently wraps tables in HTML comments.
    pandas.read_html won't see them unless we remove <!-- and -->.
    """
    # Remove comment markers but keep content
    html = re.sub(r"<!--\s*", "", html)
    html = re.sub(r"\s*-->", "", html)
    return html


def polite_delay() -> None:
    time.sleep(random.uniform(DELAY_SECONDS_MIN, DELAY_SECONDS_MAX))


def fetch_with_retries(url: str) -> str | None:
    """
    Fetch HTML with retries and exponential backoff on 429/5xx.
    Returns HTML text or None on failure.
    """
    backoff = 10
    for attempt in range(1, MAX_RETRIES_PER_CONF + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)

            if resp.status_code == 200:
                return resp.text

            if resp.status_code == 429:
                print(f"🛑 429 rate limit. Backing off {backoff}s (attempt {attempt}/{MAX_RETRIES_PER_CONF})")
                time.sleep(backoff)
                backoff *= 2
                continue

            if 500 <= resp.status_code < 600:
                print(f"⚠️ Server {resp.status_code}. Backing off {backoff}s (attempt {attempt}/{MAX_RETRIES_PER_CONF})")
                time.sleep(backoff)
                backoff *= 2
                continue

            # Other non-200: treat as skip
            print(f"⚠️ Non-200 status {resp.status_code} for {url}")
            return None

        except requests.RequestException as e:
            print(f"⚠️ Request error: {e} (attempt {attempt}/{MAX_RETRIES_PER_CONF}, backoff {backoff}s)")
            time.sleep(backoff)
            backoff *= 2

    return None


def extract_player_table(dfs: list[pd.DataFrame]) -> pd.DataFrame | None:
    """
    Find the dataframe that contains player per-game stats with Player + PTS + AST.
    """
    for df in dfs:
        cols = {str(c).strip() for c in df.columns}
        if "Player" in cols and "PTS" in cols and "AST" in cols:
            return df
    return None


def normalize_team_name(team: str) -> str:
    # Remove artifacts like " NCAA" if present
    return str(team).replace(" NCAA", "").strip()


def scrape_conference(slug: str) -> list[dict]:
    """
    Returns list of dict rows: Team, Player, PPG, APG, Conf
    """
    url = f"{BASE_URL}/cbb/conferences/{slug}/men/{SEASON}-stats.html"
    print(f"📡 Scraping {slug.upper()} → {url}")

    polite_delay()

    html = fetch_with_retries(url)
    if not html:
        return []

    clean_html = strip_html_comments(html)

    try:
        dfs = pd.read_html(StringIO(clean_html))
    except ValueError:
        # No tables found
        print(f"⚠️ No tables found for {slug.upper()}")
        return []

    stats_df = extract_player_table(dfs)
    if stats_df is None:
        print(f"⚠️ Could not locate Player/PTS/AST table for {slug.upper()}")
        return []

    # Identify the team column (varies by page)
    team_col = "Team" if "Team" in stats_df.columns else ("School" if "School" in stats_df.columns else None)
    if team_col is None:
        print(f"⚠️ No Team/School column found for {slug.upper()}")
        return []

    # Clean numeric columns
    stats_df["PTS"] = pd.to_numeric(stats_df["PTS"], errors="coerce")
    stats_df["AST"] = pd.to_numeric(stats_df["AST"], errors="coerce")

    # Keep only rows with usable stats
    stats_df = stats_df.dropna(subset=["Player", team_col, "PTS", "AST"])

    rows: list[dict] = []
    for _, r in stats_df.iterrows():
        team = normalize_team_name(r[team_col])
        player = str(r["Player"]).strip()

        # Sports-Reference columns here are per-game on the conference page.
        rows.append({
            "Team": team,
            "Player": player,
            "PPG": float(r["PTS"]),
            "APG": float(r["AST"]),
            "Conf": slug.upper(),
        })

    return rows


def scrape_stars() -> bool:
    print("🚀 Initializing Resilient Crawler (V3.1)…")

    processed_confs, all_rows = load_checkpoint()
    if processed_confs:
        print(f"⏯ Resuming from checkpoint ({len(processed_confs)} conferences finished)…")

    for slug in CONF_SLUGS:
        if slug in processed_confs:
            continue

        conf_rows = scrape_conference(slug)
        if conf_rows:
            print(f"✅ {slug.upper()} scraped: {len(conf_rows)} player rows")
            all_rows.extend(conf_rows)
        else:
            print(f"⚠️ {slug.upper()} returned 0 rows (kept going)")

        processed_confs.append(slug)
        save_checkpoint(processed_confs, all_rows)

    if not all_rows:
        print("❌ No player data collected. Output not written.")
        return False

    final_df = pd.DataFrame(all_rows)

    # Deduplicate on Team+Player; keep the first occurrence
    final_df = final_df.drop_duplicates(subset=["Team", "Player"])

    # Write clean CSV (LF newlines) so parsers don't misread it as empty
    final_df.to_csv(OUTPUT_CSV, index=False, lineterminator="\n", encoding="utf-8")

    # Cleanup
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    print(f"✨ Success! Wrote {len(final_df)} rows → {OUTPUT_CSV}")
    return True


def git_push() -> None:
    try:
        subprocess.run(["git", "add", OUTPUT_CSV], check=True)
        subprocess.run(["git", "commit", "-m", "Update player bridge (V3.1)"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub updated.")
    except Exception as e:
        print(f"⚠️ Git push skipped/failed: {e}")


if __name__ == "__main__":
    if scrape_stars():
        git_push()