import time
import os
import threading
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import setup_logging

logger = setup_logging()

# Replace with your 2captcha API key
API_KEY = "13832cc8573b312c74040fdd708b41a0"  # 2captcha API key

# Initialize the solver only if API key is provided
solver = TwoCaptcha(API_KEY) if API_KEY else None

# Global variable to track if manual input was provided
manual_input_provided = False

def input_with_timeout(prompt, timeout=30):
    """
    Get input from user with a timeout.
    
    Args:
        prompt: Text to display to the user
        timeout: Timeout in seconds
        
    Returns:
        bool: True if input was provided, False if timeout occurred
    """
    global manual_input_provided
    manual_input_provided = False
    
    def get_input():
        global manual_input_provided
        input(prompt)
        manual_input_provided = True
    
    # Start a thread to get input
    input_thread = threading.Thread(target=get_input)
    input_thread.daemon = True
    input_thread.start()
    
    # Wait for the thread to complete or timeout
    input_thread.join(timeout)
    
    if manual_input_provided:
        return True
    else:
        print(f"\nTimeout after {timeout} seconds. Continuing without manual CAPTCHA solving...")
        return False

def solve_recaptcha(driver, timeout=120):
    """
    Solves reCAPTCHA v2 on the current page.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait for CAPTCHA solution
        
    Returns:
        bool: True if CAPTCHA was solved, False otherwise
    """
    if not API_KEY:
        logger.warning("No 2captcha API key provided. CAPTCHA solving is disabled.")
        return False
        
    try:
        logger.info("Detecting reCAPTCHA...")
        
        # Take a screenshot for debugging
        screenshot_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "captcha_screenshot.png")
        driver.save_screenshot(screenshot_path)
        logger.info(f"Saved CAPTCHA screenshot to {screenshot_path}")
        
        # For Google's specific CAPTCHA
        if "google.com" in driver.current_url:
            try:
                # Try to find the Google CAPTCHA iframe
                frames = driver.find_elements(By.TAG_NAME, "iframe")
                for frame in frames:
                    if "recaptcha" in frame.get_attribute("src").lower():
                        logger.info("Found Google reCAPTCHA iframe")
                        driver.switch_to.frame(frame)
                        
                        # Click on the CAPTCHA checkbox
                        WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, ".recaptcha-checkbox-border"))
                        ).click()
                        
                        # Switch back to main content
                        driver.switch_to.default_content()
                        
                        # Wait for CAPTCHA to be solved or for image challenge
                        time.sleep(5)
                        
                        # Check if we need to solve an image challenge
                        image_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[title*='recaptcha challenge']")
                        if image_frames:
                            logger.info("Image challenge detected, waiting for manual intervention")
                            print("Image challenge detected. Please solve it manually in the browser window.")
                            print("Press Enter when you've completed the CAPTCHA...")
                            input()
                            return True
                        
                        # Check if CAPTCHA was solved
                        try:
                            WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".recaptcha-checkbox-checked"))
                            )
                            logger.info("CAPTCHA checkbox is checked, verification successful")
                            return True
                        except:
                            logger.info("CAPTCHA verification may not be complete, continuing anyway")
                            return True
                
                logger.warning("Could not find Google reCAPTCHA iframe")
                return False
                
            except Exception as e:
                logger.error(f"Error handling Google CAPTCHA: {e}")
                return False
        
        # Standard reCAPTCHA handling for other sites
        # Wait for reCAPTCHA iframe to be present
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title*='reCAPTCHA']"))
        )
        
        logger.info("reCAPTCHA detected, attempting to solve...")
        
        # Get the site key
        site_key = None
        try:
            # Try to find the site key in the reCAPTCHA iframe
            recaptcha_iframe = driver.find_element(By.CSS_SELECTOR, "iframe[title*='reCAPTCHA']")
            site_key = recaptcha_iframe.get_attribute("src").split("k=")[1].split("&")[0]
        except:
            # If not found in iframe, try to find it in the page source
            page_source = driver.page_source
            if "data-sitekey" in page_source:
                site_key = page_source.split('data-sitekey="')[1].split('"')[0]
        
        if not site_key:
            logger.error("Could not find reCAPTCHA site key")
            return False
            
        logger.info(f"Found site key: {site_key}")
        
        # Get the page URL
        page_url = driver.current_url
        
        # Send the CAPTCHA to 2captcha for solving
        logger.info("Sending CAPTCHA to 2captcha for solving...")
        result = solver.recaptcha(
            sitekey=site_key,
            url=page_url
        )
        
        # Get the solution
        code = result.get('code')
        logger.info(f"Received solution from 2captcha: {code[:10]}...")
        
        # Execute JavaScript to set the CAPTCHA response
        driver.execute_script(f'document.getElementById("g-recaptcha-response").innerHTML="{code}";')
        
        # Sometimes we need to execute additional JavaScript
        driver.execute_script("___grecaptcha_cfg.clients[0].aa.l.callback('{}');".format(code))
        
        logger.info("CAPTCHA solution applied")
        
        # Wait a moment for the form to process the CAPTCHA
        time.sleep(2)
        
        return True
        
    except Exception as e:
        logger.error(f"Error solving CAPTCHA: {e}")
        return False

