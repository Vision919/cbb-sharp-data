import requests
import pandas as pd
from io import StringIO
import subprocess
from datetime import datetime

# CONFIGURATION
API_KEY = 'dd4c9435af40ac6e8d2d38d54a62bfe4'
SPORT = 'basketball_ncaab' 
REGIONS = 'us' # Focus on US books (DraftKings, FanDuel, etc.)
MARKETS = 'spreads,h2h' # Get both Spread and Moneyline
ODDS_FORMAT = 'american'

def fetch_vegas_odds():
    print("📡 Requesting Live Vegas Odds...")
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return None
    
    data = response.json()
    rows = []
    
    for game in data:
        home_team = game['home_team']
        away_team = game['away_team']
        commence_time = game['commence_time']
        
        # We'll grab the first bookmaker available (usually DraftKings or FanDuel)
        if game['bookmakers']:
            bookie = game['bookmakers'][0]['title']
            markets = game['bookmakers'][0]['markets']
            
            spread = None
            for m in markets:
                if m['key'] == 'spreads':
                    # Find the spread for the home team
                    for outcome in m['outcomes']:
                        if outcome['name'] == home_team:
                            spread = outcome['point']
            
            rows.append({
                'Home': home_team,
                'Away': away_team,
                'Vegas_Spread': spread,
                'Bookmaker': bookie,
                'Commence_Time': commence_time
            })
            
    return pd.DataFrame(rows)

def git_push():
    try:
        subprocess.run(["git", "add", "vegas_odds.csv"], check=True)
        subprocess.run(["git", "commit", "-m", f"Vegas Update {datetime.now()}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Vegas Data pushed to GitHub.")
    except:
        print("⚠️ No changes in Vegas lines.")

if __name__ == "__main__":
    df = fetch_vegas_odds()
    if df is not None:
        df.to_csv("vegas_odds.csv", index=False)
        git_push()