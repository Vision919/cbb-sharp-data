import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
import subprocess
import time
import os
import json

def save_checkpoint(processed, data):
    with open("scrape_progress.json", 'w') as f:
        json.dump({'processed': processed, 'data': data}, f)

def scrape_stars():
    print("🚀 Initializing Resilient Crawler (V2.9)...")
    base_url = "https://www.sports-reference.com"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
    
    conf_slugs = [
        'acc', 'sec', 'big-12', 'big-ten', 'big-east', 'mwc', 'american', 'atlantic-10', 
        'wcc', 'sun-belt', 'mac', 'cusa', 'horizon', 'mvc', 'maac', 'southland', 'summit', 
        'wac', 'big-sky', 'big-south', 'big-west', 'caa', 'ivy', 'meac', 'nec', 'ovc', 
        'patriot', 'southern', 'swac', 'asun', 'america-east'
    ]

    progress_file = "scrape_progress.json"
    processed_confs = []
    all_data = []

    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            checkpoint = json.load(f)
            processed_confs = checkpoint.get('processed', [])
            all_data = checkpoint.get('data', [])
        print(f"⏯ Resuming from checkpoint ({len(processed_confs)} conferences finished)...")

    for slug in conf_slugs:
        if slug in processed_confs:
            continue

        url = f"{base_url}/cbb/conferences/{slug}/men/2026-stats.html"
        print(f"📡 Scraping {slug.upper()} (Waiting 10s for safety)...")
        time.sleep(10) 
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                print("🛑 429 ERROR: IP is still blocked. Use a Hotspot/VPN or wait 1 hour.")
                save_checkpoint(processed_confs, all_data)
                return False
            
            if response.status_code != 200:
                print(f"⚠️ Skipping {slug} (Status: {response.status_code})")
                processed_confs.append(slug)
                continue
                
            # IMPORTANT FIX: This strips HTML comments so pandas can see the hidden tables
            clean_html = response.text.replace("", "")
            dfs = pd.read_html(StringIO(clean_html))
            
            found_stats = False
            for df in dfs:
                if 'Player' in df.columns and 'PTS' in df.columns:
                    df['PTS'] = pd.to_numeric(df['PTS'], errors='coerce')
                    df['AST'] = pd.to_numeric(df['AST'], errors='coerce')
                    
                    team_col = 'Team' if 'Team' in df.columns else 'School'
                    
                    for team, group in df.groupby(team_col):
                        clean_team = str(team).replace(' NCAA', '')
                        
                        # Top 2 Scorers
                        top_scorers = group.nlargest(2, 'PTS')
                        for _, row in top_scorers.iterrows():
                            all_data.append({'Team': clean_team, 'Player': row['Player'], 'Value': row['PTS'], 'Type': 'PPG'})
                        
                        # Top Passer
                        top_passer = group.nlargest(1, 'AST')
                        for _, row in top_passer.iterrows():
                            all_data.append({'Team': clean_team, 'Player': row['Player'], 'Value': row['AST'], 'Type': 'APG'})
                    
                    found_stats = True
                    break
            
            if found_stats:
                print(f"✅ {slug.upper()} successful.")
            processed_confs.append(slug)
            save_checkpoint(processed_confs, all_data)

        except Exception as e:
            print(f"⚠️ Error on {slug}: {e}")

    if all_data:
        final_df = pd.DataFrame(all_data).drop_duplicates()
        final_df.to_csv("player_stats.csv", index=False)
        if os.path.exists(progress_file): os.remove(progress_file)
        print("✨ Success! player_stats.csv is complete.")
        return True
    return False

def git_push():
    try:
        subprocess.run(["git", "add", "player_stats.csv"], check=True)
        subprocess.run(["git", "commit", "-m", "V2.9 Final Corrected Scrape"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub updated.")
    except: pass

if __name__ == "__main__":
    if scrape_stars():
        git_push()