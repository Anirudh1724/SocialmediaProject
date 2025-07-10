import time
import os
import cv2
import easyocr
import re
import json
import csv
import pandas as pd
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import requests
from PIL import Image
import pytesseract
from urllib.parse import quote
import getpass

def login_to_quora(driver, email, password):
    """Improved login function for Quora with better element detection"""
    try:
        print(" Logging into Quora...")
        driver.get("https://www.quora.com/")
        time.sleep(8)
        
        # Try direct login URL first
        print(" Navigating to login page...")
        driver.get("https://www.quora.com/login")
        time.sleep(8)
        
        wait = WebDriverWait(driver, 20)
        
        # Step 1: Find and fill email field
        print(" Looking for email field...")
        email_field = None
        email_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="mail" i]',
            'input[data-testid*="email"]',
            'input[id*="email"]',
            'input[class*="email"]'
        ]
        
        for selector in email_selectors:
            try:
                email_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                if email_field.is_displayed() and email_field.is_enabled():
                    print(f" Found email field with selector: {selector}")
                    break
            except:
                continue
        
        if not email_field:
            print(" Could not find email field")
            return False
        
        # Clear and enter email
        try:
            email_field.clear()
            time.sleep(1)
            email_field.send_keys(email)
            print(" Email entered successfully")
            time.sleep(2)
        except Exception as e:
            print(f" Error entering email: {e}")
            return False
        
        # Step 2: Find and fill password field
        print(" Looking for password field...")
        password_field = None
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[placeholder*="password" i]',
            'input[data-testid*="password"]',
            'input[id*="password"]',
            'input[class*="password"]'
        ]
        
        for selector in password_selectors:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                if password_field.is_displayed() and password_field.is_enabled():
                    print(f" Found password field with selector: {selector}")
                    break
            except:
                continue
        
        if not password_field:
            print(" Could not find password field")
            # Try clicking on email field to trigger password field appearance
            try:
                email_field.click()
                time.sleep(2)
                for selector in password_selectors:
                    try:
                        password_field = driver.find_element(By.CSS_SELECTOR, selector)
                        if password_field.is_displayed() and password_field.is_enabled():
                            print(f" Found password field after email click: {selector}")
                            break
                    except:
                        continue
            except:
                pass
        
        if not password_field:
            print(" Still could not find password field")
            return False
        
        # Clear and enter password
        try:
            password_field.clear()
            time.sleep(1)
            password_field.send_keys(password)
            print(" Password entered successfully")
            time.sleep(2)
        except Exception as e:
            print(f" Error entering password: {e}")
            return False
        
        # Step 3: Find and click login button
        print(" Looking for login button...")
        submit_button = None
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button[data-testid*="login"]',
            'button[class*="login"]',
            'div[role="button"][data-testid*="login"]'
        ]
        
        # First try finding by text content
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                btn_text = btn.text.lower().strip()
                if btn_text in ["login", "log in", "sign in"] and btn.is_displayed() and btn.is_enabled():
                    submit_button = btn
                    print(f" Found login button by text: '{btn.text}'")
                    break
        except:
            pass
        
        # If not found by text, try selectors
        if not submit_button:
            for selector in submit_selectors:
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        print(f" Found login button with selector: {selector}")
                        break
                except:
                    continue
        
        # Submit the form
        if submit_button:
            try:
                # Scroll to button first
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(1)
                # Try clicking
                submit_button.click()
                print(" Login button clicked")
            except:
                try:
                    # Try JavaScript click
                    driver.execute_script("arguments[0].click();", submit_button)
                    print(" Login button clicked via JavaScript")
                except:
                    # Try pressing Enter on password field
                    password_field.send_keys(Keys.RETURN)
                    print(" Submitted via Enter key")
        else:
            # Try pressing Enter on password field as fallback
            password_field.send_keys(Keys.RETURN)
            print(" Submitted via Enter key (fallback)")
        
        print(" Waiting for login to complete...")
        time.sleep(10)
        
        # Step 4: Verify login success
        print(" Verifying login success...")
        
        # Check for common success indicators
        success_indicators = [
            # Profile/user menu indicators
            'div[class*="profile"]',
            'button[class*="profile"]',
            'img[class*="profile"]',
            'div[class*="user"]',
            'a[href*="/profile/"]',
            # Navigation indicators
            'nav[class*="main"]',
            'div[class*="navigation"]',
            # Content indicators
            'div[class*="feed"]',
            'div[class*="home"]'
        ]
        
        login_successful = False
        
        for indicator in success_indicators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    for elem in elements:
                        if elem.is_displayed():
                            print(f" Login success indicator found: {indicator}")
                            login_successful = True
                            break
                    if login_successful:
                        break
            except:
                continue
        
        # Additional check: URL should not contain "login"
        current_url = driver.current_url.lower()
        if "login" not in current_url and "quora.com" in current_url:
            print(" URL indicates successful login")
            login_successful = True
        
        # Check for error messages
        try:
            error_selectors = [
                'div[class*="error"]',
                'span[class*="error"]',
                'div[class*="alert"]',
                'div[role="alert"]'
            ]
            
            for selector in error_selectors:
                try:
                    error_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if error_elem.is_displayed() and error_elem.text.strip():
                        print(f" Potential error message: {error_elem.text}")
                except:
                    continue
        except:
            pass
        
        if login_successful:
            print(" Login successful!")
            return True
        else:
            print(" Login verification failed")
            print(f"Current URL: {driver.current_url}")
            
            # Take a screenshot for debugging
            try:
                driver.save_screenshot("login_debug.png")
                print(" Debug screenshot saved as 'login_debug.png'")
            except:
                pass
            
            return False
            
    except Exception as e:
        print(f" Login failed with exception: {e}")
        import traceback
        traceback.print_exc()
        
        # Take a screenshot for debugging
        try:
            driver.save_screenshot("login_error.png")
            print(" Error screenshot saved as 'login_error.png'")
        except:
            pass
        
        return False

