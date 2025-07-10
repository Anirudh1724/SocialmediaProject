import time
import os
import cv2
import easyocr
import getpass
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

def setup_driver():
    """Setup Chrome driver with appropriate options"""
    options = Options()
    # Remove headless mode to see what's happening
    # options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def login_twitter(driver, username, password):
    """Login to Twitter/X"""
    try:
        driver.get("https://x.com/i/flow/login")
        time.sleep(5)
        
        print(" Logging into Twitter/X...")
        
        # Wait for username field and enter username
        username_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
        )
        username_field.clear()
        username_field.send_keys(username)
        time.sleep(1)
        
        # Click Next button
        next_button = driver.find_element(By.XPATH, "//span[text()='Next']")
        next_button.click()
        time.sleep(3)
        
        # Handle potential phone/email verification step
        try:
            # Check if additional verification is required
            verification_field = driver.find_element(By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
            if verification_field:
                print(" Additional verification required. Please enter your phone number or email:")
                verification_input = input("Enter verification info: ")
                verification_field.send_keys(verification_input)
                
                # Click Next again
                next_button = driver.find_element(By.XPATH, "//span[text()='Next']")
                next_button.click()
                time.sleep(3)
        except:
            pass  # No additional verification needed
        
        # Wait for password field and enter password
        password_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
        )
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)
        
        # Click Login button
        login_button = driver.find_element(By.XPATH, "//span[text()='Log in']")
        login_button.click()
        time.sleep(5)
        
        # Wait for successful login
        WebDriverWait(driver, 30).until(
            lambda d: "home" in d.current_url or "timeline" in d.current_url
        )
        
        print(" Login successful!")
        return True
        
    except Exception as e:
        print(f" Login failed: {e}")
        return False

