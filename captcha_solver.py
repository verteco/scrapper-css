import time
import os
import threading
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import setup_logging
import re

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

def extract_recaptcha_site_key(driver):
    """
    Extract the reCAPTCHA site key from the page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        str: reCAPTCHA site key if found, None otherwise
    """
    try:
        # Method 1: Look for data-sitekey attribute in g-recaptcha div
        recaptcha_divs = driver.find_elements(By.CSS_SELECTOR, ".g-recaptcha, .grecaptcha-badge")
        for div in recaptcha_divs:
            site_key = div.get_attribute("data-sitekey")
            if site_key:
                logger.info(f"Found reCAPTCHA site key in div: {site_key}")
                return site_key
        
        # Method 2: Look for site key in page source using regex
        page_source = driver.page_source
        # Pattern for reCAPTCHA v2 and v3
        patterns = [
            r'data-sitekey="([^"]+)"',
            r"data-sitekey='([^']+)'",
            r'grecaptcha.execute\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'grecaptcha.enterprise.execute\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'render=([^&"\']+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_source)
            if matches:
                logger.info(f"Found reCAPTCHA site key using regex: {matches[0]}")
                return matches[0]
        
        # Method 3: Check for site key in recaptcha.net or google.com/recaptcha URLs
        scripts = driver.find_elements(By.TAG_NAME, "script")
        for script in scripts:
            src = script.get_attribute("src")
            if src and ("recaptcha" in src or "google.com/recaptcha" in src):
                # Extract key from URL if present
                key_match = re.search(r'render=([^&"\']+)', src)
                if key_match:
                    logger.info(f"Found reCAPTCHA site key in script src: {key_match.group(1)}")
                    return key_match.group(1)
        
        logger.warning("Could not find reCAPTCHA site key")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting reCAPTCHA site key: {e}")
        return None

def detect_recaptcha_version(driver):
    """
    Detect the version of reCAPTCHA on the page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        str: 'v2', 'v3', or None if not detected
    """
    try:
        page_source = driver.page_source
        
        # Check for v3
        if "grecaptcha.execute" in page_source or "grecaptcha.enterprise.execute" in page_source:
            return "v3"
            
        # Check for invisible v2
        invisible_indicators = [
            'data-size="invisible"',
            "data-callback",
            "grecaptcha.execute()"
        ]
        for indicator in invisible_indicators:
            if indicator in page_source:
                return "v2"
        
        # Check for standard v2
        if "g-recaptcha" in page_source or "grecaptcha.render" in page_source:
            return "v2"
            
        # Check for v2 checkbox
        checkboxes = driver.find_elements(By.CSS_SELECTOR, ".recaptcha-checkbox-border")
        if checkboxes:
            return "v2"
            
        # Default to v2 if we're on a CAPTCHA page but couldn't determine version
        if "/sorry/index" in driver.current_url or "unusual traffic" in page_source:
            return "v2"
            
        return None
        
    except Exception as e:
        logger.error(f"Error detecting reCAPTCHA version: {e}")
        return "v2"  # Default to v2 if detection fails

def solve_recaptcha_with_2captcha(driver):
    """
    Solve reCAPTCHA using 2Captcha service.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        bool: True if CAPTCHA was solved, False otherwise
    """
    if not API_KEY:
        logger.warning("No 2captcha API key provided. CAPTCHA solving is disabled.")
        return False
        
    try:
        # Get the current URL
        url = driver.current_url
        logger.info(f"Solving reCAPTCHA on URL: {url}")
        print(f"[2CAPTCHA] Solving reCAPTCHA on URL: {url}")
        
        # Skip automatic solving for Google Search CAPTCHA
        if "/sorry/index" in url and "google.com/search" in url:
            logger.info("Detected Google Search CAPTCHA page, skipping automatic solving")
            print("[2CAPTCHA] Detected Google Search CAPTCHA page which is not supported by 2Captcha")
            print("[2CAPTCHA] See: https://2captcha.com/blog/google-search-recaptcha")
            return False
        
        # Extract site key
        site_key = extract_recaptcha_site_key(driver)
        if not site_key:
            logger.warning("Could not extract reCAPTCHA site key, falling back to manual solving")
            print("[2CAPTCHA] Could not extract reCAPTCHA site key, falling back to manual solving")
            return False
            
        # Detect reCAPTCHA version
        version = detect_recaptcha_version(driver)
        logger.info(f"Detected reCAPTCHA version: {version}")
        print(f"[2CAPTCHA] Detected reCAPTCHA version: {version}")
        
        # Solve using 2captcha
        logger.info(f"Solving {version} reCAPTCHA with site key: {site_key}")
        print(f"[2CAPTCHA] Solving {version} reCAPTCHA with site key: {site_key}")
        print(f"[2CAPTCHA] This may take up to 2 minutes, please wait...")
        
        try:
            if version == "v3":
                print(f"[2CAPTCHA] Using V3 solving method with score 0.7")
                result = solver.recaptcha(
                    sitekey=site_key,
                    url=url,
                    version='v3',
                    action='verify',
                    score=0.7
                )
            else:  # v2
                invisible = (version == "v2" and "invisible" in driver.page_source)
                print(f"[2CAPTCHA] Using V2 solving method, invisible={invisible}")
                result = solver.recaptcha(
                    sitekey=site_key,
                    url=url,
                    invisible=invisible
                )
                
            token = result.get('code')
            logger.info("Successfully obtained reCAPTCHA token from 2captcha")
            print(f"[2CAPTCHA] Successfully obtained reCAPTCHA token: {token[:15]}...")
            
            # Execute JavaScript to set the token and submit the form
            print("[2CAPTCHA] Applying token to page and submitting form...")
            script = f"""
            try {{
                // Find and set g-recaptcha-response textarea
                var gResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (gResponse) {{
                    gResponse.innerHTML = "{token}";
                    gResponse.value = "{token}";
                    console.log("Set g-recaptcha-response value");
                }} else {{
                    console.log("Could not find g-recaptcha-response element");
                }}
                
                // Try to submit the form if it exists
                var forms = document.getElementsByTagName('form');
                if (forms.length > 0) {{
                    console.log("Found form, submitting...");
                    forms[0].submit();
                    return "Form submitted";
                }}
                
                // For Google's dedicated CAPTCHA page
                var submitButton = document.querySelector('input[type="submit"]');
                if (submitButton) {{
                    console.log("Found submit button, clicking...");
                    submitButton.click();
                    return "Submit button clicked";
                }}
                
                return "No form or submit button found";
            }} catch (e) {{
                return "Error: " + e.message;
            }}
            """
            
            result = driver.execute_script(script)
            logger.info(f"Executed JavaScript to set token and submit form. Result: {result}")
            print(f"[2CAPTCHA] JavaScript execution result: {result}")
            
            # Wait for page to change
            current_url = driver.current_url
            print(f"[2CAPTCHA] Waiting for page to change from: {current_url}")
            time.sleep(5)  # Wait for form submission and page load
            
            # Check if URL changed (indicating successful CAPTCHA solving)
            if driver.current_url != current_url:
                logger.info(f"Page URL changed after CAPTCHA solving: {driver.current_url}")
                print(f"[2CAPTCHA] Success! Page URL changed to: {driver.current_url}")
                return True
                
            # Check if CAPTCHA elements are no longer present
            if not is_captcha_present(driver):
                logger.info("CAPTCHA elements no longer present, indicating success")
                print("[2CAPTCHA] Success! CAPTCHA elements no longer present")
                return True
                
            logger.warning("CAPTCHA may not have been solved successfully")
            print("[2CAPTCHA] Warning: CAPTCHA may not have been solved successfully")
            return False
            
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA with 2captcha: {e}")
            print(f"[2CAPTCHA] Error solving reCAPTCHA: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error in solve_recaptcha_with_2captcha: {e}")
        print(f"[2CAPTCHA] Error in solve_recaptcha_with_2captcha: {e}")
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
        # Check if we're on Google's dedicated CAPTCHA page
        if "/sorry/index" in driver.current_url:
            print("Detected Google's dedicated CAPTCHA page")
            return True
            
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
            if any(phrase in driver.page_source for phrase in [
                "Please verify you're a human",
                "Our systems have detected unusual traffic",
                "unusual traffic from your computer network"
            ]):
                return True
        
        # Check for specific text indicating CAPTCHA, but be more selective
        page_text = driver.page_source.lower()
        captcha_indicators = [
            "please complete the security check",
            "i'm not a robot",
            "verify you are human",
            "security verification",
            "complete the captcha",
            "unusual traffic",
            "detected unusual traffic",
            "systems have detected unusual"
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
        print("\n" + "="*50)
        print("CAPTCHA detected, attempting to solve...")
        print("="*50)
        logger.info(f"Saved CAPTCHA screenshot to {screenshot_path}")
        
        # Bring window to foreground for CAPTCHA solving
        try:
            driver.maximize_window()
            print("Browser window maximized for CAPTCHA solving")
        except Exception as e:
            print(f"Could not maximize window: {e}")
        
        # First, try to solve automatically with 2captcha
        if API_KEY:
            print("\n" + "="*50)
            print("ATTEMPTING AUTOMATIC CAPTCHA SOLVING WITH 2CAPTCHA")
            print("="*50)
            if solve_recaptcha_with_2captcha(driver):
                print("\n" + "="*50)
                print("CAPTCHA SOLVED AUTOMATICALLY WITH 2CAPTCHA!")
                print("="*50 + "\n")
                
                # Minimize window again after solving
                try:
                    driver.minimize_window()
                except:
                    pass
                    
                return True
            else:
                print("\n" + "="*50)
                print("AUTOMATIC CAPTCHA SOLVING FAILED, FALLING BACK TO MANUAL SOLVING")
                print("="*50)
        
        # Fall back to manual solving if automatic solving fails or no API key
        if "/sorry/index" in driver.current_url:
            print("\n" + "="*50)
            print("GOOGLE DEDICATED CAPTCHA PAGE DETECTED")
            print("Please complete the CAPTCHA challenge on the dedicated page:")
            print("1. Solve the CAPTCHA puzzle (images, checkbox, etc.)")
            print("2. Click the 'Submit' button")
            print("3. Wait until you are redirected to the search results")
            print("="*50 + "\n")
        else:
            # For Google's image selection CAPTCHA, we need manual intervention
            print("\n" + "="*50)
            print("MANUAL CAPTCHA SOLVING REQUIRED")
            print("Please complete ALL steps of the CAPTCHA challenge:")
            print("1. Click the checkbox 'I'm not a robot'")
            print("2. If prompted, select ALL matching images (e.g., all cars, traffic lights, etc.)")
            print("3. Continue selecting images until the verification is complete")
            print("="*50 + "\n")
        
        # Wait for manual intervention with extended timeout for image selection
        input_result = input_with_timeout("Press Enter ONLY AFTER completing ALL steps of the CAPTCHA challenge...", 120)
        
        if input_result:
            print("Thank you for solving the CAPTCHA!")
            
            # Verify if CAPTCHA was actually solved
            time.sleep(2)  # Give time for the page to update
            
            # Check if we're still on the CAPTCHA page
            if "/sorry/index" in driver.current_url:
                print("Still on the CAPTCHA page. Please complete the challenge and submit.")
                input_with_timeout("Press Enter when you've been redirected to the search results...", 120)
            elif "unusual traffic" in driver.page_source or "detected unusual traffic" in driver.page_source:
                print("CAPTCHA may not be fully solved yet. Please complete all verification steps.")
                input_with_timeout("Press Enter when ALL verification steps are complete...", 120)
        
        # Minimize window again after solving
        try:
            driver.minimize_window()
        except:
            pass
            
        return True
    else:
        # No CAPTCHA detected
        return True
