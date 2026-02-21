# scraper.py

import requests
import pandas as pd
from bs4 import BeautifulSoup

URL = "https://kenpom.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com",
}

def fetch_html():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text

def extract_table(html):
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table", {"id": "ratings-table"})
    if table is None:
        raise ValueError("Could not find table with id='ratings-table'")

    df = pd.read_html(str(table))[0]
    return df

def clean_table(df):
    # Store original column names
    columns = df.columns.tolist()

    # Remove duplicate header rows that appear in the body
    # These rows usually have "Rank" in the first column
    df = df[df.iloc[:, 0] != "Rank"]

    # Remove rows where entire row equals column headers
    df = df[~df.apply(lambda row: list(row) == columns, axis=1)]

    # Reset index
    df = df.reset_index(drop=True)

    return df

def save_csv(df):
    df.to_csv("kenpom_live.csv", index=False)

def main():
    html = fetch_html()
    df = extract_table(html)
    df_clean = clean_table(df)
    save_csv(df_clean)
    print("kenpom_live.csv successfully updated.")

if __name__ == "__main__":
    main()
