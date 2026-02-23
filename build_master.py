import pandas as pd
import json
import os

def build_master_payload():
    print("📦 Packing all data into master_data.json...")
    
    payload = {}

    # Update these names if your actual files are named differently!
    files = {
        "efficiency": "efficiency.csv", 
        "players": "player_stats.csv",
        "odds": "vegas_odds.csv",
        "slate": "active_slate.csv"
    }

    found_at_least_one = False

    for key, filename in files.items():
        if os.path.exists(filename):
            try:
                # Load CSV and convert to a list of dictionaries
                df = pd.read_csv(filename)
                payload[key] = df.to_dict(orient='records')
                print(f"✅ Added {filename} to payload.")
                found_at_least_one = True
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")
        else:
            print(f"⚠️ Warning: {filename} not found. Skipping.")

    if found_at_least_one:
        # Save as one big JSON file
        with open("master_data.json", "w") as f:
            json.dump(payload, f, indent=4)
        print("\n🚀 master_data.json is ready for Claude!")
    else:
        print("\n❌ No CSV files were found. Nothing to pack.")

if __name__ == "__main__":
    build_master_payload()