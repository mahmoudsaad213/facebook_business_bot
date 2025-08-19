# facebook_business_bot/utils/helpers.py
def parse_cookies(cookies_input):
    """Convert cookies from text to dictionary."""
    cookies = {}
    for part in cookies_input.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies
