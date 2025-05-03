import re  # Use re instead of regex
import random
import traceback
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from email_validator import validate_email, EmailNotValidError
from selenium import webdriver
from selenium.webdriver.common.by import By

import pandas as pd

from logger import setup_logging

logger = setup_logging()

def find_emails(text):
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    return set(re.findall(email_pattern, text))

def extract_email_from_page(driver, url):
    """
    Extract email from a page using Selenium driver.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL of the page
        
    Returns:
        str: Email address if found, '-' otherwise
    """
    try:
        logger.info(f"--Scrapper--Extracting email from page: {url}")
        
        # Get page source
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find emails in the page
        email_addresses = find_emails(str(soup))
        logger.info(f"--Scrapper-- Found {len(email_addresses)} potential email addresses in {url}")
        
        # Validate emails
        if email_addresses:
            for email in email_addresses:
                try:
                    validate_email(email)
                    if len(email.split("@")[0]) > 20:
                        raise EmailNotValidError
                    logger.info(f"--Scrapper--Contact email for {url}: {email}")
                    return email  # Return the first valid email
                except EmailNotValidError:
                    logger.debug(f'--Scrapper--Email validation error for url: {url} and email {email}')
                    continue
        
        return '-'  # No valid email found
        
    except Exception as e:
        logger.error(f"--Scrapper--Error extracting email from {url}: {e}")
        return '-'

def start_mail_scrapping(driver, url):
    """
    Extract email from a page using Selenium driver.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL of the page
        
    Returns:
        str: Email address if found, '-' otherwise
    """
    try:
        logger.debug('--Scrapper--Starting E-mail scrapper for URL: ' + url)
        
        # Extract email from the current page
        email = extract_email_from_page(driver, url)
        
        # If no email found on the main page, try to find contact page
        if email == '-':
            logger.info(f"--Scrapper--No email found on main page, looking for contact page")
            
            # Try to find contact page links
            contact_links = []
            for link in driver.find_elements(By.TAG_NAME, 'a'):
                href = link.get_attribute('href')
                text = link.text.lower()
                if href and any(keyword in text for keyword in ['contact', 'kontakt', 'about', 'o nas']):
                    contact_links.append(href)
            
            # Visit contact pages and look for emails
            for contact_url in contact_links[:3]:  # Limit to first 3 contact pages
                try:
                    logger.info(f"--Scrapper--Checking contact page: {contact_url}")
                    driver.get(contact_url)
                    email = extract_email_from_page(driver, contact_url)
                    if email != '-':
                        break
                except Exception as e:
                    logger.error(f"--Scrapper--Error checking contact page {contact_url}: {e}")
                    continue
        
        logger.debug("--Scrapper--E-mail scrapper finished for URL: " + url)
        return email
        
    except Exception as e:
        logger.error(f"--Scrapper--Error in email scraping for {url}: {e}")
        return '-'

# Example usage:
if __name__ == "__main__":
    # Create a new instance of the Chrome driver
    driver = webdriver.Chrome()
    
    # URL to scrape
    url = 'http://example.com'
    
    # Start the email scraper
    email = start_mail_scrapping(driver, url)
    
    # Close the browser window
    driver.quit()