def take_profile_screenshot(driver, username):
    """Take a screenshot of the profile"""
    try:
        # Create screenshots directory
        os.makedirs("screenshots/twitter", exist_ok=True)
        
        screenshot_path = f"screenshots/twitter/{username}_profile.png"
        driver.save_screenshot(screenshot_path)
        print(f" Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f" Error taking screenshot: {e}")
        return None

def extract_profile_details(driver, target_username):
    """Extract comprehensive profile details from Twitter/X"""
    profile_url = f"https://x.com/{target_username}"
    driver.get(profile_url)
    time.sleep(5)
    
    print(f" Extracting profile details for @{target_username}...")
    
    profile_data = {
        'username': target_username,
        'display_name': 'Not Found',
        'verified': 'No',
        'posts_count': 'Not Found',
        'followers_count': 'Not Found',
        'following_count': 'Not Found',
        'date_of_birth': 'Not Found',
        'join_date': 'Not Found',
        'bio': 'Not Found',
        'location': 'Not Found',
        'website': 'Not Found',
        'profile_image_url': 'Not Found',
        'banner_image_url': 'Not Found',
        'pinned_tweet': 'Not Found'
    }
    
    try:
        # Take screenshot first
        screenshot_path = take_profile_screenshot(driver, target_username)
        profile_data['screenshot_path'] = screenshot_path
        
        # Extract display name
        try:
            display_name_selectors = [
                '[data-testid="UserName"] span',
                '[data-testid="UserProfileHeader_Items"] h1',
                'h1[role="heading"]'
            ]
            for selector in display_name_selectors:
                try:
                    name_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if name_element.text and name_element.text != f"@{target_username}":
                        profile_data['display_name'] = name_element.text
                        break
                except:
                    continue
        except Exception as e:
            print(f" Could not extract display name: {e}")
        
        # Check if verified
        try:
            verified_selectors = [
                '[data-testid="icon-verified"]',
                'svg[aria-label="Verified account"]',
                '[aria-label="Verified account"]'
            ]
            for selector in verified_selectors:
                try:
                    driver.find_element(By.CSS_SELECTOR, selector)
                    profile_data['verified'] = 'Yes'
                    break
                except:
                    continue
        except:
            pass
        
        # Extract follower stats
        try:
            # Look for stats in the profile header
            stats_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/following"], a[href*="/verified_followers"]')
            
            for link in stats_links:
                link_text = link.text.lower()
                href = link.get_attribute('href')
                
                if 'following' in href and 'following' not in href.split('/')[-1]:
                    # This is followers count
                    followers_text = link.text.split()[0]
                    profile_data['followers_count'] = extract_number_from_text(followers_text)
                elif 'following' in href:
                    # This is following count
                    following_text = link.text.split()[0]
                    profile_data['following_count'] = extract_number_from_text(following_text)
        except Exception as e:
            print(f" Could not extract follower stats: {e}")
        
        # Alternative method for stats extraction
        if profile_data['followers_count'] == 'Not Found':
            try:
                # Look for text patterns like "1.2K Following" or "500 Followers"
                page_text = driver.page_source
                
                # Extract followers
                followers_pattern = r'([\d,]+(?:\.\d+)?[KMB]?)\s+Followers'
                followers_match = re.search(followers_pattern, page_text, re.IGNORECASE)
                if followers_match:
                    profile_data['followers_count'] = extract_number_from_text(followers_match.group(1))
                
                # Extract following
                following_pattern = r'([\d,]+(?:\.\d+)?[KMB]?)\s+Following'
                following_match = re.search(following_pattern, page_text, re.IGNORECASE)
                if following_match:
                    profile_data['following_count'] = extract_number_from_text(following_match.group(1))
            except:
                pass
        
        # Extract bio
        try:
            bio_selectors = [
                '[data-testid="UserDescription"]',
                '[data-testid="UserProfileHeader_Items"] div[dir="auto"]'
            ]
            for selector in bio_selectors:
                try:
                    bio_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if bio_element.text and len(bio_element.text.strip()) > 0:
                        profile_data['bio'] = bio_element.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract location
        try:
            location_selectors = [
                '[data-testid="UserLocation"]',
                'svg[aria-label*="location"] + span',
                'span[data-testid="UserLocation"]'
            ]
            for selector in location_selectors:
                try:
                    location_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if location_element.text:
                        profile_data['location'] = location_element.text
                        break
                except:
                    continue
        except:
            pass
        
        # Extract website
        try:
            website_selectors = [
                '[data-testid="UserUrl"] a',
                'a[rel="noopener noreferrer external"]'
            ]
            for selector in website_selectors:
                try:
                    website_element = driver.find_element(By.CSS_SELECTOR, selector)
                    website_url = website_element.get_attribute('href')
                    if website_url:
                        profile_data['website'] = website_url
                        break
                except:
                    continue
        except:
            pass
        
        # Extract join date
        try:
            join_date_selectors = [
                '[data-testid="UserJoinDate"]',
                'span[data-testid="UserJoinDate"]'
            ]
            for selector in join_date_selectors:
                try:
                    join_element = driver.find_element(By.CSS_SELECTOR, selector)
                    join_text = join_element.text
                    if 'Joined' in join_text:
                        profile_data['join_date'] = join_text.replace('Joined ', '')
                        break
                except:
                    continue
        except:
            pass
        
        # Extract profile image URL
        try:
            img_selectors = [
                '[data-testid="UserAvatar-Container-undefined"] img',
                'img[alt*="profile"]',
                'div[data-testid="UserAvatar-Container-undefined"] img'
            ]
            for selector in img_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    img_src = img_element.get_attribute('src')
                    if img_src and 'profile_images' in img_src:
                        profile_data['profile_image_url'] = img_src
                        break
                except:
                    continue
        except:
            pass
        
        # Try to extract posts count by looking at tweets tab
        try:
            # Scroll down a bit to load tweets
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)
            
            # Look for posts/tweets in the timeline
            tweets = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
            if tweets:
                profile_data['recent_tweets_visible'] = len(tweets)
        except:
            pass
        
        # Extract date of birth (usually not publicly visible unless in bio)
        # This is typically private information and not displayed publicly
        
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

def save_profile_to_csv(profile_data, filename):
    """Save profile data to CSV file"""
    try:
        profile_df = pd.DataFrame([profile_data])
        profile_df.to_csv(filename, index=False, encoding='utf-8')
        print(f" Profile data saved to {filename}")
    except Exception as e:
        print(f" Error saving to CSV: {e}")

