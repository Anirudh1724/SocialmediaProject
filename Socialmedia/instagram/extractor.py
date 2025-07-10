import time
import os
import cv2
import easyocr
import getpass
import re
import json
import csv
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def login(driver, username, password):
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(5)

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
    
    driver.find_element(By.NAME, "username").send_keys(username)
    time.sleep(1)
    driver.find_element(By.NAME, "password").send_keys(password)
    time.sleep(1)
    driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
    print(" Logging in...")

    WebDriverWait(driver, 30).until(
        lambda d: "instagram.com" in d.current_url and "login" not in d.current_url
    )
    print(" Login successful.")
    time.sleep(3)
    
    try:
        driver.find_element(By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]").click()
        time.sleep(2)
    except:
        pass

def extract_profile_details(driver, username):
    """Extract basic profile information"""
    profile_url = f"https://www.instagram.com/{username}/"
    driver.get(profile_url)
    time.sleep(7)
    
    print(f" Extracting profile details for {username}...")
    
    profile_data = {
        'username': username,
        'posts': 'Not Found',
        'followers': 'Not Found',
        'following': 'Not Found',
        'verified': 'No',
        'bio': 'Not Found',
        'profile_pic_url': 'Not Found',
        'full_name': 'Not Found'
    }
    
    try:
        # Extract post count, followers, following
        stats_selectors = [
            '//header//section//ul//li',
            '//header//ul//li',
            '//main//header//ul//li'
        ]
        
        for selector in stats_selectors:
            try:
                stats_elements = driver.find_elements(By.XPATH, selector)
                if len(stats_elements) >= 3:
                    # First element is usually posts
                    posts_text = stats_elements[0].text.strip()
                    profile_data['posts'] = extract_number_from_text(posts_text)
                    
                    # Second element is usually followers
                    followers_text = stats_elements[1].text.strip()
                    profile_data['followers'] = extract_number_from_text(followers_text)
                    
                    # Third element is usually following
                    following_text = stats_elements[2].text.strip()
                    profile_data['following'] = extract_number_from_text(following_text)
                    break
            except:
                continue
        
        # Check if verified
        try:
            verified_element = driver.find_element(By.XPATH, "//*[contains(@title, 'Verified') or contains(@aria-label, 'Verified')]")
            profile_data['verified'] = 'Yes'
        except:
            pass
        
        # Extract full name
        try:
            name_selectors = [
                "//header//h2",
                "//header//h1",
                "//span[contains(@class, 'x1lliihq')]"
            ]
            for selector in name_selectors:
                try:
                    name_element = driver.find_element(By.XPATH, selector)
                    if name_element.text and name_element.text != username:
                        profile_data['full_name'] = name_element.text
                        break
                except:
                    continue
        except:
            pass
        
        # Extract bio
        try:
            bio_selectors = [
                "//header//div[contains(@class, 'bio')]//span",
                "//header//*[contains(@class, '-webkit-box')]",
                "//div[contains(@class, 'x7a106z')]//span"
            ]
            for selector in bio_selectors:
                try:
                    bio_element = driver.find_element(By.XPATH, selector)
                    if bio_element.text and len(bio_element.text) > 5:
                        profile_data['bio'] = bio_element.text
                        break
                except:
                    continue
        except:
            pass
        
        # Extract profile picture URL
        try:
            img_element = driver.find_element(By.XPATH, "//header//img")
            profile_data['profile_pic_url'] = img_element.get_attribute('src')
        except:
            pass
    
    except Exception as e:
        print(f" Error extracting profile details: {e}")
    
    return profile_data

