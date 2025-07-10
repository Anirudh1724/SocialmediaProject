import time
import os
import cv2
import easyocr
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
from selenium.webdriver.common.action_chains import ActionChains

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

def extract_channel_details(driver, channel_url):
    """Extract basic channel information"""
    driver.get(channel_url)
    time.sleep(5)
    
    print(f" Extracting channel details...")
    
    channel_data = {
        'channel_name': 'Not Found',
        'channel_url': channel_url,
        'subscribers': 'Not Found',
        'videos_count': 'Not Found',
        'views_total': 'Not Found',
        'verified': 'No',
        'description': 'Not Found',
        'channel_created': 'Not Found',
        'channel_avatar': 'Not Found',
        'channel_banner': 'Not Found'
    }
    
    try:
        # Extract channel name
        try:
            name_selectors = [
                "//yt-formatted-string[@id='text' and @class='style-scope ytd-channel-name']",
                "//div[@id='channel-name']//yt-formatted-string",
                "//h1//yt-formatted-string"
            ]
            for selector in name_selectors:
                try:
                    name_element = driver.find_element(By.XPATH, selector)
                    if name_element.text:
                        channel_data['channel_name'] = name_element.text
                        break
                except:
                    continue
        except:
            pass
        
        # Extract subscriber count
        try:
            subscriber_selectors = [
                "//yt-formatted-string[contains(@id, 'subscriber-count')]",
                "//*[contains(text(), 'subscriber')]",
                "//span[contains(text(), 'subscriber')]"
            ]
            for selector in subscriber_selectors:
                try:
                    sub_element = driver.find_element(By.XPATH, selector)
                    if 'subscriber' in sub_element.text.lower():
                        channel_data['subscribers'] = extract_number_from_text(sub_element.text)
                        break
                except:
                    continue
        except:
            pass
        
        # Check if verified
        try:
            verified_element = driver.find_element(By.XPATH, "//*[contains(@class, 'verified') or contains(@title, 'Verified')]")
            channel_data['verified'] = 'Yes'
        except:
            pass
        
        # Extract channel description (go to About tab)
        try:
            about_tab = driver.find_element(By.XPATH, "//a[contains(@href, '/about')]")
            driver.execute_script("arguments[0].click();", about_tab)
            time.sleep(3)
            
            # Extract description
            try:
                desc_selectors = [
                    "//yt-formatted-string[@id='description']",
                    "//div[@id='description-container']//yt-formatted-string",
                    "//*[@id='description']"
                ]
                for selector in desc_selectors:
                    try:
                        desc_element = driver.find_element(By.XPATH, selector)
                        if desc_element.text:
                            channel_data['description'] = desc_element.text
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract channel stats from About page
            try:
                stats_elements = driver.find_elements(By.XPATH, "//yt-formatted-string[contains(@class, 'style-scope ytd-about-channel-renderer')]")
                for element in stats_elements:
                    text = element.text.lower()
                    if 'view' in text:
                        channel_data['views_total'] = extract_number_from_text(element.text)
                    elif 'joined' in text or 'created' in text:
                        channel_data['channel_created'] = element.text
            except:
                pass
            
        except:
            pass
        
        # Extract channel avatar
        try:
            avatar_element = driver.find_element(By.XPATH, "//img[@id='img']")
            channel_data['channel_avatar'] = avatar_element.get_attribute('src')
        except:
            pass
    
    except Exception as e:
        print(f" Error extracting channel details: {e}")
    
    return channel_data

def extract_number_from_text(text):
    """Extract number from text like '1.2K subscribers' or '500M views'"""
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

