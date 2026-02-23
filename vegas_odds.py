import requests
import pandas as pd
import subprocess
from datetime import datetime

# CONFIGURATION
API_KEY = 'd1c3c64a476503067b993331a62a7ae5'
SPORT = 'basketball_ncaab'
REGIONS = 'us'
MARKETS = 'spreads'
ODDS_FORMAT = 'american'

PREFERRED_BOOKS = ["DraftKings", "FanDuel", "BetOnline.ag"]

OUTPUT_FILE = "vegas_odds.csv"


def fetch_vegas_odds():
    print("📡 Requesting Live Vegas Odds...")

    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ API request failed: {e}")
        return None

    data = response.json()
    rows = []

    for game in data:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        commence_time = game.get('commence_time')

        if not game.get('bookmakers'):
            continue

        selected_book = None

        # Choose preferred bookmaker in priority order
        for preferred in PREFERRED_BOOKS:
            for book in game['bookmakers']:
                if book['title'] == preferred:
                    selected_book = book
                    break
            if selected_book:
                break

        # If no preferred book found, skip game
        if not selected_book:
            continue

        spread = None

        for market in selected_book.get('markets', []):
            if market['key'] == 'spreads':
                for outcome in market.get('outcomes', []):
                    if outcome['name'] == home_team:
                        spread = outcome.get('point')

        # Only append if spread exists
        if spread is not None:
            rows.append({
                'Home': home_team,
                'Away': away_team,
                'Vegas_Spread': float(spread),
                'Bookmaker': selected_book['title'],
                'Commence_Time': commence_time
            })

    if not rows:
        print("⚠️ No valid spread data found.")
        return None

    df = pd.DataFrame(rows)

    # Sort by game time for clean structure
    df = df.sort_values("Commence_Time").reset_index(drop=True)

    return df


def git_push():
    try:
        subprocess.run(["git", "add", OUTPUT_FILE], check=True)
        subprocess.run(["git", "commit", "-m", f"Vegas Update {datetime.now()}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Vegas Data pushed to GitHub.")
    except subprocess.CalledProcessError:
        print("⚠️ No changes detected.")


if __name__ == "__main__":
    df = fetch_vegas_odds()
    if df is not None:
        df.to_csv(
            OUTPUT_FILE,
            index=False,
            lineterminator="\n",   # CRITICAL FIX
            encoding="utf-8"
        )
        git_push()