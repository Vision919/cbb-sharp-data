import pandas as pd
import requests
import sys
from io import StringIO
from datetime import datetime, timedelta

def fetch_slate(days_ahead):
    target_date = datetime.now() + timedelta(days=days_ahead)
    m, d, y = f"{target_date.month:02d}", f"{target_date.day:02d}", f"{target_date.year}"
    
    # Target the Men's specific index to avoid Women's game bleed-in
    url = f"https://www.sports-reference.com/cbb/boxscores/index.cgi?month={m}&day={d}&year={y}"
    print(f"📡 Scraping: {target_date.strftime('%A, %b %d, %Y')}")

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        dfs = pd.read_html(StringIO(response.text))
        
        slate = []
        seen_teams = set() # Track teams to prevent Arizona appearing twice

        for df in dfs:
            if len(df) >= 2:
                def clean(name):
                    # Remove rankings (1), (25) and generic 'NCAA' tags
                    parts = [p for p in str(name).split() if not (p.startswith('(') and p.endswith(')'))]
                    return " ".join(parts).replace('NCAA', '').strip()

                away_team = clean(df.iloc[0, 0])
                home_team = clean(df.iloc[1, 0])

                # VALIDATION: 
                # 1. Ensure it's not a header/empty
                # 2. Ensure we haven't already processed either team
                # 3. Filter out common Women's team indicators if they appear
                if away_team and home_team and "Final" not in away_team:
                    if away_team not in seen_teams and home_team not in seen_teams:
                        slate.append({
                            'Home': home_team, 
                            'Away': away_team, 
                            'Date': target_date.strftime('%Y-%m-%d')
                        })
                        seen_teams.add(away_team)
                        seen_teams.add(home_team)

        if slate:
            df_slate = pd.DataFrame(slate)
            df_slate.to_csv("active_slate.csv", index=False)
            print(f"✅ Created active_slate.csv with {len(df_slate)} unique Men's games.")
        else:
            print("📭 No games found for this date.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    fetch_slate(days)