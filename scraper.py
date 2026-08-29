import os
import json
import csv
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ওয়েবসাইটের বেজ URL
BASE_URL = "[https://hamyra.vercel.app](https://hamyra.vercel.app)"
MOVIES_URL = f"{BASE_URL}/movies"

# ক্লাউডফ্লেয়ার বা রিকোয়েস্ট ব্লক এড়াতে হেডার
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
}

def fetch_page(url):
    """নির্দিষ্ট URL থেকে HTML পেইজ সংগ্রহ করে"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as err:
        print(f"❌ URL লোড করতে ব্যর্থ: {url} | এরর: {err}")
        return None

def extract_movie_details(detail_url):
    """মুভির বিস্তারিত পেইজ থেকে ডাউনলোড এবং ওয়াচ লিংক বের করে"""
    soup = fetch_page(detail_url)
    download_links = []
    
    if not soup:
        return download_links

    # ডাউনলোড টেক্সট বা ফাইল শেয়ারিং প্ল্যাটফর্মের লিঙ্ক খোঁজা
    all_links = soup.find_all('a', href=True)
    for a in all_links:
        href = a['href']
        text = a.text.strip().lower()
        
        # ডাউনলোড বা ড্রাইভ লিংকের কিওয়ার্ড ফিল্টারিং
        if any(keyword in href.lower() or keyword in text for keyword in [
            'download', 'drive.google', 'mega.nz', '1080p', '720p', '480p', 'fast', 'direct', 'stream', 'play'
        ]):
            full_dl_link = urljoin(BASE_URL, href)
            if full_dl_link not in download_links:
                download_links.append(full_dl_link)

    return download_links

def scrape_all_movies():
    """সকল মুভি তথ্য স্ক্র্যাপ করার মূল ফাংশন"""
    print(f"🚀 স্ক্র্যাপিং শুরু হচ্ছে: {MOVIES_URL}")
    soup = fetch_page(MOVIES_URL)
    
    movies_list = []
    if not soup:
        print("❌ মুভি পেইজ ওপেন করা সম্ভব হয়নি।")
        return movies_list

    # কার্ড এবং লিঙ্ক সিলেক্টর সনাক্তকরণ
    movie_cards = soup.find_all(['a', 'div', 'article'])
    visited_urls = set()
    counter = 1

    for card in movie_cards:
        try:
            # লিঙ্ক বের করা
            movie_link = None
            if card.name == 'a' and card.has_attr('href'):
                movie_link = card['href']
            else:
                find_a = card.find('a', href=True)
                if find_a:
                    movie_link = find_a['href']

            if not movie_link or movie_link in visited_urls or '/movie' not in movie_link:
                continue

            visited_urls.add(movie_link)
            watch_url = urljoin(BASE_URL, movie_link)

            # টাইটেল সংগ্রহ
            title = ""
            title_tag = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'span'])
            if title_tag:
                title = title_tag.text.strip()
            
            # ইমেজ/পোস্টার URL সংগ্রহ
            img_url = ""
            img_tag = card.find('img')
            if img_tag:
                img_url = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('srcset', '').split(' ')[0]
                if img_url:
                    img_url = urljoin(BASE_URL, img_url)

            print(f"🔍 [{counter}] প্রসেস করা হচ্ছে: {title if title else watch_url}")

            # বিস্তারিত লিঙ্ক থেকে ডাউনলোড অপশন ফিল্টার
            downloads = extract_movie_details(watch_url)

            movie_data = {
                "id": counter,
                "title": title if title else f"Movie_{counter}",
                "image_url": img_url,
                "watch_url": watch_url,
                "download_links": downloads if downloads else [watch_url]
            }

            movies_list.append(movie_data)
            counter += 1
            
            # সার্ভার ব্যাক-অফ সময়
            time.sleep(0.8)

        except Exception as e:
            print(f"⚠️ ত্রুটি দেখা দিয়েছে: {e}")
            continue

    return movies_list

def save_data(data):
    """JSON এবং CSV দুটো ফরম্যাটেই তথ্য সেভ করে"""
    if not data:
        print("⚠️ সেভ করার মতো কোনো ডাটা পাওয়া যায়নি।")
        return

    # JSON ফরম্যাটে সেভ
    with open("movies.json", "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)
    print("✅ 'movies.json' ফাইল সফলভাবে তৈরি হয়েছে।")

    # CSV ফরম্যাটে সেভ
    fields = ["id", "title", "image_url", "watch_url", "download_links"]
    with open("movies.csv", "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for item in data:
            item_copy = item.copy()
            item_copy["download_links"] = " | ".join(item_copy["download_links"])
            writer.writerow(item_copy)
    print("✅ 'movies.csv' ফাইল সফলভাবে তৈরি হয়েছে।")

if __name__ == "__main__":
    data = scrape_all_movies()
    save_data(data)
