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


def get_video_stats(video_ids: list[str]) -> list[dict]:
    videos = []
    # API allows up to 50 IDs per request
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "part": "snippet,statistics",
            "id": ",".join(chunk),
            "key": API_KEY,
        }
        resp = requests.get(f"{YT_API}/videos", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            view_count = int(stats.get("viewCount", 0))
            videos.append(
                {
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "views": view_count,
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
            )
    return videos


def process_playlist(playlist_url: str) -> list[dict]:
    playlist_id = extract_playlist_id(playlist_url)
    print(f"  Fetching video IDs for playlist {playlist_id}...")
    video_ids = get_all_video_ids(playlist_id)
    print(f"  Found {len(video_ids)} videos. Fetching stats...")
    videos = get_video_stats(video_ids)
    videos.sort(key=lambda v: v["views"], reverse=True)
    top = videos[:TOP_N]
    for rank, v in enumerate(top, start=1):
        v["rank"] = rank
        v["playlist_url"] = playlist_url
    return top


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
            top10 = process_playlist(url)
            rows.extend(top10)
            print(f"  Done. Top video: {top10[0]['title']} ({top10[0]['views']:,} views)")
        except Exception as e:
            print(f"  Failed: {e}")

    fieldnames = ["playlist_url", "rank", "title", "views", "url"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
