import requests
import pandas as pd
import datetime
import numpy as np
import json

from logger import setup_logging

logger = setup_logging()

# CSS Leads API endpoint
CSS_LEADS_ADD_LEAD_URL = 'https://coldleads.verteco.shop/api/add-lead'

def send_lead_to_api(country, url, email, comparator):
    """
    Send a single lead to the CSS Leads API using the /api/add-lead endpoint.
    
    Args:
        country (str): Country of the lead
        url (str): Shop URL
        email (str): Contact email (can be empty)
        comparator (str): Comparison service name
        
    Returns:
        bool: True if successful, False otherwise
    """
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_text = f"Found on Google on {current_time}"
    
    # Handle email value
    if isinstance(email, float) and np.isnan(email):
        email_value = ""
    elif email in ['-', 'np.nan', None, '']:
        email_value = ""
    else:
        email_value = str(email)
    
    # Prepare lead data
    lead_data = {
        "country": country,
        "shop_url": url,
        "email": email_value,
        "comparator": comparator,
        "notes": note_text,
        "status": "New_just_discovered"
    }
    
    try:
        # Log the API request details
        print(f"🔄 API REQUEST: POST {CSS_LEADS_ADD_LEAD_URL}")
        print(f"🔄 REQUEST DATA: {json.dumps(lead_data, indent=2)}")
        logger.info(f"API REQUEST: POST {CSS_LEADS_ADD_LEAD_URL}")
        logger.info(f"REQUEST DATA: {json.dumps(lead_data)}")
        
        # Send POST request to the API
        response = requests.post(
            CSS_LEADS_ADD_LEAD_URL,
            json=lead_data,
            timeout=10  # Add timeout to prevent hanging
        )
        
        # Log the full response
        try:
            response_json = response.json()
            response_str = json.dumps(response_json, indent=2)
            logger.info(f"API RESPONSE ({response.status_code}): {response_str}")
            print(f"🔄 API RESPONSE ({response.status_code}): {response_str}")
        except:
            logger.info(f"API RESPONSE ({response.status_code}, text): {response.text}")
            print(f"🔄 API RESPONSE ({response.status_code}, text): {response.text}")
        
        # Check response
        if response.status_code in [200, 201]:
            logger.info(f"Successfully sent lead to CSS Leads API: {url}")
            print(f"✅ Lead sent to CSS API: {url} from {comparator}")
            return True
        elif response.status_code == 409:
            # 409 Conflict - Lead already exists
            logger.info(f"Lead already exists in CSS Leads API: {url}")
            print(f"ℹ️ Lead already exists in CSS API: {url}")
            return True  # Consider this a success since the lead is in the system
        else:
            logger.error(f"Failed to send lead to CSS Leads API. Status code: {response.status_code}, Response: {response.text}")
            print(f"❌ Failed to send lead to CSS API: {url}. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending lead to CSS Leads API: {e}")
        print(f"❌ Error sending lead to CSS API: {url}. Error: {e}")
        return False
