import requests
import pandas as pd

from logger import setup_logging

logger = setup_logging()

# Replace these values with your actual login credentials and web server URL
username = 'test'
password = 'test'
url = 'http://176.102.66.162:5000/upload'


def send_csv_to_server(data: pd.DataFrame):

    # Convert DataFrame to CSV string
    csv_string = data.to_csv(index=False)

    # Login to the web server
    login_data = {
        'Username': username,
        'Password': password
    }

    login_response = None  # Initialize to None
    try:
        login_response = requests.post('http://176.102.66.162:5000/login', data=login_data)
    except Exception as e:
        print(f"Error while logging up to upload page")
        logger.error(f"Error while logging up to upload page {e}")
        return False

    # Check if login was successful
    if login_response and login_response.status_code == 200:
        # Prepare the files to be sent
        files = {'file': ('test.csv', csv_string)}

        # Send the file to the server
        upload_response = requests.post(url, files=files)

        # Check the response from the server
        if upload_response.status_code == 200:
            logger.info("File uploaded successfully.")
            return True
        else:
            print(f"Failed to upload file. Status code: {upload_response.status_code}")
            logger.error(f"Failed to upload file. Status code: {upload_response.status_code}")
            return False
    else:
        status_code = login_response.status_code if login_response else "No response"
        print(f"Login failed. Status code: {status_code}")
        logger.error(f"Error while logging up to upload page. Status code: {status_code}")
        return False