def collect_all_videos(driver, channel_url):
    """Scroll through channel and collect ALL video URLs"""
    # Go to Videos tab
    videos_url = channel_url.rstrip('/') + '/videos'
    driver.get(videos_url)
    time.sleep(5)
    
    print(f" Collecting ALL videos from channel...")
    
    collected_urls = set()
    scroll_attempts = 0
    max_scrolls_without_progress = 5
    consecutive_no_progress = 0
    last_height = 0
    
    # Get initial scroll height
    current_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Find all video links
        video_elements = driver.find_elements(By.XPATH, '//a[@id="video-title-link" or @id="thumbnail"]')
        
        before_count = len(collected_urls)
        
        for video_element in video_elements:
            href = video_element.get_attribute("href")
            if href and "/watch?v=" in href:
                # Clean URL to remove extra parameters
                video_id = href.split("/watch?v=")[1].split("&")[0]
                clean_url = f"https://www.youtube.com/watch?v={video_id}"
                collected_urls.add(clean_url)
        
        current_count = len(collected_urls)
        new_videos_found = current_count - before_count
        
        print(f" Progress: {current_count} videos collected (found {new_videos_found} new videos)")
        
        # Scroll down using multiple methods
        last_height = current_height
        
        # Method 1: Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Method 2: Scroll by viewport height  
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(1)
        
        # Check if page height changed
        current_height = driver.execute_script("return document.body.scrollHeight")
        
        if current_height == last_height and new_videos_found == 0:
            consecutive_no_progress += 1
            print(f" No progress... Attempt {consecutive_no_progress}/{max_scrolls_without_progress}")
            
            if consecutive_no_progress >= max_scrolls_without_progress:
                print(f" Trying alternative scroll method...")
                # Try aggressive scrolling
                for i in range(5):
                    driver.execute_script(f"window.scrollTo(0, {current_height + (i * 1000)});")
                    time.sleep(1)
                
                # Check one more time for new videos
                video_elements = driver.find_elements(By.XPATH, '//a[@id="video-title-link" or @id="thumbnail"]')
                final_check_count = len(collected_urls)
                
                for video_element in video_elements:
                    href = video_element.get_attribute("href")
                    if href and "/watch?v=" in href:
                        video_id = href.split("/watch?v=")[1].split("&")[0]
                        clean_url = f"https://www.youtube.com/watch?v={video_id}"
                        collected_urls.add(clean_url)
                
                if len(collected_urls) == final_check_count:
                    print(f" Reached end of videos. No more content to load.")
                    break
                else:
                    consecutive_no_progress = 0
        else:
            consecutive_no_progress = 0
        
        scroll_attempts += 1
        
        # Safety net
        if scroll_attempts > 300:
            print(f" Reached maximum scroll attempts ({scroll_attempts})")
            break
        
        # Longer pause for channels with many videos
        if current_count > 1000:
            time.sleep(3)
        elif current_count > 500:
            time.sleep(2)
    
    video_urls = list(collected_urls)
    print(f" Collected {len(video_urls)} total videos")
    
    return video_urls

