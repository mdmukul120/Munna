import os
import json
import csv
import time
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "[https://hamyra.vercel.app](https://hamyra.vercel.app)"
MOVIES_URL = f"{BASE_URL}/movies"

OUTPUT_DIR = "data"

def ensure_directory():
    """ফাইল সেভ করার জন্য ফোল্ডার তৈরি করে"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def sanitize_filename(name):
    """ক্যাটাগরির নাম দিয়ে নিরাপদ ফাইলনাম তৈরি করে"""
    return re.sub(r'[^\w\-_]', '_', name.strip().lower())

def scrape_hamyra_movies():
    print("🚀 প্রিমিয়াম প্লে-রাইট ব্রাউজার ইঞ্জিন চালু হচ্ছে...")
    ensure_directory()
    
    all_movies = []
    categories = {}

    with sync_playwright() as p:
        # হেডলেস ব্রাউজার কনফিগারেশন
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        print(f"📡 পেইজ লোড করা হচ্ছে: {MOVIES_URL}")
        try:
            page.goto(MOVIES_URL, wait_until="networkidle", timeout=60000)
            time.sleep(3) # ডায়নামিক কনটেন্ট লোড নিশ্চিত করতে অপেক্ষা
        except Exception as e:
            print(f"⚠️ প্রাথমিক লোডে সমস্যা: {e}")

        # অটোমেটিক স্ক্রলিং যাতে সব লেজি-লোড কনটেন্ট দৃশ্যমান হয়
        print("📜 স্ক্রলিং করে সকল ডায়নামিক মুভি লোড করা হচ্ছে...")
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # মুভি কার্ড নির্বাচন
        movie_elements = page.query_selector_all("a[href*='/movie'], a[href*='/watch'], div.movie-card, article")
        print(f"🎯 মোট সম্ভাবনাযুক্ত উপাদান পাওয়া গেছে: {len(movie_elements)}")

        visited_links = set()
        count = 1

        for elem in movie_elements:
            try:
                href = elem.get_attribute("href")
                if not href:
                    child_a = elem.query_selector("a")
                    if child_a:
                        href = child_a.get_attribute("href")

                if not href or href in visited_links:
                    continue

                full_watch_url = urljoin(BASE_URL, href)
                visited_links.add(href)

                # টাইটেল নিষ্কাশন
                title = elem.inner_text().strip().split("\n")[0] if elem.inner_text() else ""
                
                # ইমেজ URL নিষ্কাশন
                img_elem = elem.query_selector("img")
                img_url = ""
                if img_elem:
                    img_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-src") or ""
                    if img_url:
                        img_url = urljoin(BASE_URL, img_url)

                # ক্যাটাগরি ফিল্টারিং (যদি ট্যাগ বা ব্যাজ থাকে)
                category_elem = elem.query_selector(".category, .genre, .tag, span.badge")
                category_name = category_elem.inner_text().strip() if category_elem else "Uncategorized"

                # মুভির নির্দিষ্ট পেজে গিয়ে ডিটেইল ও ডাউনলোড লিংক সংগ্রহ
                detail_page = context.new_page()
                download_links = []
                try:
                    detail_page.goto(full_watch_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(1.5)
                    
                    # ডাউনলোড লিংক এলিমেন্ট নির্বাচন
                    dl_elements = detail_page.query_selector_all("a[href*='drive'], a[href*='mega'], a[href*='download'], a[href*='link'], button")
                    for dl in dl_elements:
                        dl_href = dl.get_attribute("href")
                        if dl_href and dl_href.startswith("http"):
                            download_links.append(dl_href)
                except Exception as ex:
                    print(f"⚠️ ডিটেইল পেজ ব্রাউজ করতে সমস্যা: {full_watch_url}")
                finally:
                    detail_page.close()

                # যদি কোনো ডাউনলোড লিঙ্ক না পাওয়া যায় তবে ওয়াচ লিঙ্কই ডিফল্ট
                if not download_links:
                    download_links.append(full_watch_url)

                movie_data = {
                    "id": count,
                    "title": title if title else f"Movie_{count}",
                    "category": category_name,
                    "image_url": img_url,
                    "watch_url": full_watch_url,
                    "download_links": list(set(download_links))
                }

                all_movies.append(movie_data)

                # ক্যাটাগরি অনুযায়ী আলাদা তালিকা সংগঠিতকরণ
                cat_key = sanitize_filename(category_name)
                if cat_key not in categories:
                    categories[cat_key] = []
                categories[cat_key].append(movie_data)

                print(f"✅ [{count}] সফলভাবে স্ক্র্যাপ করা হয়েছে: {movie_data['title']} ({category_name})")
                count += 1

            except Exception as e:
                print(f"❌ কার্ড প্রসেসিং এরর: {e}")
                continue

        browser.close()

    return all_movies, categories

def save_all_data(all_movies, categories):
    """মেইন ফাইল এবং ক্যাটাগরি ভিত্তিক ফাইল সেভ করে"""
    ensure_directory()

    # ১. মেইন JSON ফাইল (রুট ফোল্ডারে ও ডাটা ফোল্ডারে)
    main_json_path = "movies.json"
    with open(main_json_path, "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=4)
    print(f"💾 রুট ফাইলে মূল তথ্য সংরক্ষিত: {main_json_path}")

    # ২. মেইন CSV ফাইল
    main_csv_path = "movies.csv"
    fields = ["id", "title", "category", "image_url", "watch_url", "download_links"]
    with open(main_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in all_movies:
            row = item.copy()
            row["download_links"] = " | ".join(row["download_links"])
            writer.writerow(row)
    print(f"💾 মূল CSV ফাইল তৈরি সম্পন্ন: {main_csv_path}")

    # ৩. ক্যাটাগরি অনুযায়ী আলাদা ফাইল তৈরি
    for cat_name, movies in categories.items():
        cat_file_json = os.path.join(OUTPUT_DIR, f"category_{cat_name}.json")
        with open(cat_file_json, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False, indent=4)
        print(f"📁 ক্যাটাগরি ফাইল প্রস্তুত: {cat_file_json}")

if __name__ == "__main__":
    movies, categories = scrape_hamyra_movies()
    save_all_data(movies, categories)
