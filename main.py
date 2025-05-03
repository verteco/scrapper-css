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

def scrape_all_urls(driver, product_name, first_run):
    """
    Scrapes all URLs from Google Shopping results for a given product name.
    """
    try:
        print(f"Scraping all URLs for: {product_name[:20]}")
        
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
        country = "Slovakia"  # Default country
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
            print(f"Could not detect country, using default: {country}. Error: {str(e)}")
            
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

        # Attempt to find shopping tab and click it if available
        try:
            shopping_tab = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'tbm=shop') or contains(text(), 'Shopping')]"))
            )
            print("Found Shopping tab, clicking it...")
            shopping_tab.click()
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"No Shopping tab found or couldn't click it: {str(e)}")

        # Collect all URLs inside 'pla-unit-container'
        print("Collecting all URLs inside 'pla-unit-container'...") 
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all shopping containers
        shopping_containers = soup.find_all("div", {"class": "pla-unit-container"})
        print(f"Found {len(shopping_containers)} shopping containers")
        
        # If no shopping containers found, try to search with "buy" keyword
        if len(shopping_containers) == 0 and "buy" not in product_name.lower():
            print("No shopping results found. Trying with 'buy' keyword...")
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.clear()
            search_box.send_keys(f"buy {product_name}")
            search_box.send_keys(Keys.RETURN)
            
            # Wait for search results to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
            time.sleep(random.uniform(0.3, 0.8))
            
            # Try to click shopping tab again
            try:
                shopping_tab = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'tbm=shop') or contains(text(), 'Shopping')]"))
                )
                print("Found Shopping tab, clicking it...")
                shopping_tab.click()
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"No Shopping tab found or couldn't click it: {str(e)}")
            
            # Get updated page source
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find all shopping containers again
            shopping_containers = soup.find_all("div", {"class": "pla-unit-container"})
            print(f"Found {len(shopping_containers)} shopping containers after adding 'buy' keyword")
        
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
                        
                        # Send lead to CSS Leads API
                        send_lead_to_api(country, base_url, "", comparison_service)
        
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

def initialize_browser():
    """
    Initialize Chrome browser with appropriate options.
    """
    try:
        # Try regular ChromeDriver first since undetected_chromedriver has compatibility issues
        print("Initializing regular ChromeDriver...")
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1920, 1080)
        
        return driver
    except Exception as e:
        logger.error(f"Error initializing regular ChromeDriver: {e}")
        print(f"Error initializing regular ChromeDriver: {e}")
        
        # Fallback to undetected_chromedriver
        print("Falling back to undetected_chromedriver...")
        try:
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
            
            # Add user agent
            options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
            
            # Create the undetected ChromeDriver
            driver = uc.Chrome(options=options)
            
            # Set window size
            driver.set_window_size(1920, 1080)
            
            return driver
        except Exception as e:
            logger.error(f"Error initializing undetected_chromedriver: {e}")
            print(f"Error initializing undetected_chromedriver: {e}")
            raise

def main():
    try:
        while True:  # Run indefinitely
            print("\n" + "="*50)
            print(f"Starting new scraping cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50 + "\n")
            
            # Read products from file (get a fresh random selection each cycle)
            products = read_products(f"{ACTUAL_FOLDER}/product-categories.txt")
            
            # Initialize browser
            driver = None
            try:
                driver = initialize_browser()
                first_run = True
                
                # Process each product
                for product_name in products:
                    try:
                        # Scrape URLs from Google Shopping
                        urls = scrape_all_urls(driver, product_name, first_run)
                        
                        # Wait a bit before next product to avoid rate limiting
                        time.sleep(random.uniform(2, 5))
                        
                        first_run = False
                    except Exception as e:
                        logger.error(f"Error processing product '{product_name}': {e}")
                        print(f"Error processing product '{product_name}': {e}")
                        
                        # Check if browser is still alive
                        try:
                            driver.current_url  # This will throw an exception if the browser is closed
                        except:
                            print("Browser appears to be closed. Restarting browser...")
                            if driver:
                                try:
                                    driver.quit()
                                except:
                                    pass  # Ignore errors when trying to quit a dead browser
                            driver = initialize_browser()
                            first_run = True
                        
                        # Continue with next product
                        continue
                    
            except Exception as e:
                logger.error(f"Browser error: {e}")
                print(f"Browser error: {e}")
            finally:
                # Close the browser after processing all products
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass  # Ignore errors when trying to quit
                
            print("\n" + "="*50)
            print(f"Completed scraping cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Waiting 10 minutes before starting next cycle...")
            print("="*50 + "\n")
            
            # Wait 10 minutes before starting the next cycle
            time.sleep(600)
    
    except KeyboardInterrupt:
        print("\nScript stopped by user. Exiting gracefully...")
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}")
        print(f"Critical error: {e}")
        # If a critical error occurs, wait a bit and then restart
        time.sleep(60)
        main()  # Restart the main function

if __name__ == "__main__":
    main()
