"""
Fetches top 10 most-viewed videos from each YouTube playlist and writes results to a CSV.

Usage:
  1. Set your YouTube Data API v3 key in API_KEY below.
  2. Add playlist URLs to PLAYLISTS.
  3. Run: python3 playlist_top10.py
     Output is written to top10_views.csv.

Get a free API key at https://console.cloud.google.com/ → APIs & Services → YouTube Data API v3.
"""

import csv
import re
import sys
import requests

API_KEY = "YOUR_API_KEY_HERE"

PLAYLISTS = [
    # Add your playlist URLs here, e.g.:
    # "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx",
    # "https://www.youtube.com/playlist?list=PLyyyyyyyyyyyyyyyy",
]

OUTPUT_FILE = "top10_views.csv"
TOP_N = 10
YT_API = "https://www.googleapis.com/youtube/v3"


def extract_playlist_id(url: str) -> str:
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not find playlist ID in URL: {url}")
    return match.group(1)


def get_playlist_name(playlist_id: str) -> str:
    params = {"part": "snippet", "id": playlist_id, "key": API_KEY}
    resp = requests.get(f"{YT_API}/playlists", params=params, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return playlist_id
    return items[0]["snippet"]["title"]


def get_all_video_ids(playlist_id: str) -> list[str]:
    video_ids = []
    page_token = None
    while True:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(f"{YT_API}/playlistItems", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            vid = item["contentDetails"].get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def get_view_counts(video_ids: list[str]) -> list[int]:
    view_counts = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {"part": "statistics", "id": ",".join(chunk), "key": API_KEY}
        resp = requests.get(f"{YT_API}/videos", params=params, timeout=15)
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            views = int(item.get("statistics", {}).get("viewCount", 0))
            view_counts.append(views)
    return view_counts


def process_playlist(playlist_url: str) -> tuple[str, list[int]]:
    playlist_id = extract_playlist_id(playlist_url)
    name = get_playlist_name(playlist_id)
    print(f"  Playlist: {name}")
    video_ids = get_all_video_ids(playlist_id)
    print(f"  {len(video_ids)} videos found. Fetching view counts...")
    view_counts = get_view_counts(video_ids)
    view_counts.sort(reverse=True)
    return name, view_counts[:TOP_N]


def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("Error: set your YouTube Data API key in API_KEY before running.")
        sys.exit(1)
    if not PLAYLISTS:
        print("Error: add at least one playlist URL to PLAYLISTS before running.")
        sys.exit(1)

    rows = []
    for url in PLAYLISTS:
        print(f"Processing: {url}")
        try:
            name, top_views = process_playlist(url)
            for views in top_views:
                rows.append({"playlist_name": name, "views": views})
        except Exception as e:
            print(f"  Failed: {e}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["playlist_name", "views"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