def extract_number_from_text(text):
    """Extract number from text like '1.2K posts' or '500 followers'"""
    if not text:
        return 0
    
    text = str(text).replace(',', '').lower()
    
    patterns = [
        r'(\d+\.?\d*)\s*k',
        r'(\d+\.?\d*)\s*m',
        r'(\d+\.?\d*)\s*b',
        r'(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            num = float(match.group(1))
            if 'k' in text:
                return int(num * 1000)
            elif 'm' in text:
                return int(num * 1000000)
            elif 'b' in text:
                return int(num * 1000000000)
            else:
                return int(num)
    
    return 0

def collect_all_posts(driver, username, expected_post_count=None):
    """Scroll through profile and collect ALL post URLs with improved scrolling"""
    profile_url = f"https://www.instagram.com/{username}/"
    driver.get(profile_url)
    time.sleep(5)
    
    print(f" Collecting ALL posts from {username}...")
    if expected_post_count:
        print(f" Expected posts from profile: {expected_post_count}")
    
    # Scroll to posts section
    driver.execute_script("window.scrollTo(0, 800);")
    time.sleep(3)
    
    collected_urls = set()
    scroll_attempts = 0
    max_scrolls_without_progress = 10  # Increased patience for finding posts
    consecutive_no_progress = 0
    last_height = 0
    
    # Get initial scroll height
    current_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Find all post links
        post_elements = driver.find_elements(By.XPATH, '//a[contains(@href,"/p/") or contains(@href,"/reel/")]')
        
        before_count = len(collected_urls)
        
        for post_element in post_elements:
            href = post_element.get_attribute("href")
            if href and ("/p/" in href or "/reel/" in href):
                collected_urls.add(href)
        
        current_count = len(collected_urls)
        new_posts_found = current_count - before_count
        
        print(f" Progress: {current_count} posts collected (found {new_posts_found} new posts)")
        
        # Check if we found the expected number of posts
        if expected_post_count and current_count >= expected_post_count:
            print(f" Found all expected posts ({current_count}/{expected_post_count})")
            break
        
        # Scroll down using multiple methods for better coverage
        last_height = current_height
        
        # Method 1: Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Method 2: Scroll by viewport height
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(1)
        
        # Method 3: Try to click "Show more posts" or similar buttons
        try:
            show_more_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Show more') or contains(text(), 'Load more') or contains(text(), 'See more')]")
            for button in show_more_buttons:
                try:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(2)
                    break
                except:
                    continue
        except:
            pass
        
        # Check if page height changed (indicating new content loaded)
        current_height = driver.execute_script("return document.body.scrollHeight")
        
        if current_height == last_height and new_posts_found == 0:
            consecutive_no_progress += 1
            print(f" No progress... Attempt {consecutive_no_progress}/{max_scrolls_without_progress}")
            
            if consecutive_no_progress >= max_scrolls_without_progress:
                print(f" Trying alternative scroll method...")
                # Try aggressive scrolling
                for i in range(5):
                    driver.execute_script(f"window.scrollTo(0, {current_height + (i * 1000)});")
                    time.sleep(1)
                
                # Check one more time for new posts
                post_elements = driver.find_elements(By.XPATH, '//a[contains(@href,"/p/") or contains(@href,"/reel/")]')
                final_check_count = len(collected_urls)
                
                for post_element in post_elements:
                    href = post_element.get_attribute("href")
                    if href and ("/p/" in href or "/reel/" in href):
                        collected_urls.add(href)
                
                if len(collected_urls) == final_check_count:
                    print(f" Reached end of posts. No more content to load.")
                    break
                else:
                    consecutive_no_progress = 0  # Reset if we found new posts
        else:
            consecutive_no_progress = 0  # Reset counter if we made progress
        
        scroll_attempts += 1
        
        # Safety net to prevent infinite scrolling
        if scroll_attempts > 200:  # Increased limit for profiles with many posts
            print(f" Reached maximum scroll attempts ({scroll_attempts})")
            break
        
        # Longer pause for very large profiles
        if current_count > 1000:
            time.sleep(3)
        elif current_count > 500:
            time.sleep(2)
    
    post_urls = list(collected_urls)
    print(f" Collected {len(post_urls)} total posts")
    print(f" Expected: {expected_post_count}, Found: {len(post_urls)}")
    
    if expected_post_count and len(post_urls) < expected_post_count * 0.9:  # If we found less than 90% of expected
        print(f" Warning: Found fewer posts than expected. This might indicate:")
        print(f"   - Some posts are private/restricted")
        print(f"   - Profile has stories/highlights counted in post count")
        print(f"   - Instagram's layout changed")
    
    return post_urls

def analyze_single_post(driver, post_url, post_index, total_posts):
    """Analyze a single post and extract all details"""
    try:
        print(f" Analyzing post {post_index}/{total_posts}: {post_url}")
        driver.get(post_url)
        time.sleep(4)
        
        post_data = {
            'url': post_url,
            'type': 'reel' if '/reel/' in post_url else 'post',
            'likes': 0,
            'comments': 0,
            'shares': 0,
            'views': 0,
            'caption': 'Not Found',
            'hashtags': [],
            'mentions': [],
            'location': 'Not Found',
            'timestamp': 'Not Found'
        }
        
        # Extract likes
        like_selectors = [
            "//section//button[contains(@aria-label, 'like')]//span",
            "//span[contains(text(), 'likes')]",
            "//a[contains(@href, '/liked_by/')]",
            "//*[contains(text(), 'likes')]"
        ]
        
        for selector in like_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    likes = extract_number_from_text(element.text)
                    if likes > 0:
                        post_data['likes'] = likes
                        break
                if post_data['likes'] > 0:
                    break
            except:
                continue
        
        # Extract comments count
        comment_selectors = [
            "//span[contains(text(), 'comments')]",
            "//a[contains(text(), 'View all')]//span",
            "//button[contains(@aria-label, 'Comment')]//span"
        ]
        
        for selector in comment_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    comments = extract_number_from_text(element.text)
                    if comments > 0:
                        post_data['comments'] = comments
                        break
                if post_data['comments'] > 0:
                    break
            except:
                continue
        
        # Extract views (for reels/videos)
        view_selectors = [
            "//span[contains(text(), 'views')]",
            "//*[contains(text(), 'views')]",
            "//div[contains(@class, 'view')]//span"
        ]
        
        for selector in view_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    views = extract_number_from_text(element.text)
                    if views > 0:
                        post_data['views'] = views
                        break
                if post_data['views'] > 0:
                    break
            except:
                continue
        
        # Extract caption and content
        caption_selectors = [
            "//article//div[contains(@class, 'caption')]//span",
            "//div[contains(@data-testid, 'post-caption')]//span",
            "//div[contains(@class, 'C4VMK')]//span",
            "//article//ul//div//span"
        ]
        
        for selector in caption_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > 5:
                        post_data['caption'] = text
                        
                        # Extract hashtags
                        hashtags = re.findall(r'#\w+', text)
                        post_data['hashtags'] = hashtags
                        
                        # Extract mentions
                        mentions = re.findall(r'@\w+', text)
                        post_data['mentions'] = mentions
                        break
                if post_data['caption'] != 'Not Found':
                    break
            except:
                continue
        
        # Extract location
        try:
            location_element = driver.find_element(By.XPATH, "//a[contains(@href, '/locations/')]")
            post_data['location'] = location_element.text
        except:
            pass
        
        # Extract timestamp
        try:
            time_element = driver.find_element(By.XPATH, "//time")
            post_data['timestamp'] = time_element.get_attribute('datetime') or time_element.get_attribute('title')
        except:
            pass
        
        # Take screenshot of the post (optional for large datasets)
        if post_index <= 100:  # Only take screenshots for first 100 posts to save space
            os.makedirs("screenshots/posts", exist_ok=True)
            screenshot_path = f"screenshots/posts/post_{post_index}.png"
            driver.save_screenshot(screenshot_path)
            post_data['screenshot_path'] = screenshot_path
        
        return post_data
        
    except Exception as e:
        print(f" Error analyzing post {post_index}: {e}")
        return None

def extract_from_screenshot(image_path):
    """Extract additional data from screenshot using OCR as backup"""
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        img = cv2.imread(image_path)
        results = reader.readtext(img)
        texts = [text[1] for text in results if len(text) > 1]
        
        ocr_data = {
            'likes_ocr': 0,
            'comments_ocr': 0,
            'views_ocr': 0,
            'text_content': ' '.join(texts)
        }
        
        for text in texts:
            text_lower = text.lower()
            if 'like' in text_lower:
                ocr_data['likes_ocr'] = extract_number_from_text(text)
            elif 'comment' in text_lower:
                ocr_data['comments_ocr'] = extract_number_from_text(text)
            elif 'view' in text_lower:
                ocr_data['views_ocr'] = extract_number_from_text(text)
        
        return ocr_data
        
    except Exception as e:
        return {'likes_ocr': 0, 'comments_ocr': 0, 'views_ocr': 0, 'text_content': ''}

def save_profile_to_csv(profile_data, filename):
    """Save profile data to CSV file"""
    profile_df = pd.DataFrame([profile_data])
    profile_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Profile data saved to {filename}")

def save_posts_to_csv(posts_data, filename):
    """Save posts data to CSV file with proper handling of lists"""
    if not posts_data:
        print(" No posts data to save")
        return
    
    # Prepare data for CSV - convert lists to strings for CSV compatibility
    csv_posts_data = []
    for post in posts_data:
        if post:
            csv_post = post.copy()
            # Convert lists to comma-separated strings
            csv_post['hashtags'] = ', '.join(post['hashtags']) if post['hashtags'] else ''
            csv_post['mentions'] = ', '.join(post['mentions']) if post['mentions'] else ''
            csv_posts_data.append(csv_post)
    
    # Create DataFrame and save to CSV
    posts_df = pd.DataFrame(csv_posts_data)
    posts_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Posts data saved to {filename}")

def save_summary_to_csv(profile_data, posts_data, filename):
    """Save analysis summary to CSV file"""
    if not posts_data:
        summary_data = {
            'total_posts_analyzed': 0,
            'total_likes': 0,
            'total_comments': 0,
            'total_views': 0,
            'average_likes': 0,
            'average_comments': 0,
            'posts_with_location': 0,
            'total_hashtags': 0,
            'total_mentions': 0
        }
    else:
        valid_posts = [post for post in posts_data if post]
        summary_data = {
            'total_posts_analyzed': len(valid_posts),
            'total_likes': sum(post['likes'] for post in valid_posts),
            'total_comments': sum(post['comments'] for post in valid_posts),
            'total_views': sum(post['views'] for post in valid_posts),
            'average_likes': sum(post['likes'] for post in valid_posts) / len(valid_posts) if valid_posts else 0,
            'average_comments': sum(post['comments'] for post in valid_posts) / len(valid_posts) if valid_posts else 0,
            'posts_with_location': len([post for post in valid_posts if post['location'] != 'Not Found']),
            'total_hashtags': sum(len(post['hashtags']) for post in valid_posts),
            'total_mentions': sum(len(post['mentions']) for post in valid_posts)
        }
    
    # Add profile information to summary
    summary_data.update({
        'profile_username': profile_data.get('username', 'N/A'),
        'profile_full_name': profile_data.get('full_name', 'N/A'),
        'profile_posts': profile_data.get('posts', 'N/A'),
        'profile_followers': profile_data.get('followers', 'N/A'),
        'profile_following': profile_data.get('following', 'N/A'),
        'profile_verified': profile_data.get('verified', 'N/A'),
        'profile_bio': profile_data.get('bio', 'N/A')
    })
    
    summary_df = pd.DataFrame([summary_data])
    summary_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Summary data saved to {filename}")

def save_top_posts_to_csv(posts_data, filename, top_n=10):
    """Save top performing posts to CSV file"""
    if not posts_data:
        print(" No posts data to save top posts")
        return
    
    valid_posts = [post for post in posts_data if post]
    if not valid_posts:
        return
    
    # Sort by likes and get top posts
    top_posts = sorted(valid_posts, key=lambda x: x['likes'], reverse=True)[:top_n]
    
    # Prepare data for CSV
    csv_top_posts = []
    for i, post in enumerate(top_posts, 1):
        csv_post = post.copy()
        csv_post['rank'] = i
        csv_post['hashtags'] = ', '.join(post['hashtags']) if post['hashtags'] else ''
        csv_post['mentions'] = ', '.join(post['mentions']) if post['mentions'] else ''
        csv_top_posts.append(csv_post)
    
    top_posts_df = pd.DataFrame(csv_top_posts)
    top_posts_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Top {top_n} posts saved to {filename}")

def save_checkpoint_csv(profile_data, posts_data, checkpoint_num, target_username):
    """Save checkpoint data to CSV files"""
    posts_filename = f"{target_username}_checkpoint_{checkpoint_num}_posts.csv"
    summary_filename = f"{target_username}_checkpoint_{checkpoint_num}_summary.csv"
    
    save_posts_to_csv(posts_data, posts_filename)
    save_summary_to_csv(profile_data, posts_data, summary_filename)
    
    print(f" Checkpoint saved: {posts_filename}, {summary_filename}")

def main():
    print(" Complete Instagram Profile Analyzer - ALL POSTS (CSV OUTPUT)")
    print("=" * 70)
    
    username = input("Enter your Instagram username: ")
    password = getpass.getpass("Enter your Instagram password: ")
    target = input("Enter target Instagram username: ")
    
    # Option to analyze all posts or set a custom limit
    analyze_all = input("Analyze ALL posts? (y/n, default=y): ").lower().strip()
    if analyze_all == 'n':
        max_posts = int(input("Enter maximum posts to analyze: "))
    else:
        max_posts = None
        print(" Will analyze ALL posts found in the profile")

    driver = setup_driver()
    
    try:
        # Login
        login(driver, username, password)
        
        # Extract profile details
        print("\n EXTRACTING PROFILE DETAILS...")
        profile_data = extract_profile_details(driver, target)
        expected_posts = profile_data.get('posts', 0) if isinstance(profile_data.get('posts'), int) else 0
        
        # Collect all posts
        print("\n COLLECTING ALL POSTS...")
        post_urls = collect_all_posts(driver, target, expected_posts)
        
        if not post_urls:
            print(" No posts found!")
            return
        
        # Apply limit if specified
        if max_posts:
            post_urls = post_urls[:max_posts]
            print(f" Limited to first {len(post_urls)} posts as requested")
        
        # Analyze each post
        print(f"\n ANALYZING {len(post_urls)} POSTS...")
        posts_data = []
        
        for i, post_url in enumerate(post_urls, 1):
            post_data = analyze_single_post(driver, post_url, i, len(post_urls))
            if post_data:
                # Add OCR data as backup (only for first 100 posts to save time)
                if 'screenshot_path' in post_data and i <= 100:
                    ocr_data = extract_from_screenshot(post_data['screenshot_path'])
                    post_data.update(ocr_data)
                
                posts_data.append(post_data)
            
            # Progress checkpoint - save data every 50 posts
            if i % 50 == 0:
                save_checkpoint_csv(profile_data, posts_data, i, target)
            
            time.sleep(1.5)  # Be respectful to Instagram
        
        # Save all data to CSV files
        print("\n SAVING DATA TO CSV FILES...")
        
        # Save profile data
        profile_filename = f"{target}_profile_data.csv"
        save_profile_to_csv(profile_data, profile_filename)
        
        # Save all posts data
        posts_filename = f"{target}_all_posts_data.csv"
        save_posts_to_csv(posts_data, posts_filename)
        
        # Save summary
        summary_filename = f"{target}_analysis_summary.csv"
        save_summary_to_csv(profile_data, posts_data, summary_filename)
        
        # Save top posts
        top_posts_filename = f"{target}_top_posts.csv"
        save_top_posts_to_csv(posts_data, top_posts_filename, 10)
        
        # Display summary
        print("\n" + "="*70)
        print(" COMPLETE ANALYSIS RESULTS - ALL POSTS")
        print("="*70)
        
        print(f"\n PROFILE INFORMATION:")
        print(f"Username: {profile_data['username']}")
        print(f"Full Name: {profile_data['full_name']}")
        print(f"Posts: {profile_data['posts']}")
        print(f"Followers: {profile_data['followers']}")
        print(f"Following: {profile_data['following']}")
        print(f"Verified: {profile_data['verified']}")
        print(f"Bio: {profile_data['bio'][:100]}..." if len(str(profile_data['bio'])) > 100 else f"Bio: {profile_data['bio']}")
        
        valid_posts = [post for post in posts_data if post]
        print(f"\n POSTS ANALYSIS SUMMARY:")
        print(f"Total Posts Analyzed: {len(valid_posts)}")
        print(f"Expected Posts: {expected_posts}")
        print(f"Coverage: {(len(valid_posts)/expected_posts*100):.1f}%" if expected_posts > 0 else "N/A")
        print(f"Total Likes: {sum(post['likes'] for post in valid_posts):,}")
        print(f"Total Comments: {sum(post['comments'] for post in valid_posts):,}")
        print(f"Total Views: {sum(post['views'] for post in valid_posts):,}")
        print(f"Average Likes: {sum(post['likes'] for post in valid_posts) / len(valid_posts):.2f}" if valid_posts else "0")
        print(f"Average Comments: {sum(post['comments'] for post in valid_posts) / len(valid_posts):.2f}" if valid_posts else "0")
        print(f"Posts with Location: {len([post for post in valid_posts if post['location'] != 'Not Found'])}")
        print(f"Total Hashtags Used: {sum(len(post['hashtags']) for post in valid_posts)}")
        print(f"Total Mentions: {sum(len(post['mentions']) for post in valid_posts)}")
        
        print(f"\n  TOP 5 POSTS BY LIKES:")
        top_posts = sorted(valid_posts, key=lambda x: x['likes'], reverse=True)[:5]
        for i, post in enumerate(top_posts, 1):
            print(f"{i}. {post['likes']:,} likes, {post['comments']:,} comments - {post['url']}")
        
        print(f"\n  CSV FILES CREATED:")
        print(f"- Profile data: {profile_filename}")
        print(f"- All posts data: {posts_filename}")
        print(f"- Analysis summary: {summary_filename}")
        print(f"- Top posts: {top_posts_filename}")
        if any('screenshot_path' in post for post in valid_posts):
            screenshot_count = len([post for post in valid_posts if 'screenshot_path' in post])
            print(f"- Screenshots: screenshots/posts/ ({screenshot_count} files)")
        
        print(f"\n Analysis complete! All data saved in CSV format.")
        
    except Exception as e:
        print(f" Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

class Instagram:
    def __init__(self):
        pass

    def run(self):
        main()