def setup_driver():
    """Enhanced Chrome driver setup with better options for Quora"""
    options = Options()
    
    # Keep visible for debugging (comment out for headless)
    # options.add_argument("--headless=new")
    
    # Window and display options
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    
    # Anti-detection options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Permissions and security
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    
    # Additional options for stability
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    
    # Create driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Execute script to remove webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def get_random_questions(driver, num_questions=3):
    """Get random questions from Quora feed"""
    try:
        print(f" Looking for {num_questions} random questions...")
        
        # Go to home page
        driver.get("https://www.quora.com/")
        time.sleep(5)
        
        # Scroll down to load more content
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Find question elements
        question_selectors = [
            'div[class*="question"]',
            'a[class*="question"]',
            'div[data-testid*="question"]',
            'span[class*="question_text"]',
            'div[class*="QuestionText"]',
            'a[href*="/q/"]',
            'div[class*="feed_item"]'
        ]
        
        all_questions = []
        for selector in question_selectors:
            try:
                questions = driver.find_elements(By.CSS_SELECTOR, selector)
                if questions:
                    # Filter for actual question elements
                    valid_questions = []
                    for q in questions:
                        try:
                            # Check if element contains question-like content
                            text = q.text.strip()
                            if text and len(text) > 10 and ('?' in text or len(text.split()) > 3):
                                valid_questions.append(q)
                        except:
                            continue
                    
                    if valid_questions:
                        all_questions.extend(valid_questions)
                        break
            except:
                continue
        
        if not all_questions:
            print(" No questions found on the page")
            return []
        
        print(f" Found {len(all_questions)} questions on the page")
        
        # Select random questions
        selected_questions = random.sample(all_questions, min(num_questions, len(all_questions)))
        print(f" Selected {len(selected_questions)} random questions")
        
        return selected_questions
        
    except Exception as e:
        print(f" Error getting random questions: {e}")
        return []

