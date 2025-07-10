import time
import os
import cv2
import easyocr
import re
import json
import csv
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests
from PIL import Image
import pytesseract
from urllib.parse import quote

def setup_driver():
    """Setup Chrome driver with appropriate options for Threads"""
    options = Options()
    # Keep visible for debugging, comment out for headless
    options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Use a realistic user agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Additional options for better compatibility
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-extensions")
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def take_profile_screenshot(driver, username):
    """Take a screenshot of the Threads profile"""
    try:
        # Create screenshots directory
        os.makedirs("screenshots/threads", exist_ok=True)
        
        # Wait for page to load completely
        time.sleep(5)
        
        # Scroll to top to ensure header is visible
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # Take screenshot
        screenshot_path = f"screenshots/threads/{username}_profile.png"
        driver.save_screenshot(screenshot_path)
        print(f" Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f" Error taking screenshot: {e}")
        return None

def extract_threads_profile_details(driver, target_username):
    """Extract profile details from Instagram Threads"""
    profile_url = f"https://www.threads.net/@{target_username}"
    
    print(f" Navigating to: {profile_url}")
    driver.get(profile_url)
    
    # Wait for page to load
    time.sleep(8)
    
    print(f" Extracting profile details for @{target_username}...")
    
    profile_data = {
        'username': target_username,
        'display_name': 'Not Found',
        'verified': 'No',
        'posts_count': 'Not Found',
        'followers_count': 'Not Found',
        'following_count': 'Not Found',
        'bio': 'Not Found',
        'profile_image_url': 'Not Found',
        'is_private': 'Unknown',
        'external_url': 'Not Found',
        'threads_visible': 0
    }
    
    try:
        # Take screenshot first
        screenshot_path = take_profile_screenshot(driver, target_username)
        profile_data['screenshot_path'] = screenshot_path
        
        # Wait for content to load
        time.sleep(3)
        
        # Check if profile exists by looking for error messages
        try:
            error_selectors = [
                'div:contains("Sorry, this page isn\'t available")',
                'div:contains("User not found")',
                'div:contains("This account doesn\'t exist")',
                '[data-testid="error"]'
            ]
            
            page_text = driver.page_source.lower()
            if any(error_text in page_text for error_text in ['sorry, this page', 'user not found', 'doesn\'t exist', 'not available']):
                profile_data['profile_exists'] = False
                print(f" Profile @{target_username} does not exist or is not accessible")
                return profile_data
            else:
                profile_data['profile_exists'] = True
        except:
            profile_data['profile_exists'] = True
        
        # Extract display name - try multiple selectors
        try:
            name_selectors = [
                'h1',
                '[data-testid="user-name"]',
                'div[role="main"] h1',
                'header h1',
                'div:contains("@' + target_username + '") h1'
            ]
            
            for selector in name_selectors:
                try:
                    if 'contains' in selector:
                        # Handle complex selector separately
                        elements = driver.find_elements(By.TAG_NAME, "h1")
                        for elem in elements:
                            if elem.text and elem.text != f"@{target_username}":
                                profile_data['display_name'] = elem.text.strip()
                                break
                    else:
                        name_element = driver.find_element(By.CSS_SELECTOR, selector)
                        if name_element.text and name_element.text != f"@{target_username}":
                            profile_data['display_name'] = name_element.text.strip()
                            break
                except:
                    continue
                    
            if profile_data['display_name'] == 'Not Found':
                # Try extracting from page title
                page_title = driver.title
                if page_title and '@' in page_title:
                    # Extract name before the @ symbol
                    name_part = page_title.split('@')[0].strip()
                    if name_part and name_part.lower() != 'threads':
                        profile_data['display_name'] = name_part
                        
        except Exception as e:
            print(f" Could not extract display name: {e}")
        
        # Check for verification badge
        try:
            verification_selectors = [
                'svg[aria-label*="Verified"]',
                '[data-testid="verified-badge"]',
                'img[alt*="Verified"]',
                'span:contains("Verified")'
            ]
            
            for selector in verification_selectors:
                try:
                    driver.find_element(By.CSS_SELECTOR, selector)
                    profile_data['verified'] = 'Yes'
                    break
                except:
                    continue
        except:
            pass
        
        # Extract follower counts and stats
        try:
            # Look for numbers that might represent followers/following
            page_source = driver.page_source
            
            # Try to find follower patterns in the page source
            follower_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+followers',
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+Followers',
                r'"followers_count":(\d+)',
                r'followers.*?(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)',
                r'(\d+(?:,\d+)*)\s+followers'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    profile_data['followers_count'] = extract_number_from_text(match.group(1))
                    break
            
            following_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+following',
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+Following',
                r'"following_count":(\d+)',
                r'following.*?(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)',
                r'(\d+(?:,\d+)*)\s+following'
            ]
            
            for pattern in following_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    profile_data['following_count'] = extract_number_from_text(match.group(1))
                    break
            
            
            posts_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+posts',
                r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+threads',
                r'"posts_count":(\d+)',
                r'posts.*?(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)'
            ]
            
            for pattern in posts_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    profile_data['posts_count'] = extract_number_from_text(match.group(1))
                    break
                    
        except Exception as e:
            print(f" Could not extract stats from page source: {e}")
        
        
        try:
            bio_selectors = [
                '[data-testid="user-bio"]',
                'div[role="main"] div:nth-child(2) div',
                'header + div',
                'div[dir="auto"]'
            ]
            
            for selector in bio_selectors:
                try:
                    bio_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for bio_element in bio_elements:
                        bio_text = bio_element.text.strip()
                        if (bio_text and 
                            len(bio_text) > 10 and 
                            bio_text != profile_data['display_name'] and 
                            f"@{target_username}" not in bio_text):
                            profile_data['bio'] = bio_text
                            break
                    if profile_data['bio'] != 'Not Found':
                        break
                except:
                    continue
        except:
            pass
        
        # Extract profile image URL
        try:
            img_selectors = [
                'img[alt*="profile"]',
                'header img',
                'div[role="main"] img:first-child',
                'img[src*="profile"]'
            ]
            
            for selector in img_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    img_src = img_element.get_attribute('src')
                    if img_src and ('profile' in img_src.lower() or 'avatar' in img_src.lower()):
                        profile_data['profile_image_url'] = img_src
                        break
                except:
                    continue
        except:
            pass
        
        # Check if account is private
        try:
            private_indicators = [
                'This account is private',
                'Private account',
                'Follow to see their posts',
                'This user\'s posts are private'
            ]
            
            page_text = driver.page_source.lower()
            for indicator in private_indicators:
                if indicator.lower() in page_text:
                    profile_data['is_private'] = 'Yes'
                    break
            
            if profile_data['is_private'] == 'Unknown':
                profile_data['is_private'] = 'No'
        except:
            pass
        
        # Count visible threads/posts
        try:
            # Look for thread elements
            thread_selectors = [
                '[data-testid="thread"]',
                'article',
                'div[role="article"]'
            ]
            
            for selector in thread_selectors:
                try:
                    threads = driver.find_elements(By.CSS_SELECTOR, selector)
                    if threads:
                        profile_data['threads_visible'] = len(threads)
                        break
                except:
                    continue
        except:
            pass
        
        # Extract external URL if present
        try:
            link_selectors = [
                'a[href^="http"]:not([href*="threads.net"])',
                '[data-testid="external-link"]'
            ]
            
            for selector in link_selectors:
                try:
                    link_element = driver.find_element(By.CSS_SELECTOR, selector)
                    external_url = link_element.get_attribute('href')
                    if external_url and not any(domain in external_url for domain in ['threads.net', 'instagram.com', 'facebook.com']):
                        profile_data['external_url'] = external_url
                        break
                except:
                    continue
        except:
            pass
        
    except Exception as e:
        print(f" Error extracting profile details: {e}")
    
    return profile_data

