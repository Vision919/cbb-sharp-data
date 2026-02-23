from seleniumbase import SB
import pandas as pd
from io import StringIO
import subprocess

def scrape_kenpom():
    # 'uc=True' triggers the undetected mode
    # 'headless=True' keeps it in the background
    with SB(uc=True, headless=True) as sb:
        print("Scouting KenPom... (Stealth Mode Active)")
        sb.open("https://kenpom.com/")
        
        # Wait for the table to actually appear
        sb.wait_for_element("#ratings-table", timeout=20)
        
        # Grab the table HTML
        table_html = sb.get_element("#ratings-table").get_attribute("outerHTML")
        
        # Use Pandas to parse
        df = pd.read_html(StringIO(table_html))[0]
        
        # Clean up KenPom's repeated header rows
        df = df[df.iloc[:, 1] != "Team"]
        
        # Save to CSV
        df.to_csv("kenpom_live.csv", index=False)
        print(f"✅ Successfully logged {len(df)} teams.")
        return True

def git_push():
    try:
        subprocess.run(["git", "add", "kenpom_live.csv"], check=True)
        subprocess.run(["git", "commit", "-m", f"KenPom Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub Updated.")
    except Exception as e:
        print("⚠️ GitHub push skipped (no changes or git not configured).")

if __name__ == "__main__":
    if scrape_kenpom():
        git_push()