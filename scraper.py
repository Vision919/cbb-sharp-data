from seleniumbase import SB
import pandas as pd
from io import StringIO
import subprocess
from datetime import datetime

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
        # Column 1 is typically "Team" — filter out any header-like rows
        df = df[df.iloc[:, 1].astype(str) != "Team"].copy()

        # --- CLEAN KENPOM OUTPUT (overwrite kenpom_live.csv) ---

        # If KenPom table comes in with a MultiIndex header, flatten it.
        # We keep the 2nd level names (e.g., Team, Conf, NetRtg, ORtg...)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[1]).strip() for c in df.columns]
        else:
            df.columns = [str(c).strip() for c in df.columns]

        # Remove repeated header rows (some tables repeat "Team" in the body)
        df = df[df["Team"].astype(str) != "Team"].copy()

        # Keep only the first occurrence of each column name
        df = df.loc[:, ~pd.Index(df.columns).duplicated()].copy()

        # REQUIRED columns (value columns)
        required = ["Team", "Conf", "NetRtg", "ORtg", "DRtg", "AdjT", "Luck"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise RuntimeError(f"KenPom table missing columns after flattening: {missing}. Columns found: {list(df.columns)}")

        # Select only the columns we need
        df = df[required].copy()

        # Convert numerics
        for col in ["NetRtg", "ORtg", "DRtg", "AdjT", "Luck"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop rows missing core numerics
        df = df.dropna(subset=["NetRtg", "ORtg", "DRtg", "AdjT"]).reset_index(drop=True)

        # Save clean file (overwrite)
        df.to_csv("kenpom_live.csv", index=False)

        print(f"✅ Successfully logged {len(df)} teams.")
        return True

def git_push():
    try:
        subprocess.run(["git", "add", "kenpom_live.csv"], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"KenPom Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True
        )
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("🚀 GitHub Updated.")
    except Exception as e:
        print(f"⚠️ GitHub push skipped or failed: {e}")

if __name__ == "__main__":
    if scrape_kenpom():
        git_push()