def extract_question_data(driver, question_element, question_number):
    """Extract comprehensive data from a question"""
    try:
        print(f"\n Analyzing question #{question_number}...")
        
        # Scroll question into view and click
        driver.execute_script("arguments[0].scrollIntoView(true);", question_element)
        time.sleep(2)
        
        # Try to click on the question
        try:
            question_element.click()
        except:
            try:
                driver.execute_script("arguments[0].click();", question_element)
            except:
                # Find a clickable link within the element
                links = question_element.find_elements(By.TAG_NAME, "a")
                if links:
                    links[0].click()
        
        time.sleep(5)
        
        question_data = {
            'question_number': question_number,
            'question_url': driver.current_url,
            'question_text': 'Not Found',
            'question_views': 'Not Found',
            'question_followers': 'Not Found',
            'question_topics': [],
            'question_author': 'Not Found',
            'question_author_url': 'Not Found',
            'question_date': 'Not Found',
            'total_answers': 0,
            'answers_data': [],
            'related_questions': [],
            'extraction_timestamp': datetime.now().isoformat()
        }
        
        # Extract question text
        try:
            question_text_selectors = [
                'span[class*="question_text"]',
                'div[class*="QuestionText"]',
                'h1[class*="question"]',
                'div[data-testid*="question"]',
                'span[class*="rendered_qtext"]'
            ]
            
            for selector in question_text_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text.strip():
                        question_data['question_text'] = element.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract question statistics
        try:
            # Views
            view_patterns = [r'(\d+\.?\d*[KM]?)\s*views?', r'(\d+,?\d+)\s*views?']
            page_text = driver.page_source
            for pattern in view_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    question_data['question_views'] = matches[0]
                    break
            
            # Followers
            follower_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'follow') and contains(text(), 'question')]")
            for elem in follower_elements:
                text = elem.text.lower()
                numbers = re.findall(r'(\d+\.?\d*[km]?)', text)
                if numbers:
                    question_data['question_followers'] = numbers[0]
                    break
        except:
            pass
        
        # Extract topics/tags
        try:
            topic_selectors = [
                'a[class*="topic"]',
                'span[class*="topic"]',
                'div[class*="topic"] a',
                'a[href*="/topic/"]'
            ]
            
            topics = []
            for selector in topic_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        topic_text = elem.text.strip()
                        if topic_text and topic_text not in topics and len(topic_text) < 50:
                            topics.append(topic_text)
                    if topics:
                        break
                except:
                    continue
            
            question_data['question_topics'] = topics[:10]  # Limit to 10 topics
        except:
            pass
        
        # Extract question author
        try:
            author_selectors = [
                'a[class*="author"]',
                'span[class*="author"] a',
                'div[class*="author"] a',
                'a[href*="/profile/"]'
            ]
            
            for selector in author_selectors:
                try:
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if author_elem.text.strip():
                        question_data['question_author'] = author_elem.text.strip()
                        question_data['question_author_url'] = author_elem.get_attribute('href')
                        break
                except:
                    continue
        except:
            pass
        
        # Extract answers
        try:
            print(" Extracting answers...")
            answers_data = extract_answers_data(driver)
            question_data['answers_data'] = answers_data
            question_data['total_answers'] = len(answers_data)
            print(f" Found {len(answers_data)} answers")
        except Exception as e:
            print(f" Error extracting answers: {e}")
        
        # Extract related questions
        try:
            related_selectors = [
                'div[class*="related"] a',
                'div[class*="similar"] a',
                'a[class*="question"][href*="/q/"]'
            ]
            
            related_questions = []
            for selector in related_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        href = elem.get_attribute('href')
                        if text and href and '?' in text and len(related_questions) < 5:
                            related_questions.append({
                                'question': text,
                                'url': href
                            })
                    if related_questions:
                        break
                except:
                    continue
            
            question_data['related_questions'] = related_questions
        except:
            pass
        
        return question_data
        
    except Exception as e:
        print(f" Error extracting question data: {e}")
        return None

