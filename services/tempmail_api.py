# facebook_business_bot/services/tempmail_api.py
import requests
import logging
import re
import time

from config import TEMPMAIL_BASE_URL, BUSINESS_CREATION_TIMEOUT

logger = logging.getLogger(__name__)

class TempMailAPI:
    def __init__(self):
        pass # No global API key needed here, it's passed per method

    def _get_headers(self, api_key: str):
        """Helper to get headers with the provided API key."""
        if not api_key:
            raise ValueError("TempMail API Key is required.")
        return {"Authorization": f"Bearer {api_key}"}

    def create_temp_email(self, api_key: str):
        """Create a new temporary email address."""
        try:
            headers = self._get_headers(api_key)
            response = requests.post(f"{TEMPMAIL_BASE_URL}/addresses", headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            email = data["data"]["email"]
            logger.info(f"📧 Created temporary email: {email}")
            return email
        except requests.RequestException as e:
            logger.error(f"❌ Error creating email with API Key {api_key[:5]}...: {e}")
            return None
        except ValueError as e:
            logger.error(f"❌ Configuration error for TempMail API: {e}")
            return None

    def get_emails(self, email_address: str, api_key: str):
        """Retrieve emails for the given temporary email address."""
        try:
            headers = self._get_headers(api_key)
            response = requests.get(f"{TEMPMAIL_BASE_URL}/addresses/{email_address}/emails", headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data["data"]
        except requests.RequestException as e:
            logger.error(f"❌ Error fetching emails for {email_address} with API Key {api_key[:5]}...: {e}")
            return []
        except ValueError as e:
            logger.error(f"❌ Configuration error for TempMail API: {e}")
            return []

    def read_email(self, email_uuid: str, api_key: str):
        """Read the content of a specific email by its UUID."""
        try:
            headers = self._get_headers(api_key)
            response = requests.get(f"{TEMPMAIL_BASE_URL}/emails/{email_uuid}", headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data["data"]
        except requests.RequestException as e:
            logger.error(f"❌ Error reading email {email_uuid} with API Key {api_key[:5]}...: {e}")
            return None
        except ValueError as e:
            logger.error(f"❌ Configuration error for TempMail API: {e}")
            return None

    def extract_invitation_link(self, email_body: str):
        """Extract the invitation link starting with 'https://business.facebook.com/invitation/?token='."""
        # The pattern should correctly capture the URL without extra backslashes.
        # The issue with backslashes was likely due to Markdown escaping, not the regex itself.
        pattern = r'https://business\.facebook\.com/invitation/\?token=[^"\s]+'
        match = re.search(pattern, email_body)
        if match:
            return match.group(0)
        return None

    async def wait_for_invitation_email(self, email_address: str, api_key: str, timeout=BUSINESS_CREATION_TIMEOUT):
        """Wait for invitation email and extract the link."""
        logger.info(f"🔄 Waiting for invitation email on: {email_address}")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            emails = self.get_emails(email_address, api_key)
            if emails:
                for email_data in emails:
                    # Check for 'from' and 'subject' keys before accessing them
                    if 'from' in email_data and 'subject' in email_data:
                        if "facebook" in email_data['from'].lower() or "invitation" in email_data['subject'].lower():
                            logger.info(f"📨 Found invitation email from: {email_data['from']}")
                            
                            email_content = self.read_email(email_data['uuid'], api_key)
                            if email_content and 'body' in email_content:
                                invitation_link = self.extract_invitation_link(email_content['body'])
                                if invitation_link:
                                    logger.info(f"🔗 Invitation link extracted!")
                                    return invitation_link
                            else:
                                logger.warning(f"⚠️ Could not read full email content or body for UUID: {email_data.get('uuid')}")
            
            await asyncio.sleep(10)  # Use asyncio.sleep for non-blocking wait
        
        logger.warning("⏰ Timeout waiting for invitation email")
        return None

# Initialize the TempMailAPI class
tempmail_api = TempMailAPI()