def extract_number_from_text(text):
    """Extract number from text like '1.2K followers' or '500 following'"""
    if not text:
        return 0
    
    text = str(text).replace(',', '').lower().strip()
    
    # Handle different number formats
    patterns = [
        r'(\d+\.?\d*)\s*k',  # 1.2K
        r'(\d+\.?\d*)\s*m',  # 1.5M
        r'(\d+\.?\d*)\s*b',  # 1.2B
        r'(\d+)',            # 1234
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

def extract_from_screenshot_ocr(image_path):
    """Extract additional data from screenshot using OCR"""
    ocr_data = {
        'followers_ocr': 0,
        'following_ocr': 0,
        'posts_ocr': 0,
        'extracted_text': '',
        'ocr_method_used': 'none'
    }
    
    if not os.path.exists(image_path):
        print(f" Screenshot file not found: {image_path}")
        return ocr_data
    
    try:
        # Try EasyOCR first
        print(" Attempting OCR analysis...")
        try:
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            results = reader.readtext(image_path, detail=0)
            
            if results:
                texts = [str(text) for text in results if text and len(str(text).strip()) > 0]
                full_text = ' '.join(texts).lower()
                ocr_data['extracted_text'] = full_text
                ocr_data['ocr_method_used'] = 'easyocr'
                print(f" EasyOCR extracted {len(texts)} text elements")
            
        except Exception as e:
            print(f" EasyOCR failed, trying Tesseract: {e}")
            try:
                img = Image.open(image_path)
                img_gray = img.convert('L')
                text = pytesseract.image_to_string(img_gray)
                
                if text and len(text.strip()) > 0:
                    ocr_data['extracted_text'] = text.lower()
                    ocr_data['ocr_method_used'] = 'tesseract'
                    print(" Tesseract OCR successful")
                
            except Exception as e2:
                print(f" All OCR methods failed: {e2}")
        
        # Extract numbers from OCR text
        if ocr_data['extracted_text']:
            full_text = ocr_data['extracted_text']
            
            # Look for follower patterns
            follower_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)\s+followers',
                r'followers\s+(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    ocr_data['followers_ocr'] = extract_number_from_text(match.group(1))
                    break
            
            # Look for following patterns
            following_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)\s+following',
                r'following\s+(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)'
            ]
            
            for pattern in following_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    ocr_data['following_ocr'] = extract_number_from_text(match.group(1))
                    break
        
        return ocr_data
        
    except Exception as e:
        print(f" OCR extraction failed: {e}")
        return ocr_data

def save_profile_to_csv(profile_data, filename):
    """Save profile data to CSV file"""
    try:
        # Create data directory
        os.makedirs("data/threads", exist_ok=True)
        filepath = f"data/threads/{filename}"
        
        profile_df = pd.DataFrame([profile_data])
        profile_df.to_csv(filepath, index=False, encoding='utf-8')
        print(f" Profile data saved to {filepath}")
        return filepath
    except Exception as e:
        print(f" Error saving to CSV: {e}")
        return None

def save_profile_to_json(profile_data, filename):
    """Save profile data to JSON file"""
    try:
        # Create data directory
        os.makedirs("data/threads", exist_ok=True)
        filepath = f"data/threads/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        print(f" Profile data saved to {filepath}")
        return filepath
    except Exception as e:
        print(f" Error saving to JSON: {e}")
        return None

def check_profile_accessibility(username):
    """Check if profile is accessible without login using requests"""
    try:
        url = f"https://www.threads.net/@{username}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, "Profile accessible"
        elif response.status_code == 404:
            return False, "Profile not found"
        else:
            return False, f"HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {e}"

def main():
    print(" Instagram Threads Profile Analyzer (No Login Required)")
    print("=" * 60)
    
    # Get target username
    target_username = input("Enter Threads username (without @): ").strip()
    
    if not target_username:
        print(" No username provided. Exiting...")
        return
    
    # First check if profile is accessible
    print(f" Checking profile accessibility for @{target_username}...")
    accessible, status = check_profile_accessibility(target_username)
    
    if not accessible:
        print(f" Profile check failed: {status}")
        print(" Continuing with browser-based extraction anyway...")
    else:
        print(f" Profile appears to be accessible: {status}")
    
    # Setup driver
    print(" Setting up browser...")
    driver = setup_driver()
    
    try:
        # Extract profile details
        print(f"\n Analyzing Threads profile @{target_username}...")
        profile_data = extract_threads_profile_details(driver, target_username)
        
        # Check if profile exists
        if not profile_data.get('profile_exists', True):
            print(f" Profile @{target_username} does not exist or is not accessible")
            return
        
        # Add OCR analysis if screenshot was taken
        if 'screenshot_path' in profile_data and profile_data['screenshot_path']:
            print(" Running OCR analysis on screenshot...")
            ocr_data = extract_from_screenshot_ocr(profile_data['screenshot_path'])
            profile_data.update(ocr_data)
            
            # Use OCR data as backup if main extraction failed
            if profile_data['followers_count'] == 'Not Found' and ocr_data['followers_ocr'] > 0:
                profile_data['followers_count'] = ocr_data['followers_ocr']
                print(f" Used OCR for followers count: {ocr_data['followers_ocr']}")
            if profile_data['following_count'] == 'Not Found' and ocr_data['following_ocr'] > 0:
                profile_data['following_count'] = ocr_data['following_ocr']
                print(f" Used OCR for following count: {ocr_data['following_ocr']}")
        
        # Add extraction timestamp
        profile_data['extraction_timestamp'] = datetime.now().isoformat()
        profile_data['extraction_method'] = 'no_login_browser'
        
        # Save data to files
        print("\n Saving extracted data...")
        csv_filename = f"{target_username}_threads_profile.csv"
        json_filename = f"{target_username}_threads_profile.json"
        
        csv_path = save_profile_to_csv(profile_data, csv_filename)
        json_path = save_profile_to_json(profile_data, json_filename)
        
        # Display results
        print("\n" + "="*70)
        print(" THREADS PROFILE ANALYSIS RESULTS")
        print("="*70)
        
        print(f"\n PROFILE INFORMATION:")
        print(f"Username: @{profile_data['username']}")
        print(f"Display Name: {profile_data['display_name']}")
        print(f"Verified: {profile_data['verified']}")
        print(f"Profile Exists: {profile_data.get('profile_exists', 'Unknown')}")
        print(f"Is Private: {profile_data['is_private']}")
        print(f"Followers: {profile_data['followers_count']}")
        print(f"Following: {profile_data['following_count']}")
        print(f"Posts/Threads: {profile_data['posts_count']}")
        print(f"Visible Threads: {profile_data['threads_visible']}")
        print(f"External URL: {profile_data['external_url']}")
        
        bio_text = profile_data['bio']
        if bio_text != 'Not Found':
            if len(str(bio_text)) > 100:
                print(f"Bio: {bio_text[:100]}...")
            else:
                print(f"Bio: {bio_text}")
        else:
            print(f"Bio: {bio_text}")
        
        if 'ocr_method_used' in profile_data and profile_data['ocr_method_used'] != 'none':
            print(f"OCR Method Used: {profile_data['ocr_method_used']}")
        
        print(f"\n FILES CREATED:")
        if csv_path:
            print(f"- Profile data (CSV): {csv_path}")
        if json_path:
            print(f"- Profile data (JSON): {json_path}")
        if 'screenshot_path' in profile_data:
            print(f"- Screenshot: {profile_data['screenshot_path']}")
        
        print(f"\n Analysis complete!")
        
        
        
    except Exception as e:
        print(f" Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n Closing browser...")
        driver.quit()

if __name__ == "__main__":
    main()