def extract_answers_data(driver):
    """Extract detailed data from answers"""
    answers_data = []
    
    try:
        # Scroll down to load more answers
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Find answer elements
        answer_selectors = [
            'div[class*="answer"]',
            'div[data-testid*="answer"]',
            'div[class*="Answer"]',
            'div[class*="AnswerBase"]'
        ]
        
        answer_elements = []
        for selector in answer_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    answer_elements = elements
                    break
            except:
                continue
        
        for i, answer_elem in enumerate(answer_elements[:5]):  # Limit to 5 answers
            try:
                answer_data = {
                    'answer_number': i + 1,
                    'author_name': 'Not Found',
                    'author_url': 'Not Found',
                    'author_credentials': 'Not Found',
                    'answer_text': 'Not Found',
                    'answer_length': 0,
                    'upvotes': 'Not Found',
                    'answer_date': 'Not Found',
                    'comments_count': 0,
                    'shares': 'Not Found'
                }
                
                # Extract author information
                try:
                    author_selectors = [
                        'a[class*="author"]',
                        'span[class*="author"] a',
                        'div[class*="author"] a'
                    ]
                    
                    for selector in author_selectors:
                        try:
                            author_elem = answer_elem.find_element(By.CSS_SELECTOR, selector)
                            answer_data['author_name'] = author_elem.text.strip()
                            answer_data['author_url'] = author_elem.get_attribute('href')
                            break
                        except:
                            continue
                    
                    # Extract author credentials
                    cred_selectors = [
                        'span[class*="credential"]',
                        'div[class*="credential"]',
                        'span[class*="bio"]'
                    ]
                    
                    for selector in cred_selectors:
                        try:
                            cred_elem = answer_elem.find_element(By.CSS_SELECTOR, selector)
                            if cred_elem.text.strip():
                                answer_data['author_credentials'] = cred_elem.text.strip()
                                break
                        except:
                            continue
                except:
                    pass
                
                # Extract answer text
                try:
                    text_selectors = [
                        'div[class*="answer_text"]',
                        'span[class*="rendered_qtext"]',
                        'div[class*="AnswerText"]',
                        'div[class*="content"]'
                    ]
                    
                    for selector in text_selectors:
                        try:
                            text_elem = answer_elem.find_element(By.CSS_SELECTOR, selector)
                            if text_elem.text.strip():
                                answer_text = text_elem.text.strip()
                                answer_data['answer_text'] = answer_text[:500] + "..." if len(answer_text) > 500 else answer_text
                                answer_data['answer_length'] = len(answer_text)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Extract upvotes
                try:
                    upvote_selectors = [
                        'button[class*="upvote"]',
                        'span[class*="upvote"]',
                        'div[class*="upvote"]'
                    ]
                    
                    for selector in upvote_selectors:
                        try:
                            upvote_elem = answer_elem.find_element(By.CSS_SELECTOR, selector)
                            upvote_text = upvote_elem.text.strip()
                            if upvote_text and upvote_text.isdigit():
                                answer_data['upvotes'] = int(upvote_text)
                                break
                            elif upvote_text:
                                # Extract number from text like "1.2K"
                                numbers = re.findall(r'(\d+\.?\d*[KM]?)', upvote_text)
                                if numbers:
                                    answer_data['upvotes'] = numbers[0]
                                    break
                        except:
                            continue
                except:
                    pass
                
                # Extract comments count
                try:
                    comment_elements = answer_elem.find_elements(By.XPATH, ".//*[contains(text(), 'comment')]")
                    for elem in comment_elements:
                        text = elem.text.lower()
                        numbers = re.findall(r'(\d+)', text)
                        if numbers and 'comment' in text:
                            answer_data['comments_count'] = int(numbers[0])
                            break
                except:
                    pass
                
                answers_data.append(answer_data)
                
            except Exception as e:
                print(f" Error extracting answer {i+1}: {e}")
                continue
    
    except Exception as e:
        print(f" Error in extract_answers_data: {e}")
    
    return answers_data

