import numpy as np
import pandas as pd
import os
import undetected_chromedriver as uc
from captcha_solver import handle_captcha

from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time
import random
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


from mail_scraper import start_mail_scrapping
from css_leads_api import send_lead_to_api
from logger import setup_logging

logger = setup_logging()

ACTUAL_FOLDER = os.path.dirname(os.path.realpath(__file__))

def read_products(file_path):
    """
    Read product names from a file and return them as a list.
    Now selects products randomly from the file.
    """
    try:
        with open(file_path, 'r') as file:
            products = [line.strip() for line in file if line.strip()]
            
        # Shuffle the products randomly
        import random
        random.shuffle(products)
        
        # Take a subset of products (e.g., 10-20 random products)
        num_products = min(random.randint(10, 20), len(products))
        selected_products = products[:num_products]
        
        print(f"Randomly selected {num_products} products from {len(products)} total products")
        return selected_products
    except Exception as e:
        logger.error(f"Error reading products file: {e}")
        print(f"Error reading products file: {e}")
        return []

def accept_cookies(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Accept all')]"))
        ).click()
        time.sleep(1)
    except:
        pass

def get_base_url(url):
    """
    Extract the base URL from a full URL.
    """
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    return base_url

def scrape_all_urls(driver, product_name, first_run, target_country=None):
    """
    Scrapes all URLs from Google Shopping results for a given product name.
    """
    try:
        print(f"Scraping all URLs for: {product_name[:20]}")
        
        # Ensure window is minimized before navigation
        driver.minimize_window()
        
        # Navigate to Google homepage
        print(f"Navigating to Google homepage for product: {product_name}")
        driver.get("https://www.google.com")
        
        # Accept cookies if consent appears
        print("Accepting cookies if consent appears...")
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Accept all')]"))
            ).click()
            time.sleep(1)
        except:
            pass
        
        # Try to detect country from the Google homepage
        country = target_country  # Use target_country if provided
        try:
            # Wait for the country element to be visible
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "uU7dJb"))
            )
            country_element = driver.find_element(By.CLASS_NAME, "uU7dJb")
            if country_element and country_element.text.strip():
                detected_country = country_element.text.strip()
                print(f"Detected country from Google homepage: {detected_country}")
                country = detected_country
        except Exception as e:
            print(f"Could not detect country. Error: {str(e)}")
            
        # Check for CAPTCHA
        if handle_captcha(driver):
            print("No CAPTCHA detected or CAPTCHA solved successfully")
        else:
            print("CAPTCHA handling failed, but continuing...")
        
        # Search for product
        print(f"Searching for product in {country}: {product_name}")
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_box.clear()
        search_box.send_keys(product_name)
        search_box.send_keys(Keys.RETURN)
        
        # Wait for search results to load
        print("Waiting for search results to load...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
        time.sleep(random.uniform(0.3, 0.8))

        # No longer clicking on Shopping tab - staying on main search results page
        print("Staying on main search results page (not clicking Shopping tab)")
        
        # Check for shopping containers in the main search results
        print("Collecting all URLs from shopping containers...") 
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all shopping containers
        shopping_containers = soup.find_all("div", {"class": "pla-unit-container"})
        print(f"Found {len(shopping_containers)} shopping containers")
        
        # Create a DataFrame to store the results
        results = []
        
        # Keep track of processed URLs to avoid duplicates
        processed_urls = set()
        
        # Process each container
        for i, container in enumerate(shopping_containers, 1):
            print(f"Examining container {i}/{len(shopping_containers)}")
            
            # Extract merchant information
            merchant = "Unknown"
            merchant_element = container.find("div", {"class": ["VuuXrf", "zPEcBd", "KbpByd", "aULzUe"]})
            if merchant_element:
                merchant = merchant_element.text.strip()
                print(f"  Found merchant: {merchant}")
            
            # Extract comparison service information - IMPROVED VERSION
            comparison_service = "Unknown"
            
            # Look for the "By Google" or similar text in the nNuQVc div
            by_service_div = container.find("div", {"class": "nNuQVc"})
            if by_service_div:
                by_service_link = by_service_div.find("a")
                if by_service_link and by_service_link.text:
                    comparison_service = by_service_link.text.strip()
                    print(f"  Found comparison service: {comparison_service}")
            
            # If not found, try other selectors
            if comparison_service == "Unknown":
                # Try to find in OkcyVb class which often contains "By X" text
                by_service_div = container.find("div", {"class": "OkcyVb"})
                if by_service_div and by_service_div.text and "By " in by_service_div.text:
                    comparison_service = by_service_div.text.strip()
                    print(f"  Found comparison service: {comparison_service}")
            
            # If still not found, try the pla-extensions-container
            if comparison_service == "Unknown":
                extensions_container = container.find("div", {"class": "pla-extensions-container"})
                if extensions_container and extensions_container.text and "By " in extensions_container.text:
                    comparison_service = extensions_container.text.strip()
                    print(f"  Found comparison service: {comparison_service}")
            
            # Find all links with class 'plantl'
            plantl_links = container.find_all("a", {"class": "plantl"})
            if plantl_links:
                print(f"  Found {len(plantl_links)} links with class 'plantl'")
                
                # Process each link
                for link in plantl_links:
                    href = link.get("href")
                    if href:
                        # Extract the base URL
                        base_url = get_base_url(href)
                        
                        # Skip if we've already processed this URL
                        if base_url in processed_urls:
                            print(f"  Skipping already processed URL: {base_url}")
                            continue
                        
                        # Add to processed URLs
                        processed_urls.add(base_url)
                        
                        # Extract domain for merchant name if merchant is unknown
                        domain = urlparse(base_url).netloc
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        
                        # Use domain as merchant name if merchant is unknown
                        merchant_name = merchant if merchant != "Unknown" else domain
                        
                        # Add to results
                        results.append({
                            'url': base_url,
                            'merchant': merchant_name,
                            'comparison_service': comparison_service,
                            'country': country
                        })
                        
                        # Print the found e-shop
                        print(f"FOUND E-SHOP: {domain}, Base URL: {base_url}, Merchant: {merchant_name}, Comparison Service: {comparison_service}, Country: {country}")
                        
                        # Send lead to CSS Leads API only if comparison_service is not "Unknown" and country is available
                        if comparison_service != "Unknown" and country:
                            send_lead_to_api(country, base_url, "", comparison_service)
                            print(f"LEAD SENT TO API: {domain}, Comparison Service: {comparison_service}")
                        elif not country:
                            print(f"SKIPPING LEAD (No country detected): {domain}")
                        else:
                            print(f"SKIPPING LEAD (Unknown comparison service): {domain}")
        
        # Create DataFrame from results
        df = pd.DataFrame(results)
        
        # Remove duplicates
        if not df.empty:
            df = df.drop_duplicates(subset=['url'], keep='first')
        
        return df
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
        return pd.DataFrame([], columns=['url', 'merchant', 'comparison_service', 'country'])

def initialize_browser(target_country=None):
    """
    Initialize Chrome browser with appropriate options.
    """
    try:
        # Create browser with stealth mode
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36")
        options.add_argument("--start-minimized")  # Start Chrome minimized
        options.add_argument("--window-position=-32000,-32000")  # Position window far off-screen initially
        
        # Add experimental options to avoid detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Create a custom Chrome driver class that starts minimized
        class MinimizedChromeDriver(webdriver.Chrome):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.minimize_window()  # Minimize immediately upon creation
        
        # Initialize Chrome driver with our custom class
        service = ChromeService(ChromeDriverManager().install())
        driver = MinimizedChromeDriver(service=service, options=options)
        
        # Double-ensure window is minimized and positioned off-screen
        driver.set_window_position(-32000, -32000)  # Position far off-screen
        driver.minimize_window()
        
        # Execute CDP commands to avoid detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            // Overwrite the 'webdriver' property to undefined
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Overwrite the plugins array with a fake one
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Overwrite the languages property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'es']
            });
            """
        })
        
        print(f"Successfully initialized Chrome for {target_country}")
        return driver
    except Exception as e:
        logger.error(f"Critical error in initialize_browser: {e}")
        print(f"Critical error in initialize_browser: {e}")
        
        # Last resort fallback
        print("Critical error occurred. Using basic Chrome without any customization...")
        try:
            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--start-minimized")  # Start minimized even in fallback mode
            options.add_argument("--window-position=-32000,-32000")  # Position far off-screen
            
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.minimize_window()  # Ensure minimized
            print("WARNING: Running with basic Chrome configuration. No customization.")
            return driver
        except Exception as fallback_error:
            # If even the fallback fails, try one more time with absolute minimal options
            logger.error(f"Fallback initialization failed: {fallback_error}")
            print(f"Fallback initialization failed: {fallback_error}")
            print("Attempting absolute minimal Chrome initialization...")
            
            options = Options()
            options.add_argument("--start-minimized")
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.minimize_window()
            return driver

def is_browser_responsive(driver):
    """
    Check if the browser is responsive by trying to get the current URL.
    Returns True if responsive, False otherwise.
    """
    try:
        driver.current_url
        return True
    except Exception:
        # Try multiple recovery methods before giving up
        recovery_methods = [
            # Method 1: Simple refresh
            lambda d: (d.refresh(), time.sleep(1)),
            # Method 2: Navigate to blank page
            lambda d: (d.get("about:blank"), time.sleep(2)),
            # Method 3: Execute JavaScript to stop loading
            lambda d: (d.execute_script("window.stop();"), time.sleep(1)),
            # Method 4: Execute simple JavaScript
            lambda d: (d.execute_script("return navigator.userAgent;"), None),
            # Method 5: Try to switch to default content
            lambda d: (d.switch_to.default_content(), None)
        ]
        
        for i, recovery_method in enumerate(recovery_methods, 1):
            try:
                print(f"Browser recovery attempt {i}/5...")
                recovery_method(driver)
                # Check if browser is now responsive
                driver.current_url
                print(f"Successfully recovered browser with method {i}")
                return True
            except Exception as e:
                print(f"Recovery method {i} failed: {e}")
                continue
        
        print("All browser recovery methods failed")
        return False

def is_browser_stuck(driver, start_time, timeout=60):
    """
    Check if the browser has been on the same page for too long.
    Returns True if stuck, False otherwise.
    """
    if time.time() - start_time > timeout:
        print(f"Browser appears to be stuck on {driver.current_url} for more than {timeout} seconds")
        
        # Try multiple recovery methods before declaring it stuck
        recovery_methods = [
            # Method 1: Simple refresh
            lambda d: (d.refresh(), time.sleep(2)),
            # Method 2: Navigate to blank page and back
            lambda d: (d.get("about:blank"), time.sleep(1), d.back(), time.sleep(2)),
            # Method 3: Execute JavaScript to stop loading and reload
            lambda d: (d.execute_script("window.stop(); location.reload(true);"), time.sleep(3)),
            # Method 4: Clear cookies and cache via JavaScript
            lambda d: (d.execute_script("localStorage.clear(); sessionStorage.clear();"), d.refresh(), time.sleep(2))
        ]
        
        for i, recovery_method in enumerate(recovery_methods, 1):
            try:
                print(f"Stuck browser recovery attempt {i}/{len(recovery_methods)}...")
                recovery_method(driver)
                # Check if we can interact with the page after recovery
                driver.execute_script("return document.readyState")
                print(f"Successfully recovered stuck browser with method {i}")
                return False
            except Exception as e:
                print(f"Stuck recovery method {i} failed: {e}")
                continue
        
        print("All stuck browser recovery methods failed")
        return True
    return False

def main():
    try:
        # Choose a target country for this instance
        target_country = random.choice([
            "Austria", "Belgium", "Czechia", "Denmark", "Finland", "France", 
            "Germany", "Greece", "Hungary", "Ireland", "Italy", "Netherlands", 
            "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Spain", 
            "Sweden", "Switzerland", "United Kingdom"
        ])
        print(f"Selected target country for this instance: {target_country}")
        
        # Track countries we've already tried in this session to avoid immediate repeats
        tried_countries = set([target_country])
        
        while True:  # Run indefinitely
            print("\n" + "="*50)
            print(f"Starting new scraping cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} for {target_country}")
            print("="*50 + "\n")
            
            # Read products from file (get a fresh random selection each cycle)
            products = read_products(f"{ACTUAL_FOLDER}/product-categories.txt")
            
            # Track when the current page was loaded
            page_start_time = time.time()
            first_run = True
            
            # Initialize browser
            driver = None
            try:
                driver = initialize_browser(target_country)
                
                # Counter for consecutive searches with no results
                no_results_counter = 0
                
                # Process each product
                for product_name in products:
                    try:
                        # Check if browser is responsive and not stuck
                        browser_unresponsive = not is_browser_responsive(driver)
                        browser_stuck = is_browser_stuck(driver, page_start_time)
                        
                        if browser_unresponsive or browser_stuck:
                            # Try one final extreme recovery attempt before restarting
                            try:
                                print("Browser is still unresponsive or stuck. Attempting extreme recovery...")
                                # Try a series of last-resort recovery methods
                                
                                # 1. Try to clear all alerts
                                try:
                                    driver.switch_to.alert.accept()
                                except:
                                    pass
                                
                                # 2. Try to get a completely fresh page
                                driver.get("data:,")  # Minimal valid page
                                time.sleep(1)
                                
                                # 3. Try to execute a complex JavaScript operation
                                driver.execute_script("""
                                    // Clear all intervals and timeouts
                                    for (let i = 0; i < 1000; i++) {
                                        clearInterval(i);
                                        clearTimeout(i);
                                    }
                                    // Clear storage
                                    try { localStorage.clear(); } catch(e) {}
                                    try { sessionStorage.clear(); } catch(e) {}
                                    // Reset history
                                    try { history.go(0); } catch(e) {}
                                    return true;
                                """)
                                
                                # 4. Check if we can still interact with the browser
                                time.sleep(2)
                                driver.execute_script("return window.navigator.userAgent")
                                
                                print("Successfully recovered browser with extreme recovery methods")
                                # Reset the page start time
                                page_start_time = time.time()
                                
                                # Continue with next product instead of trying to use this browser for the current product
                                print(f"Skipping product '{product_name}' after extreme recovery")
                                continue
                                
                            except Exception as e:
                                # We've tried everything, only now do we restart the browser
                                print(f"Extreme recovery failed: {e}. Reluctantly restarting browser...")
                                
                                # Count browser restarts
                                browser_restart_count = browser_restart_count + 1 if 'browser_restart_count' in locals() else 1
                                print(f"Browser restart count: {browser_restart_count}")
                                
                                # Only restart if we haven't restarted too many times in this session
                                if browser_restart_count <= 5:  # Limit browser restarts
                                    if driver:
                                        try:
                                            driver.quit()
                                        except:
                                            pass  # Ignore errors when trying to quit a dead browser
                                    driver = initialize_browser(target_country)
                                    first_run = True
                                    page_start_time = time.time()
                                    driver.minimize_window()  # Ensure window is minimized after restart
                                else:
                                    print("Too many browser restarts. Skipping this product instead.")
                                    continue
                        # Scrape URLs from Google Shopping
                        urls = scrape_all_urls(driver, product_name, first_run, target_country)
                        
                        # Check if we found any results
                        if urls.empty:
                            no_results_counter += 1
                            print(f"No results found for this product. Consecutive searches with no results: {no_results_counter}")
                            
                            # If we've had 10 consecutive searches with no results, get a new set of products
                            if no_results_counter >= 10:
                                print("\n" + "="*50)
                                print(f"No results found in {no_results_counter} consecutive searches. Getting a new set of products.")
                                print("="*50 + "\n")
                                
                                # Also rotate to a new country if we're having trouble with the current one
                                old_country = target_country
                                
                                # Choose a country we haven't tried recently
                                available_countries = [c for c in [
                                    "Austria", "Belgium", "Czechia", "Denmark", "Finland", "France", 
                                    "Germany", "Greece", "Hungary", "Ireland", "Italy", "Netherlands", 
                                    "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Spain", 
                                    "Sweden", "Switzerland", "United Kingdom"
                                ] if c not in tried_countries]
                                
                                # If we've tried all countries, reset the tried countries set
                                if not available_countries:
                                    print("We've tried all countries. Resetting the country rotation.")
                                    tried_countries = set([target_country])
                                    available_countries = [c for c in [
                                        "Austria", "Belgium", "Czechia", "Denmark", "Finland", "France", 
                                        "Germany", "Greece", "Hungary", "Ireland", "Italy", "Netherlands", 
                                        "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Spain", 
                                        "Sweden", "Switzerland", "United Kingdom"
                                    ] if c != target_country]
                                
                                target_country = random.choice(available_countries)
                                tried_countries.add(target_country)
                                
                                print(f"Switching target country from {old_country} to {target_country}")
                                
                                # Restart the browser with the new country
                                if driver:
                                    try:
                                        driver.quit()
                                    except:
                                        pass
                                driver = initialize_browser(target_country)
                                first_run = True
                                page_start_time = time.time()
                                driver.minimize_window()  # Ensure window is minimized after restart
                                
                                break  # Break out of the for loop to get a new set of products
                        else:
                            # Reset the counter if we found results
                            no_results_counter = 0
                        
                        # Update the page start time after successful scraping
                        page_start_time = time.time()
                        
                        # Wait a bit before next product to avoid rate limiting
                        time.sleep(random.uniform(2, 5))
                        
                        first_run = False
                    except Exception as e:
                        logger.error(f"Error processing product '{product_name}': {e}")
                        print(f"Error processing product '{product_name}': {e}")
                        
                        # Check if browser is still alive
                        if not is_browser_responsive(driver):
                            print("Browser appears to be closed. Restarting browser...")
                            if driver:
                                try:
                                    driver.quit()
                                except:
                                    pass  # Ignore errors when trying to quit a dead browser
                            driver = initialize_browser(target_country)
                            first_run = True
                            page_start_time = time.time()
                            driver.minimize_window()  # Ensure window is minimized after restart
                            
                        # Continue with next product
                        continue
                
                # Occasionally rotate country even if we're getting results (every 3-5 cycles)
                if random.randint(1, 5) <= 2:  # 40% chance to rotate country
                    old_country = target_country
                    
                    # Choose a country we haven't tried recently
                    available_countries = [c for c in [
                        "Austria", "Belgium", "Czechia", "Denmark", "Finland", "France", 
                        "Germany", "Greece", "Hungary", "Ireland", "Italy", "Netherlands", 
                        "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Spain", 
                        "Sweden", "Switzerland", "United Kingdom"
                    ] if c not in tried_countries]
                    
                    # If we've tried all countries, reset the tried countries set
                    if not available_countries:
                        print("We've tried all countries. Resetting the country rotation.")
                        tried_countries = set([target_country])
                        available_countries = [c for c in [
                            "Austria", "Belgium", "Czechia", "Denmark", "Finland", "France", 
                            "Germany", "Greece", "Hungary", "Ireland", "Italy", "Netherlands", 
                            "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Spain", 
                            "Sweden", "Switzerland", "United Kingdom"
                        ] if c != target_country]
                    
                    target_country = random.choice(available_countries)
                    tried_countries.add(target_country)
                    
                    print(f"\nProactively rotating country from {old_country} to {target_country} for next cycle")
                    
                    # Restart the browser with the new country
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    driver = initialize_browser(target_country)
                    driver.minimize_window()  # Ensure window is minimized after restart
                
                print("\n" + "="*50)
                print(f"Completed scraping cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} for {target_country}")
                print(f"Waiting 10 seconds before starting next cycle...")
                print("="*50 + "\n")
                
                # Wait 10 seconds before starting the next cycle
                time.sleep(10)
            
            except Exception as e:
                logger.error(f"Browser error: {e}")
                print(f"Browser error: {e}")
                # Only quit the browser if we're exiting the program or if there's a critical error
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass  # Ignore errors when trying to quit a dead browser
    
    except KeyboardInterrupt:
        print("\nScript stopped by user. Exiting gracefully...")
        if driver:
            try:
                driver.quit()
            except:
                pass
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}")
        print(f"Critical error: {e}")
        # If a critical error occurs, wait a bit and then restart
        time.sleep(60)
        main()  # Restart the main function

if __name__ == "__main__":
    main()
