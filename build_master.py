import pandas as pd
import json
import os

def build_master_payload():
    print("📦 Packing data into Master Payload (Priority Order)...")
    
    # We define the order here. JSON will follow this sequence.
    # Smallest/Most critical data first to avoid truncation.
    payload_order = [
        ("slate", "active_slate.csv"),
        ("vegas_odds", "vegas_odds.csv"),
        ("kenpom", "efficiency.csv"),   # Ensure your team file is named efficiency.csv
        ("players", "player_stats.csv")
    ]

    master_data = {}
    found_any = False

    for key, filename in payload_order:
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)
                # Convert to list of dicts
                master_data[key] = df.to_dict(orient='records')
                print(f"✅ Added {key} ({len(df)} rows)")
                found_any = True
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")
        else:
            print(f"⚠️ Warning: {filename} not found. Skipping {key}.")

    if found_any:
        # Save to JSON
        with open("master_data.json", "w") as f:
            # We don't use indent here to save space/tokens, 
            # but if you want it pretty, add indent=4
            json.dump(master_data, f) 
        
        print("\n🚀 master_data.json reordered and ready!")
        print("Structure: [Slate] -> [Vegas] -> [KenPom] -> [Players]")
    else:
        print("\n❌ No data found to pack.")

if __name__ == "__main__":
    build_master_payload()