def extract_user_profile_data(driver, profile_url):
    """Extract detailed user profile information"""
    try:
        print(f" Extracting profile data from: {profile_url}")
        driver.get(profile_url)
        time.sleep(5)
        
        profile_data = {
            'profile_url': profile_url,
            'name': 'Not Found',
            'bio': 'Not Found',
            'followers': 'Not Found',
            'following': 'Not Found',
            'answers_count': 'Not Found',
            'questions_count': 'Not Found',
            'profile_image_url': 'Not Found',
            'credentials': [],
            'spaces_count': 'Not Found',
            'posts_count': 'Not Found',
            'profile_views': 'Not Found'
        }
        
        # Extract name
        try:
            name_selectors = [
                'h1[class*="name"]',
                'span[class*="name"]',
                'div[class*="ProfileNameAndBio"] h1'
            ]
            
            for selector in name_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.text.strip():
                        profile_data['name'] = elem.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract bio
        try:
            bio_selectors = [
                'div[class*="bio"]',
                'span[class*="bio"]',
                'div[class*="ProfileNameAndBio"] div'
            ]
            
            for selector in bio_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.text.strip() and len(elem.text.strip()) > 10:
                        profile_data['bio'] = elem.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract statistics
        try:
            stats_text = driver.page_source
            
            # Extract followers
            follower_patterns = [r'(\d+\.?\d*[KM]?)\s*followers?', r'(\d+,?\d+)\s*followers?']
            for pattern in follower_patterns:
                matches = re.findall(pattern, stats_text, re.IGNORECASE)
                if matches:
                    profile_data['followers'] = matches[0]
                    break
            
            # Extract following
            following_patterns = [r'(\d+\.?\d*[KM]?)\s*following', r'(\d+,?\d+)\s*following']
            for pattern in following_patterns:
                matches = re.findall(pattern, stats_text, re.IGNORECASE)
                if matches:
                    profile_data['following'] = matches[0]
                    break
            
            # Extract answers count
            answer_patterns = [r'(\d+\.?\d*[KM]?)\s*answers?', r'(\d+,?\d+)\s*answers?']
            for pattern in answer_patterns:
                matches = re.findall(pattern, stats_text, re.IGNORECASE)
                if matches:
                    profile_data['answers_count'] = matches[0]
                    break
        except:
            pass
        
        # Extract profile image
        try:
            img_selectors = [
                'img[class*="profile"]',
                'img[class*="avatar"]',
                'div[class*="ProfilePhoto"] img'
            ]
            
            for selector in img_selectors:
                try:
                    img_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    img_src = img_elem.get_attribute('src')
                    if img_src:
                        profile_data['profile_image_url'] = img_src
                        break
                except:
                    continue
        except:
            pass
        
        return profile_data
        
    except Exception as e:
        print(f" Error extracting profile data: {e}")
        return None