def save_profile_to_json(profile_data, filename):
    """Save profile data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        print(f" Profile data saved to {filename}")
    except Exception as e:
        print(f" Error saving to JSON: {e}")

def extract_from_screenshot_ocr(image_path):
    """Extract additional data from screenshot using OCR"""
    try:
        reader = easyocr.Reader(['en'], gpu=True)
        results = reader.readtext(image_path)
        texts = [text[1] for text in results if len(text) > 1]
        
        ocr_data = {
            'followers_ocr': 0,
            'following_ocr': 0,
            'posts_ocr': 0,
            'extracted_text': ' '.join(texts)
        }
        
        # Look for followers/following patterns in OCR text
        full_text = ' '.join(texts).lower()
        
        # Extract followers
        followers_patterns = [
            r'(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)\s+followers',
            r'(\d+(?:,\d+)*)\s+followers'
        ]
        for pattern in followers_patterns:
            match = re.search(pattern, full_text)
            if match:
                ocr_data['followers_ocr'] = extract_number_from_text(match.group(1))
                break
        
        # Extract following
        following_patterns = [
            r'(\d+(?:,\d+)*(?:\.\d+)?[kmb]?)\s+following',
            r'(\d+(?:,\d+)*)\s+following'
        ]
        for pattern in following_patterns:
            match = re.search(pattern, full_text)
            if match:
                ocr_data['following_ocr'] = extract_number_from_text(match.group(1))
                break
        
        return ocr_data
        
    except Exception as e:
        print(f" OCR extraction failed: {e}")
        return {'followers_ocr': 0, 'following_ocr': 0, 'posts_ocr': 0, 'extracted_text': ''}

def main():
    print(" Twitter/X Profile Analyzer")
    print("=" * 50)
    
    # Get login credentials
    login_username = input("Enter your Twitter/X username or email: ")
    login_password = getpass.getpass("Enter your Twitter/X password: ")
    target_username = input("Enter target Twitter/X username (without @): ")
    
    # Setup driver
    driver = setup_driver()
    
    try:
        # Login to Twitter
        if not login_twitter(driver, login_username, login_password):
            print(" Failed to login. Exiting...")
            return
        
        # Extract profile details
        print(f"\n Analyzing @{target_username}...")
        profile_data = extract_profile_details(driver, target_username)
        
        # Add OCR analysis if screenshot was taken
        if 'screenshot_path' in profile_data and profile_data['screenshot_path']:
            print(" Running OCR analysis on screenshot...")
            ocr_data = extract_from_screenshot_ocr(profile_data['screenshot_path'])
            profile_data.update(ocr_data)
            
            # Use OCR data as backup if main extraction failed
            if profile_data['followers_count'] == 'Not Found' and ocr_data['followers_ocr'] > 0:
                profile_data['followers_count'] = ocr_data['followers_ocr']
            if profile_data['following_count'] == 'Not Found' and ocr_data['following_ocr'] > 0:
                profile_data['following_count'] = ocr_data['following_ocr']
        
        # Add extraction timestamp
        profile_data['extraction_timestamp'] = datetime.now().isoformat()
        
        # Save data to files
        print("\n Saving extracted data...")
        csv_filename = f"{target_username}_twitter_profile.csv"
        json_filename = f"{target_username}_twitter_profile.json"
        
        save_profile_to_csv(profile_data, csv_filename)
        save_profile_to_json(profile_data, json_filename)
        
        # Display results
        print("\n" + "="*60)
        print(" TWITTER PROFILE ANALYSIS RESULTS")
        print("="*60)
        
        print(f"\n PROFILE INFORMATION:")
        print(f"Username: @{profile_data['username']}")
        print(f"Display Name: {profile_data['display_name']}")
        print(f"Verified: {profile_data['verified']}")
        print(f"Followers: {profile_data['followers_count']}")
        print(f"Following: {profile_data['following_count']}")
        print(f"Posts Count: {profile_data['posts_count']}")
        print(f"Join Date: {profile_data['join_date']}")
        print(f"Date of Birth: {profile_data['date_of_birth']}")
        print(f"Location: {profile_data['location']}")
        print(f"Website: {profile_data['website']}")
        
        bio_text = profile_data['bio']
        if len(str(bio_text)) > 100:
            print(f"Bio: {bio_text[:100]}...")
        else:
            print(f"Bio: {bio_text}")
        
        print(f"\n FILES CREATED:")
        print(f"- Profile data (CSV): {csv_filename}")
        print(f"- Profile data (JSON): {json_filename}")
        if 'screenshot_path' in profile_data:
            print(f"- Screenshot: {profile_data['screenshot_path']}")
        
        print(f"\n Analysis complete!")
        
    except Exception as e:
        print(f" Error during analysis: {e}")
    finally:
        print("\n Closing browser...")
        driver.quit()

if __name__ == "__main__":
    main()