def is_captcha_present(driver):
    """
    Check if a CAPTCHA is present on the page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        bool: True if CAPTCHA is detected, False otherwise
    """
    try:
        # Check for reCAPTCHA iframe with more specific criteria
        captcha_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[title*='reCAPTCHA']")
        if captcha_iframes:
            # Verify it's actually a CAPTCHA iframe, not just any iframe with "reCAPTCHA" in the title
            for iframe in captcha_iframes:
                src = iframe.get_attribute("src")
                if src and "google.com/recaptcha" in src:
                    return True
            
        # Check for Google's specific CAPTCHA with more specific criteria
        if "google.com" in driver.current_url:
            # Look for specific elements that indicate a CAPTCHA challenge
            # 1. Check for the CAPTCHA checkbox
            recaptcha_checkboxes = driver.find_elements(By.CSS_SELECTOR, ".recaptcha-checkbox-border")
            if recaptcha_checkboxes:
                return True
                
            # 2. Check for CAPTCHA challenge iframe
            challenge_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[title*='recaptcha challenge']")
            if challenge_frames:
                return True
                
            # 3. Check for specific CAPTCHA text
            if "Please verify you're a human" in driver.page_source:
                return True
        
        # Check for specific text indicating CAPTCHA, but be more selective
        page_text = driver.page_source.lower()
        captcha_indicators = [
            "please complete the security check",
            "i'm not a robot",
            "verify you are human",
            "security verification",
            "complete the captcha"
        ]
        
        for indicator in captcha_indicators:
            if indicator in page_text:
                return True
                
        return False
        
    except Exception as e:
        logger.error(f"Error checking for CAPTCHA: {e}")
        return False

def handle_captcha(driver):
    """
    Detect and solve CAPTCHA if present.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        bool: True if no CAPTCHA or CAPTCHA was solved, False if CAPTCHA solving failed
    """
    # Take a screenshot for debugging
    screenshot_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "captcha_screenshot.png")
    driver.save_screenshot(screenshot_path)
    
    if is_captcha_present(driver):
        logger.info("CAPTCHA detected")
        print("CAPTCHA detected, attempting to solve...")
        logger.info(f"Saved CAPTCHA screenshot to {screenshot_path}")
        
        if not API_KEY:
            logger.warning("No 2captcha API key provided. Please add your API key to captcha_solver.py")
            print(" No 2captcha API key provided. Please add your API key to captcha_solver.py")
            print(" You can get an API key from https://2captcha.com/")
            print(" For now, you'll need to solve CAPTCHAs manually")
            
            # Wait for manual intervention with timeout
            input_with_timeout("Please solve the CAPTCHA manually in the browser window, then press Enter to continue...", 30)
            return True
        
        # Solve the CAPTCHA
        solved = solve_recaptcha(driver)
        
        if solved:
            logger.info("CAPTCHA solved successfully")
            print("CAPTCHA solved successfully")
            return True
        else:
            logger.error("Failed to solve CAPTCHA automatically")
            print("Failed to solve CAPTCHA automatically. Please solve it manually.")
            
            # Fall back to manual solving with timeout
            input_with_timeout("Please solve the CAPTCHA manually in the browser window, then press Enter to continue...", 30)
            return True
    else:
        # No CAPTCHA detected
        return True