def take_screenshot(driver, filename):
    """Take a screenshot of the current page"""
    try:
        os.makedirs("screenshots/quora", exist_ok=True)
        screenshot_path = f"screenshots/quora/{filename}"
        driver.save_screenshot(screenshot_path)
        print(f" Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f" Error taking screenshot: {e}")
        return None

def save_data_to_csv(data, filename):
    """Save extracted data to CSV file"""
    try:
        os.makedirs("data/quora", exist_ok=True)
        filepath = f"data/quora/{filename}"
        
        # Flatten nested data for CSV
        flattened_data = []
        for item in data:
            flat_item = item.copy()
            
            # Handle nested answer data
            if 'answers_data' in flat_item:
                # Keep only summary info for CSV
                flat_item['top_answer_author'] = flat_item['answers_data'][0]['author_name'] if flat_item['answers_data'] else 'None'
                flat_item['top_answer_upvotes'] = flat_item['answers_data'][0]['upvotes'] if flat_item['answers_data'] else 'None'
                del flat_item['answers_data']
            
            # Convert lists to strings
            for key, value in flat_item.items():
                if isinstance(value, list):
                    flat_item[key] = '; '.join(str(v) for v in value)
            
            flattened_data.append(flat_item)
        
        df = pd.DataFrame(flattened_data)
        df.to_csv(filepath, index=False, encoding='utf-8')
        print(f" Data saved to {filepath}")
        return filepath
    except Exception as e:
        print(f" Error saving to CSV: {e}")
        return None

def save_data_to_json(data, filename):
    """Save extracted data to JSON file"""
    try:
        os.makedirs("data/quora", exist_ok=True)
        filepath = f"data/quora/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f" Data saved to {filepath}")
        return filepath
    except Exception as e:
        print(f" Error saving to JSON: {e}")
        return None

def main():
    print("🔍 Quora Data Analyzer - Comprehensive Question & Profile Extractor")
    print("=" * 80)
    
    # Get login credentials
    email = input("Enter your Quora email: ").strip()
    if not email:
        print(" No email provided. Exiting...")
        return
    
    password = getpass.getpass("Enter your Quora password: ")
    if not password:
        print(" No password provided. Exiting...")
        return
    
    # Setup driver
    print(" Setting up browser...")
    driver = setup_driver()
    
    try:
        # Login to Quora
        login_success = login_to_quora(driver, email, password)
        
        if not login_success:
            print(" Login failed. Please check your credentials and try again.")
            return
        
        # Take screenshot of home page
        take_screenshot(driver, "quora_home_page.png")
        
        # Get random questions
        questions = get_random_questions(driver, num_questions=3)
        
        if not questions:
            print(" Could not find any questions to analyze.")
            return
        
        # Extract comprehensive data from each question
        all_data = []
        
        for i, question in enumerate(questions, 1):
            try:
                question_data = extract_question_data(driver, question, i)
                
                if question_data:
                    all_data.append(question_data)
                    
                    # Take screenshot of the question page
                    take_screenshot(driver, f"question_{i}_analysis.png")
                    
                    print(f" Question {i} data extracted successfully")
                else:
                    print(f" Failed to extract data for question {i}")
                
                # Go back to home page for next question
                if i < len(questions):
                    driver.get("https://www.quora.com/")
                    time.sleep(3)
                    
            except Exception as e:
                print(f" Error processing question {i}: {e}")
                continue
        
        if not all_data:
            print(" No data was extracted.")
            return
        
        # Save data to files
        print("\n Saving extracted data...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"quora_analysis_{timestamp}.csv"
        json_filename = f"quora_analysis_{timestamp}.json"
        
        csv_path = save_data_to_csv(all_data, csv_filename)
        json_path = save_data_to_json(all_data, json_filename)
        
        # Display comprehensive results
        print("\n" + "="*80)
        print(" QUORA COMPREHENSIVE ANALYSIS RESULTS")
        print("="*80)
        
        for i, data in enumerate(all_data, 1):
            print(f"\n QUESTION {i} ANALYSIS:")
            print(f"Question: {data['question_text'][:100]}...")
            print(f"URL: {data['question_url']}")
            print(f"Topics: {', '.join(data['question_topics'][:5])}")
            print(f"Views: {data['question_views']}")
            print(f"Followers: {data['question_followers']}")
            print(f"Total Answers: {data['total_answers']}")
            print(f"Question Author: {data['question_author']}")
            
            if data['answers_data']:
                print(f"\n TOP ANSWERS:")
                for j, answer in enumerate(data['answers_data'][:3], 1):
                    print(f"  Answer {j}:")
                    print(f"  Author: {answer['author_name']}")
                    print(f"  Credentials: {answer['author_credentials']}")
                    print(f"  Upvotes: {answer['upvotes']}")
                    print(f"  Length: {answer['answer_length']} characters")
                    print(f"  Comments: {answer['comments_count']}")
                    if answer['answer_text'] != 'Not Found':
                        preview = answer['answer_text'][:150] + "..." if len(answer['answer_text']) > 150 else answer['answer_text']
                        print(f"    Preview: {preview}")
            
            if data['related_questions']:
                print(f"\n RELATED QUESTIONS:")
                for j, related in enumerate(data['related_questions'][:3], 1):
                    print(f"  {j}. {related['question'][:80]}...")
        
        print(f"\n FILES CREATED:")
        if csv_path:
            print(f"- Comprehensive data (CSV): {csv_path}")
        if json_path:
            print(f"- Comprehensive data (JSON): {json_path}")
        print(f"- Screenshots saved in: screenshots/quora/")
        
        # Summary statistics
        total_answers = sum(len(data['answers_data']) for data in all_data)
        total_topics = sum(len(data['question_topics']) for data in all_data)
        
        print(f"\n EXTRACTION SUMMARY:")
        print(f"- Questions analyzed: {len(all_data)}")
        print(f"- Total answers extracted: {total_answers}")
        print(f"- Total topics identified: {total_topics}")
        print(f"- Average answers per question: {total_answers/len(all_data):.1f}")
        
        print(f"\n Analysis complete! Comprehensive Quora data extraction finished.")
        
    except Exception as e:
        print(f" Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n Closing browser...")
        driver.quit()

def extract_trending_topics(driver):
    """Extract trending topics from Quora"""
    try:
        print(" Extracting trending topics...")
        driver.get("https://www.quora.com/")
        time.sleep(3)
        
        trending_topics = []
        topic_selectors = [
            'div[class*="trending"] a',
            'div[class*="topic"] a',
            'a[href*="/topic/"]'
        ]
        
        for selector in topic_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    topic_text = elem.text.strip()
                    topic_url = elem.get_attribute('href')
                    if topic_text and topic_url and len(topic_text) < 50:
                        trending_topics.append({
                            'topic': topic_text,
                            'url': topic_url
                        })
                if trending_topics:
                    break
            except:
                continue
        
        return trending_topics[:10]  # Return top 10
        
    except Exception as e:
        print(f" Error extracting trending topics: {e}")
        return []

def extract_space_data(driver, space_url):
    """Extract data from a Quora Space"""
    try:
        print(f" Extracting space data from: {space_url}")
        driver.get(space_url)
        time.sleep(5)
        
        space_data = {
            'space_url': space_url,
            'space_name': 'Not Found',
            'space_description': 'Not Found',
            'followers': 'Not Found',
            'posts_count': 'Not Found',
            'contributors': 'Not Found',
            'space_image_url': 'Not Found',
            'recent_posts': []
        }
        
        # Extract space name
        try:
            name_selectors = [
                'h1[class*="space"]',
                'h1[class*="Space"]',
                'div[class*="SpaceHeader"] h1'
            ]
            
            for selector in name_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.text.strip():
                        space_data['space_name'] = elem.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract space description
        try:
            desc_selectors = [
                'div[class*="space_description"]',
                'div[class*="SpaceDescription"]',
                'p[class*="description"]'
            ]
            
            for selector in desc_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.text.strip():
                        space_data['space_description'] = elem.text.strip()
                        break
                except:
                    continue
        except:
            pass
        
        # Extract statistics
        try:
            stats_text = driver.page_source.lower()
            
            # Followers
            follower_patterns = [r'(\d+\.?\d*[km]?)\s*followers?', r'(\d+,?\d+)\s*followers?']
            for pattern in follower_patterns:
                matches = re.findall(pattern, stats_text)
                if matches:
                    space_data['followers'] = matches[0]
                    break
            
            # Posts
            post_patterns = [r'(\d+\.?\d*[km]?)\s*posts?', r'(\d+,?\d+)\s*posts?']
            for pattern in post_patterns:
                matches = re.findall(pattern, stats_text)
                if matches:
                    space_data['posts_count'] = matches[0]
                    break
        except:
            pass
        
        return space_data
        
    except Exception as e:
        print(f" Error extracting space data: {e}")
        return None

def search_quora_topic(driver, topic_name):
    """Search for a specific topic on Quora and extract related data"""
    try:
        print(f" Searching for topic: {topic_name}")
        
        # Navigate to search
        search_url = f"https://www.quora.com/search?q={quote(topic_name)}"
        driver.get(search_url)
        time.sleep(5)
        
        topic_data = {
            'topic_name': topic_name,
            'search_url': search_url,
            'top_questions': [],
            'top_answers': [],
            'related_topics': []
        }
        
        # Extract top questions from search results
        try:
            question_elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/q/"]')
            for elem in question_elements[:5]:
                question_text = elem.text.strip()
                question_url = elem.get_attribute('href')
                if question_text and question_url:
                    topic_data['top_questions'].append({
                        'question': question_text,
                        'url': question_url
                    })
        except:
            pass
        
        return topic_data
        
    except Exception as e:
        print(f" Error searching topic: {e}")
        return None

def extract_notification_data(driver):
    """Extract notification data if available"""
    try:
        print(" Checking notifications...")
        
        # Look for notification bell or menu
        notification_selectors = [
            'div[class*="notification"]',
            'button[class*="notification"]',
            'a[class*="notification"]'
        ]
        
        notifications = []
        for selector in notification_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                if elem.is_displayed():
                    elem.click()
                    time.sleep(2)
                    
                    # Extract notification items
                    notif_items = driver.find_elements(By.CSS_SELECTOR, 'div[class*="notification_item"]')
                    for item in notif_items[:5]:
                        notif_text = item.text.strip()
                        if notif_text:
                            notifications.append(notif_text)
                    break
            except:
                continue
        
        return notifications
        
    except Exception as e:
        print(f" Error extracting notifications: {e}")
        return []

def extract_user_activity_data(driver, profile_url):
    """Extract detailed user activity data"""
    try:
        print(f" Extracting user activity data...")
        driver.get(profile_url)
        time.sleep(5)
        
        activity_data = {
            'recent_answers': [],
            'recent_questions': [],
            'recent_posts': [],
            'activity_timeline': []
        }
        
        # Look for activity sections
        activity_selectors = [
            'div[class*="activity"]',
            'div[class*="Activity"]',
            'div[class*="timeline"]'
        ]
        
        for selector in activity_selectors:
            try:
                activity_section = driver.find_element(By.CSS_SELECTOR, selector)
                
                # Extract recent activities
                activity_items = activity_section.find_elements(By.CSS_SELECTOR, 'div[class*="item"]')
                for item in activity_items[:10]:
                    activity_text = item.text.strip()
                    if activity_text:
                        activity_data['activity_timeline'].append({
                            'activity': activity_text,
                            'timestamp': 'Not Found'  # Could be extracted if timestamp elements are found
                        })
                
                if activity_data['activity_timeline']:
                    break
            except:
                continue
        
        return activity_data
        
    except Exception as e:
        print(f" Error extracting activity data: {e}")
        return None

# Additional utility functions for enhanced data extraction

def extract_question_metrics(driver):
    """Extract detailed metrics for the current question"""
    try:
        metrics = {
            'total_views': 'Not Found',
            'unique_viewers': 'Not Found',
            'shares': 'Not Found',
            'bookmarks': 'Not Found',
            'last_activity': 'Not Found'
        }
        
        # Look for various metric indicators
        metric_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'view') or contains(text(), 'share') or contains(text(), 'bookmark')]")
        
        for elem in metric_elements:
            text = elem.text.lower()
            if 'view' in text:
                numbers = re.findall(r'(\d+\.?\d*[km]?)', text)
                if numbers:
                    metrics['total_views'] = numbers[0]
            elif 'share' in text:
                numbers = re.findall(r'(\d+\.?\d*[km]?)', text)
                if numbers:
                    metrics['shares'] = numbers[0]
        
        return metrics
        
    except Exception as e:
        print(f" Error extracting question metrics: {e}")
        return {}

def extract_answer_quality_metrics(driver, answer_element):
    """Extract quality metrics for an answer"""
    try:
        quality_metrics = {
            'helpful_votes': 'Not Found',
            'not_helpful_votes': 'Not Found',
            'credibility_score': 'Not Found',
            'answer_ranking': 'Not Found'
        }
        
        # Look for quality indicators within the answer element
        quality_elements = answer_element.find_elements(By.XPATH, ".//*[contains(text(), 'helpful') or contains(text(), 'credible')]")
        
        for elem in quality_elements:
            text = elem.text.lower()
            if 'helpful' in text:
                numbers = re.findall(r'(\d+)', text)
                if numbers:
                    quality_metrics['helpful_votes'] = numbers[0]
        
        return quality_metrics
        
    except Exception as e:
        return {}

if __name__ == "__main__":
    main()