def analyze_single_video(driver, video_url, video_index, total_videos):
    """Analyze a single video and extract all details - IMPROVED VERSION"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f" Analyzing video {video_index}/{total_videos}: {video_url} (Attempt {attempt + 1})")
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            try:
                driver.get(video_url)
            except Exception as e:
                print(f" Page load timeout or error: {e}")
                if attempt < max_retries - 1:
                    print(f" Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    print(f" Skipping video after {max_retries} attempts")
                    return None
            
            # Wait for page to load with multiple checks
            wait = WebDriverWait(driver, 15)
            
            # Wait for video player or title to load
            try:
                wait.until(lambda d: d.find_element(By.TAG_NAME, "h1") or 
                          d.find_element(By.CSS_SELECTOR, ".ytp-time-duration"))
            except:
                print(f" Page didn't load properly, trying anyway...")
            
            time.sleep(3)  # Additional wait
            
            video_data = {
                'url': video_url,
                'video_id': video_url.split('v=')[1].split('&')[0] if 'v=' in video_url else 'Unknown',
                'title': 'Not Found',
                'views': 0,
                'likes': 0,
                'comments': 0,
                'duration': 'Not Found',
                'upload_date': 'Not Found',
                'description': 'Not Found',
                'tags': [],
                'category': 'Not Found',
                'thumbnail_url': 'Not Found'
            }
            
            # Extract title with multiple fallbacks
            try:
                title_found = False
                title_selectors = [
                    "//h1[@class='style-scope ytd-watch-metadata']//yt-formatted-string",
                    "//h1//yt-formatted-string[@class='style-scope ytd-watch-metadata']",
                    "//h1[contains(@class, 'ytd-watch-metadata')]",
                    "//h1//yt-formatted-string",
                    "//title"
                ]
                
                for selector in title_selectors:
                    try:
                        title_element = driver.find_element(By.XPATH, selector)
                        if title_element.text and len(title_element.text.strip()) > 0:
                            video_data['title'] = title_element.text.strip()
                            title_found = True
                            break
                    except:
                        continue
                
                if not title_found:
                    # Try getting from page title
                    page_title = driver.title
                    if page_title and " - YouTube" in page_title:
                        video_data['title'] = page_title.replace(" - YouTube", "")
                        
            except Exception as e:
                print(f" Error extracting title: {e}")
            
            # Extract views with better error handling
            try:
                view_selectors = [
                    "//span[contains(text(), 'views')]",
                    "//*[@id='info']//span[contains(text(), 'views')]",
                    "//div[@id='info-container']//span[contains(text(), 'views')]",
                    "//div[contains(@class, 'view-count')]",
                    "//*[contains(@class, 'ytd-video-view-count-renderer')]"
                ]
                
                for selector in view_selectors:
                    try:
                        view_elements = driver.find_elements(By.XPATH, selector)
                        for view_element in view_elements:
                            if view_element.text and 'view' in view_element.text.lower():
                                views = extract_number_from_text(view_element.text)
                                if views > 0:
                                    video_data['views'] = views
                                    break
                        if video_data['views'] > 0:
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting views: {e}")
            
            # Extract likes (simplified approach)
            try:
                like_selectors = [
                    "//button[@aria-label and contains(@aria-label, 'like')]//span",
                    "//*[contains(@class, 'like')]//span[text()]",
                    "//yt-formatted-string[@id='text' and ancestor::*[contains(@aria-label, 'like')]]"
                ]
                
                for selector in like_selectors:
                    try:
                        like_elements = driver.find_elements(By.XPATH, selector)
                        for element in like_elements:
                            if element.text:
                                likes = extract_number_from_text(element.text)
                                if likes > 0:
                                    video_data['likes'] = likes
                                    break
                        if video_data['likes'] > 0:
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting likes: {e}")
            
            # Extract comments count (scroll down first)
            try:
                # Gentle scroll to comments
                driver.execute_script("window.scrollTo(0, Math.min(800, document.body.scrollHeight * 0.3));")
                time.sleep(2)
                
                comment_selectors = [
                    "//yt-formatted-string[contains(@class, 'count-text')]",
                    "//h2[@id='count']//yt-formatted-string",
                    "//*[contains(text(), 'Comments')]//yt-formatted-string",
                    "//*[@id='count']//yt-formatted-string"
                ]
                
                for selector in comment_selectors:
                    try:
                        comment_elements = driver.find_elements(By.XPATH, selector)
                        for element in comment_elements:
                            if element.text:
                                comments = extract_number_from_text(element.text)
                                if comments > 0:
                                    video_data['comments'] = comments
                                    break
                        if video_data['comments'] > 0:
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting comments: {e}")
            
            # Extract duration
            try:
                # Try to get duration from video player
                duration_selectors = [
                    "//span[@class='ytp-time-duration']",
                    "//div[@class='ytp-time-display']//span[contains(@class, 'ytp-time-duration')]",
                    "//*[contains(@class, 'ytp-time-duration')]"
                ]
                
                for selector in duration_selectors:
                    try:
                        duration_element = driver.find_element(By.XPATH, selector)
                        if duration_element.text and ':' in duration_element.text:
                            video_data['duration'] = duration_element.text
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting duration: {e}")
            
            # Extract upload date
            try:
                date_selectors = [
                    "//div[@id='info-strings']//yt-formatted-string",
                    "//div[@id='info']//yt-formatted-string",
                    "//*[contains(text(), 'Published') or contains(text(), 'Streamed') or contains(text(), 'Premiered')]",
                    "//*[contains(text(), 'ago')]"
                ]
                
                for selector in date_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        for element in elements:
                            text = element.text.lower()
                            if any(word in text for word in ['published', 'streamed', 'premiered', 'ago']) and len(text) > 3:
                                video_data['upload_date'] = element.text
                                break
                        if video_data['upload_date'] != 'Not Found':
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting upload date: {e}")
            
            # Extract description (simplified)
            try:
                # Scroll back to top
                driver.execute_script("window.scrollTo(0, 200);")
                time.sleep(1)
                
                # Try to click Show More if it exists
                try:
                    show_more_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Show more') or contains(text(), '...more')]")
                    if show_more_buttons:
                        driver.execute_script("arguments[0].click();", show_more_buttons[0])
                        time.sleep(1)
                except:
                    pass
                
                desc_selectors = [
                    "//div[@id='description']//yt-formatted-string",
                    "//div[contains(@class, 'description')]//yt-formatted-string",
                    "//div[@id='meta-contents']//yt-formatted-string"
                ]
                
                for selector in desc_selectors:
                    try:
                        desc_elements = driver.find_elements(By.XPATH, selector)
                        description_parts = []
                        for element in desc_elements:
                            if element.text and len(element.text.strip()) > 5:
                                description_parts.append(element.text.strip())
                        
                        if description_parts:
                            video_data['description'] = ' '.join(description_parts)[:1000]  # Limit length
                            
                            # Extract hashtags from description
                            hashtags = re.findall(r'#\w+', video_data['description'])
                            video_data['tags'] = hashtags[:10]  # Limit hashtags
                            break
                    except:
                        continue
            except Exception as e:
                print(f" Error extracting description: {e}")
            
            # Set thumbnail URL
            video_id = video_data['video_id']
            video_data['thumbnail_url'] = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
            # Take screenshot (optional, for first 20 videos)
            if video_index <= 20:
                try:
                    os.makedirs("screenshots/videos", exist_ok=True)
                    screenshot_path = f"screenshots/videos/video_{video_index}.png"
                    driver.save_screenshot(screenshot_path)
                    video_data['screenshot_path'] = screenshot_path
                except:
                    pass
            
            # Print progress with key metrics
            print(f" ✓ Title: {video_data['title'][:50]}...")
            print(f" ✓ Views: {video_data['views']:,}, Likes: {video_data['likes']:,}, Comments: {video_data['comments']:,}")
            
            return video_data
            
        except Exception as e:
            print(f" Error analyzing video {video_index} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f" Retrying in 5 seconds...")
                time.sleep(5)
                # Try to refresh the page or reset
                try:
                    driver.refresh()
                    time.sleep(3)
                except:
                    pass
            else:
                print(f" Failed to analyze video after {max_retries} attempts")
                return None

def extract_from_screenshot(image_path):
    """Extract additional data from screenshot using OCR as backup"""
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        img = cv2.imread(image_path)
        results = reader.readtext(img)
        texts = [text[1] for text in results if len(text) > 1]
        
        ocr_data = {
            'views_ocr': 0,
            'likes_ocr': 0,
            'comments_ocr': 0,
            'text_content': ' '.join(texts)
        }
        
        for text in texts:
            text_lower = text.lower()
            if 'view' in text_lower:
                ocr_data['views_ocr'] = extract_number_from_text(text)
            elif 'like' in text_lower:
                ocr_data['likes_ocr'] = extract_number_from_text(text)
            elif 'comment' in text_lower:
                ocr_data['comments_ocr'] = extract_number_from_text(text)
        
        return ocr_data
        
    except Exception as e:
        return {'views_ocr': 0, 'likes_ocr': 0, 'comments_ocr': 0, 'text_content': ''}

def save_channel_to_csv(channel_data, filename):
    """Save channel data to CSV file"""
    channel_df = pd.DataFrame([channel_data])
    channel_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Channel data saved to {filename}")

def save_videos_to_csv(videos_data, filename):
    """Save videos data to CSV file"""
    if not videos_data:
        print(" No videos data to save")
        return
    
    # Prepare data for CSV
    csv_videos_data = []
    for video in videos_data:
        if video:
            csv_video = video.copy()
            # Convert lists to comma-separated strings
            csv_video['tags'] = ', '.join(video['tags']) if video['tags'] else ''
            csv_videos_data.append(csv_video)
    
    videos_df = pd.DataFrame(csv_videos_data)
    videos_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Videos data saved to {filename}")

def save_summary_to_csv(channel_data, videos_data, filename):
    """Save analysis summary to CSV file"""
    if not videos_data:
        summary_data = {
            'total_videos_analyzed': 0,
            'total_views': 0,
            'total_likes': 0,
            'total_comments': 0,
            'average_views': 0,
            'average_likes': 0,
            'average_comments': 0,
            'videos_with_description': 0,
            'total_tags': 0
        }
    else:
        valid_videos = [video for video in videos_data if video]
        summary_data = {
            'total_videos_analyzed': len(valid_videos),
            'total_views': sum(video['views'] for video in valid_videos),
            'total_likes': sum(video['likes'] for video in valid_videos),
            'total_comments': sum(video['comments'] for video in valid_videos),
            'average_views': sum(video['views'] for video in valid_videos) / len(valid_videos) if valid_videos else 0,
            'average_likes': sum(video['likes'] for video in valid_videos) / len(valid_videos) if valid_videos else 0,
            'average_comments': sum(video['comments'] for video in valid_videos) / len(valid_videos) if valid_videos else 0,
            'videos_with_description': len([video for video in valid_videos if video['description'] != 'Not Found']),
            'total_tags': sum(len(video['tags']) for video in valid_videos)
        }
    
    # Add channel information to summary
    summary_data.update({
        'channel_name': channel_data.get('channel_name', 'N/A'),
        'channel_url': channel_data.get('channel_url', 'N/A'),
        'channel_subscribers': channel_data.get('subscribers', 'N/A'),
        'channel_total_views': channel_data.get('views_total', 'N/A'),
        'channel_verified': channel_data.get('verified', 'N/A'),
        'channel_description': channel_data.get('description', 'N/A')
    })
    
    summary_df = pd.DataFrame([summary_data])
    summary_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Summary data saved to {filename}")

def save_top_videos_to_csv(videos_data, filename, top_n=10):
    """Save top performing videos to CSV file"""
    if not videos_data:
        print(" No videos data to save top videos")
        return
    
    valid_videos = [video for video in videos_data if video]
    if not valid_videos:
        return
    
    # Sort by views and get top videos
    top_videos = sorted(valid_videos, key=lambda x: x['views'], reverse=True)[:top_n]
    
    # Prepare data for CSV
    csv_top_videos = []
    for i, video in enumerate(top_videos, 1):
        csv_video = video.copy()
        csv_video['rank'] = i
        csv_video['tags'] = ', '.join(video['tags']) if video['tags'] else ''
        csv_top_videos.append(csv_video)
    
    top_videos_df = pd.DataFrame(csv_top_videos)
    top_videos_df.to_csv(filename, index=False, encoding='utf-8')
    print(f" Top {top_n} videos saved to {filename}")

def save_checkpoint_csv(channel_data, videos_data, checkpoint_num, channel_name):
    """Save checkpoint data to CSV files"""
    safe_channel_name = re.sub(r'[^\w\-_\.]', '_', channel_name)
    videos_filename = f"{safe_channel_name}_checkpoint_{checkpoint_num}_videos.csv"
    summary_filename = f"{safe_channel_name}_checkpoint_{checkpoint_num}_summary.csv"
    
    save_videos_to_csv(videos_data, videos_filename)
    save_summary_to_csv(channel_data, videos_data, summary_filename)
    
    print(f" Checkpoint saved: {videos_filename}, {summary_filename}")

def main():
    print(" Complete YouTube Channel Analyzer - ALL VIDEOS (CSV OUTPUT)")
    print("=" * 70)
    
    channel_input = input("Enter YouTube channel URL (e.g., https://www.youtube.com/@channelname): ")
    
    # Validate and format channel URL
    if not channel_input.startswith('http'):
        if channel_input.startswith('@'):
            channel_url = f"https://www.youtube.com/{channel_input}"
        else:
            channel_url = f"https://www.youtube.com/@{channel_input}"
    else:
        channel_url = channel_input
    
    # Option to analyze all videos or set a custom limit
    analyze_all = input("Analyze ALL videos? (y/n, default=y): ").lower().strip()
    if analyze_all == 'n':
        max_videos = int(input("Enter maximum videos to analyze: "))
    else:
        max_videos = None
        print(" Will analyze ALL videos found in the channel")

    driver = setup_driver()
    
    try:
        # Extract channel details
        print("\n EXTRACTING CHANNEL DETAILS...")
        channel_data = extract_channel_details(driver, channel_url)
        
        # Collect all videos
        print("\n COLLECTING ALL VIDEOS...")
        video_urls = collect_all_videos(driver, channel_url)
        
        if not video_urls:
            print(" No videos found!")
            return
        
        # Apply limit if specified
        if max_videos:
            video_urls = video_urls[:max_videos]
            print(f" Limited to first {len(video_urls)} videos as requested")
        
        # Analyze each video with better error handling
        print(f"\n ANALYZING {len(video_urls)} VIDEOS...")
        videos_data = []
        failed_videos = []
        
        for i, video_url in enumerate(video_urls, 1):
            print(f"\n--- Processing Video {i}/{len(video_urls)} ---")
            
            video_data = analyze_single_video(driver, video_url, i, len(video_urls))
            
            if video_data:
                # Add OCR data as backup (only for first 20 videos)
                if 'screenshot_path' in video_data and i <= 20:
                    ocr_data = extract_from_screenshot(video_data['screenshot_path'])
                    video_data.update(ocr_data)
                
                videos_data.append(video_data)
                print(f" ✓ Successfully analyzed video")
            else:
                failed_videos.append(video_url)
                print(f" ✗ Failed to analyze video")
            
            # Save checkpoint every 50 videos
            if i % 50 == 0:
                safe_channel_name = re.sub(r'[^\w\-_\.]', '_', channel_data.get('channel_name', 'Unknown'))
                save_checkpoint_csv(channel_data, videos_data, i, safe_channel_name)
            
            # Brief pause between videos
            time.sleep(1)
        
        # Final results
        print("\n" + "=" * 70)
        print(" ANALYSIS COMPLETE!")
        print("=" * 70)
        print(f" Channel: {channel_data['channel_name']}")
        print(f" Total videos found: {len(video_urls)}")
        print(f" Successfully analyzed: {len(videos_data)}")
        print(f" Failed to analyze: {len(failed_videos)}")
        
        if videos_data:
            total_views = sum(video['views'] for video in videos_data)
            total_likes = sum(video['likes'] for video in videos_data)
            total_comments = sum(video['comments'] for video in videos_data)
            
            print(f" Total views: {total_views:,}")
            print(f" Total likes: {total_likes:,}")
            print(f" Total comments: {total_comments:,}")
            print(f" Average views per video: {total_views/len(videos_data):,.0f}")
        
        # Save all data to CSV files
        print("\n SAVING DATA TO CSV FILES...")
        safe_channel_name = re.sub(r'[^\w\-_\.]', '_', channel_data.get('channel_name', 'Unknown'))
        
        # Save channel data
        channel_filename = f"{safe_channel_name}_channel_data.csv"
        save_channel_to_csv(channel_data, channel_filename)
        
        # Save all videos data
        videos_filename = f"{safe_channel_name}_all_videos.csv"
        save_videos_to_csv(videos_data, videos_filename)
        
        # Save analysis summary
        summary_filename = f"{safe_channel_name}_analysis_summary.csv"
        save_summary_to_csv(channel_data, videos_data, summary_filename)
        
        # Save top 10 videos
        top_videos_filename = f"{safe_channel_name}_top_10_videos.csv"
        save_top_videos_to_csv(videos_data, top_videos_filename, 10)
        
        # Save failed videos list
        if failed_videos:
            failed_filename = f"{safe_channel_name}_failed_videos.csv"
            failed_df = pd.DataFrame({'failed_urls': failed_videos})
            failed_df.to_csv(failed_filename, index=False)
            print(f" Failed videos list saved to {failed_filename}")
        
        print("\n CSV FILES CREATED:")
        print(f" - {channel_filename} (Channel information)")
        print(f" - {videos_filename} (All videos data)")
        print(f" - {summary_filename} (Analysis summary)")
        print(f" - {top_videos_filename} (Top 10 videos)")
        if failed_videos:
            print(f" - {failed_filename} (Failed videos list)")
        
        print("\n Analysis completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n Process interrupted by user!")
        print(" Saving partial data...")
        
        # Save whatever data we have so far
        if 'videos_data' in locals() and videos_data:
            safe_channel_name = re.sub(r'[^\w\-_\.]', '_', channel_data.get('channel_name', 'Unknown'))
            partial_filename = f"{safe_channel_name}_partial_videos.csv"
            save_videos_to_csv(videos_data, partial_filename)
            print(f" Partial data saved to {partial_filename}")
        
    except Exception as e:
        print(f"\n Error during analysis: {e}")
        
        # Save whatever data we have so far
        if 'videos_data' in locals() and videos_data:
            safe_channel_name = re.sub(r'[^\w\-_\.]', '_', channel_data.get('channel_name', 'Unknown'))
            error_filename = f"{safe_channel_name}_error_recovery.csv"
            save_videos_to_csv(videos_data, error_filename)
            print(f" Error recovery data saved to {error_filename}")
        
    finally:
        driver.quit()
        print("\n Browser closed.")

if __name__ == "__main__":
    main()