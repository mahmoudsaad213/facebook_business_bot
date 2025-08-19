# facebook_business_bot/services/tempmail_api.py
import requests
import logging

logger = logging.getLogger(__name__)

def create_temp_email(api_key):
    """Create a new temporary email address using TempMail API."""
    try:
        response = requests.post(
            f"https://api.tempmail.co/v1/addresses",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        email_data = response.json()
        return email_data['data']['email']
    except Exception as e:
        logger.error(f"Error creating temporary email: {e}")
        return None
