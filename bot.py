import os
import time
import schedule
import tweepy
from googleapiclient.discovery import build
import yt_dlp
from flask import Flask
from threading import Thread

# -----------------------------
# API Keys
# -----------------------------
TWITTER_API_KEY = "uv2JDb1wbF6cRMZZ7uETHriHj"
TWITTER_API_SECRET = "6DISax8skk4UjffbLC8WgbpxvvO9cj5uULrdNbxLg3Jdqi3ZGF"
TWITTER_ACCESS_TOKEN = "1854479517097869312-fRXvFKzAXHYawb3NpVhWjwU5hcZ18g"
TWITTER_ACCESS_SECRET = "kcETiiZca1EMXBrjzchGLkeW6G8lmFc9FrD0LWhl2rP19"
YOUTUBE_API_KEY = "AIzaSyApIgRxGNBrzzj2zibyb_TOS-gnZdQ8VOM"

# -----------------------------
# Twitter authentication
# -----------------------------
auth = tweepy.OAuth1UserHandler(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)
twitter_api = tweepy.API(auth)
print("✅ Twitter auth successful!")

# -----------------------------
# YouTube API setup
# -----------------------------
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

POSTED_FILE = "posted_videos.txt"

def load_posted_ids():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_posted_id(video_id):
    with open(POSTED_FILE, "a") as f:
        f.write(video_id + "\n")

# -----------------------------
# Bot logic
# -----------------------------
def get_safe_short():
    posted_ids = load_posted_ids()
    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        chart="mostPopular",
        regionCode="US",
        maxResults=20
    )
    response = request.execute()

    for item in response.get("items", []):
        video_id = item["id"]
        title = item["snippet"]["title"]
        duration = item["contentDetails"]["duration"]
        license_type = item["contentDetails"].get("licensedContent", False)

        if video_id in posted_ids or license_type:
            continue
        if any(word in title.lower() for word in ["music", "official", "trailer", "vevo"]):
            continue
        if "M" in duration:
            continue
        seconds = int(duration.replace("PT", "").replace("S", "") or 0)
        if seconds > 60:
            continue

        video_url = f"https://youtu.be/{video_id}"
        return title, video_url, video_id

    return None, None, None

def download_video(url):
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': 'video.mp4',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "video.mp4"

def post_to_twitter(title, video_path):
    media = twitter_api.media_upload(video_path)
    twitter_api.update_status(status=title, media_ids=[media.media_id])
    print(f"✅ Posted: {title}")

def job():
    print("🔍 Searching for safe short...")
    for _ in range(3):  # Post 3 videos per job
        title, url, vid_id = get_safe_short()
        if not url:
            print("⚠ No safe video found this round.")
            continue
        print(f"🎯 Found: {title} ({url})")
        video_file = download_video(url)
        post_to_twitter(title, video_file)
        os.remove(video_file)
        save_posted_id(vid_id)
        time.sleep(10)  # Short delay between posts

# -----------------------------
# Schedule job in a separate thread
# -----------------------------
def run_schedule():
    # 3 posts/day → every 8 hours
    schedule.every(8).hours.do(job)
    print("🚀 Bot scheduler started! Posting 3 videos/day...")
    while True:
        schedule.run_pending()
        time.sleep(10)

Thread(target=run_schedule).start()

# -----------------------------
# Flask web server to stay awake
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot is alive!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
