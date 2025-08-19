# facebook_business_bot/services/facebook_creator.py
import requests
import logging
import json
import time
import random
import re
import asyncio # Import asyncio for async operations

from services.tempmail_api import tempmail_api
from database.db_manager import db_manager # Import db_manager
from utils.helpers import (
    generate_random_name, generate_random_email, generate_business_name,
    generate_random_user_agent, extract_token_from_response,
    parse_cookies, get_user_id_from_cookies
)

logger = logging.getLogger(__name__)

class FacebookCreator:
    def __init__(self):
        pass

    async def setup_business_review(self, cookies, token_value, user_id, biz_id, admin_email):
        """Complete business setup with review card mutation."""
        logger.info(f"📋 Setting up business review for Business ID: {biz_id}")
        
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://business.facebook.com',
            'priority': 'u=1, i',
            'referer': 'https://business.facebook.com/billing_hub/payment_settings/?asset_id=&payment_account_id=',
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.184", "Google Chrome";v="138.0.7204.184"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-asbd-id': '359341',
            'x-bh-flowsessionid': 'upl_wizard_1755490133794_62e6e455-e443-49db-aeba-58f23a27ec01',
            'x-fb-friendly-name': 'BizKitBusinessSetupReviewCardMutation',
            'x-fb-lsd': token_value,
            'x-fb-upl-sessionid': 'upl_1755490133794_11c3faff-8830-427d-b820-0c4366afac9d',
        }

        params = {
            '_callFlowletID': '0',
            '_triggerFlowletID': '6821',
            'qpl_active_e2e_trace_ids': '',
        }

        data = {
            'av': user_id,
            '__aaid': '0',
            '__user': user_id,
            '__a': '1',
            '__req': '1c',
            '__hs': '20318.BP:DEFAULT.2.0...0',
            'dpr': '1',
            '__ccg': 'EXCELLENT',
            '__rev': '1026002495',
            '__s': 'si7vjs:iccgau:4k38c3',
            '__hsi': '7539772710483233608',
            '__dyn': '7xeUmxa2C5rgydwCwRyU8EKmhe2Om2q1DxiFGxK7oG484S4UKewSAAzpoixW4E726US2Sfxq4U5i4824yoyaxG4o4B0l898885G0Eo9FE4WqbwLghwLyaxBa2dmm11K6U8o2lxep122y5oeEjx63K2y1py-0DU2qwgEhxWbwQwnHxC0Bo9k2B2V8cE98451KfwXxq1-orx2ewyx6i2GU8U-U98C2i48nwCAzEowwwTxu1cwh8S1qxa3O6UW4UnwhFA0FUkx22W11wCz84e2K7EOicwVyES2e0UFU6K19xq1owqp8aE4KeyE9Eco9U4S7ErwMxN0lF9UcE3xwtU5K2G0BE88twba3i15xBxa2u1aw',
            '__hsdp': '85v92crRg8pkFxqe5ybjyk8jdAQO5WQm2G3qm2a9StAK2KK1txC_xAC4y4KIqilJjCZKcCy8GE49BGze5ahk1exugG8ukidxe2504Fg2EadzE9UWFFEgwNqzpEb4EgG-ezFjzczF2CQA4l1gUjxK5k2d8kieFD18EYE9FE1uU5S1Gwto5q0lGl6e0dLw0X1Kq9ym2aiQezUpAximbCjw0xfw',
            '__hblp': '0Rwbu3G6U4W1gw48w54w75xGE1oA0OA2q7pUdUCbwoobU88aWwjUdE6i1Gw8y1ZwVK0FE9U3oG1tw7jG1iw8uE3PwkU2kzonwYwrE6C1ZwiUeo1vo6i17xO4Uiy9ES6awno1kElwlEao3BwtEG3-7EhwHwmoaE9bwIAgK8x2l4xii9wwxq5GwwyEO1OyawhVE88lg4Cex-1dwSw9C3G2mi0ha0DE98iBx23a11w_xJa2W9BwBCxm2Kq4EswMyomwwwkEgwxg9Ulxm5qGqqUy2it0iUaoyazE4u2G6E4-az85e78cECayEjwrFEq_82aRwXKUSmWyGK7FWhd5gC9zdfU8rG4KE7-3zwGwfe2q68cA5A58b8gy837wxwmo2WwFwnFUc-m2O5o8oS9xWi2OnwIDwko8U8EW1wxV1C229xG7p8owNxydg6x0DwNiw8u3uui',
            'fb_dtsg': token_value,
            'jazoest': '25376',
            'lsd': token_value,
            '__spin_r': '1026002495',
            '__spin_b': 'trunk',
            '__spin_t': '1755490133',
            '__jssesw': '1',
            'qpl_active_flow_ids': '1001927540,558500776',
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'BizKitBusinessSetupReviewCardMutation',
            'variables': f'{{"businessId":"{biz_id}","entryPoint":"BIZWEB_BIZ_SETUP_REVIEW_CARD","inviteUsers":[{{"email":"{admin_email}","roles":["ADMIN"]}}],"personalPageIdsToBeClaimed":[],"directPageUsers":[],"flowType":"BUSINESS_CREATION_IN_FBS"}}',
            'server_timestamps': 'true',
            'doc_id': '9845682502146236',
            'fb_api_analytics_tags': '["qpl_active_flow_ids=1001927540,558500776"]',
        }

        try:
            response = requests.post(
                'https://business.facebook.com/api/graphql/', 
                params=params, 
                cookies=cookies, 
                headers=headers, 
                data=data,
                timeout=30
            )
            response.raise_for_status()
            
            response_text = response.text
            if response_text.startswith('for (;;);'):
                response_text = response_text[9:]
            
            response_json = json.loads(response_text)
            
            if 'errors' in response_json:
                error_messages = [error.get('message', 'Unknown error') for error in response_json['errors']]
                logger.error(f"❌ Failed to complete business setup: {'; '.join(error_messages)}")
                return False
            elif 'error' in response_json:
                error_code = response_json.get('error', 'Unknown')
                error_desc = response_json.get('errorDescription', 'Unknown error')
                logger.error(f"❌ Setup Error {error_code}: {error_desc}")
                return False
            elif 'data' in response_json:
                logger.info("✅ Business setup completed successfully!")
                return True
            else:
                logger.warning(f"⚠️ Unexpected setup response format: {response_json}")
                return False
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error in setup response: {e}. Response: {response.text[:500]}...")
            return False
        except requests.RequestException as e:
            logger.error(f"❌ Network error during setup: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ General error in setup: {e}")
            return False

    async def create_facebook_business(self, cookies_dict: dict, telegram_user_id: int, tempmail_api_key: str):
        """
        Attempts to create a Facebook Business Manager account.
        Returns (success_status, biz_id, invitation_link, error_message)
        success_status: True for success, False for general failure, "LIMIT_REACHED" for limit.
        """
        logger.info("=== Starting Facebook Business Creation Process ===")
        
        if not cookies_dict:
            logger.error("❌ No cookies provided to the function!")
            return False, None, None, "No cookies provided."
        
        if not tempmail_api_key:
            logger.error("❌ No TempMail API Key provided for business creation!")
            return False, None, None, "No TempMail API Key provided."

        cookies = cookies_dict
        user_id = get_user_id_from_cookies(cookies)
        
        # Use db_manager to get or create the daily temp email
        try:
            admin_email = await db_manager.get_or_create_daily_temp_email(telegram_user_id, tempmail_api_key)
        except Exception as e:
            logger.error(f"❌ Failed to get/create daily temp email for user {telegram_user_id}: {e}")
            return False, None, None, f"Failed to get/create daily temp email: {e}"
        
        if not admin_email:
            return False, None, None, "Failed to get/create temporary email."
        
        first_name, last_name = generate_random_name()
        email = generate_random_email(first_name, last_name)
        business_name = generate_business_name()
        user_agent = generate_random_user_agent()
        
        logger.info(f"\n=== Generated Data ===")
        logger.info(f"Business Name: {business_name}")
        logger.info(f"First Name: {first_name}")
        logger.info(f"Last Name: {last_name}")
        logger.info(f"Email: {email}")
        logger.info(f"Admin Email (TempMail): {admin_email}")
        logger.info(f"User ID: {user_id}")
        logger.info("=" * 30)
        
        headers_initial = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': user_agent,
        }

        logger.info("🔍 Getting token...")
        
        try:
            response = requests.get(
                'https://business.facebook.com/overview',
                cookies=cookies,
                headers=headers_initial,
                stream=True,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            
            logger.info(f"Initial request status: {response.status_code}")

            token_value = extract_token_from_response(response)
            
            if not token_value:
                return False, None, None, "Token not found - please check cookies validity."
                
            logger.info(f"✅ Token obtained successfully: {token_value[:20]}...")
            await asyncio.sleep(2) # Use asyncio.sleep

            headers_create = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://business.facebook.com',
                'referer': 'https://business.facebook.com/overview',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent,
                'x-asbd-id': str(random.randint(359340, 359350)),
                'x-fb-friendly-name': 'useBusinessCreationMutationMutation',
                'x-fb-lsd': token_value,
            }

            variables_data = {
                "input": {
                    "client_mutation_id": str(random.randint(1, 999)),
                    "actor_id": user_id,
                    "business_name": business_name,
                    "user_first_name": first_name,
                    "user_last_name": last_name,
                    "user_email": email,
                    "creation_source": "BM_HOME_BUSINESS_CREATION_IN_SCOPE_SELECTOR",
                    "entry_point": "UNIFIED_GLOBAL_SCOPE_SELECTOR"
                }
            }

            data_create = {
                'av': user_id,
                '__user': user_id,
                '__a': '1',
                '__req': str(random.randint(10, 30)),
                '__hs': f'{random.randint(20000, 25000)}.BP:DEFAULT.2.0...0',
                'dpr': '1',
                '__ccg': 'MODERATE',
                '__rev': str(random.randint(1026001750, 1026001760)),
                '__s': f'{random.choice(["3arcua", "4brcub", "5csdvc"])}:{random.choice(["iccgau", "jddgbv", "kddgbv"])}:{random.choice(["myl46k", "nzm47l", "ozm48m"])}',
                '__hsi': str(random.randint(7539741099426225680, 7539741099426225690)),
                '__comet_req': '15',
                'fb_dtsg': token_value,
                'jazoest': str(random.randint(25540, 25550)),
                'lsd': token_value,
                '__spin_r': str(random.randint(1026001750, 1026001760)),
                '__spin_b': 'trunk',
                '__spin_t': str(int(time.time())),
                '__jssesw': '1',
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'useBusinessCreationMutationMutation',
                'variables': json.dumps(variables_data, separators=(',', ':')),
                'server_timestamps': 'true',
                'doc_id': '10024830640911292',
            }

            logger.info("🏢 Creating business account...")
            response_create = requests.post(
                'https://business.facebook.com/api/graphql/', 
                cookies=cookies, 
                headers=headers_create, 
                data=data_create,
                timeout=30
            )
            response_create.raise_for_status()
            
            response_text = response_create.text
            if response_text.startswith('for (;;);'):
                response_text = response_text[9:]
            
            response_json = json.loads(response_text)
            
            if 'errors' in response_json:
                for error in response_json['errors']:
                    error_msg = error.get('message', '')
                    if 'field_exception' in error_msg or 'حد عدد الأنشطة التجارية' in error.get('description', ''):
                        logger.warning("🛑 Facebook business creation limit reached!")
                        return "LIMIT_REACHED", None, None, "Facebook business creation limit reached."
                
                error_messages = [error.get('message', 'Unknown error') for error in response_json['errors']]
                logger.error(f"❌ Failed to create business account: {'; '.join(error_messages)}")
                return False, None, None, f"Failed to create business account: {'; '.join(error_messages)}"
                
            elif 'error' in response_json:
                error_code = response_json.get('error', 'Unknown')
                error_desc = response_json.get('errorDescription', 'Unknown error')
                logger.error(f"❌ Error {error_code}: {error_desc}")
                return False, None, None, f"Facebook API Error {error_code}: {error_desc}"
                
            elif 'data' in response_json:
                logger.info("✅ Business account created successfully!")
                
                try:
                    biz_id = response_json['data']['bizkit_create_business']['id']
                    logger.info(f"✅ Business ID: {biz_id}")
                except KeyError:
                    logger.error("⚠️ Could not extract Business ID from response.")
                    return False, None, None, "Could not extract Business ID from response."
                    
                logger.info("\n📧 Setting up business with TempMail admin...")
                await asyncio.sleep(3) # Use asyncio.sleep
                
                setup_success = await self.setup_business_review(cookies, token_value, user_id, biz_id, admin_email)
                
                if setup_success:
                    logger.info("\n📨 Waiting for invitation email...")
                    # Pass tempmail_api_key to wait_for_invitation_email
                    invitation_link = await tempmail_api.wait_for_invitation_email(admin_email, tempmail_api_key)
                    
                    if invitation_link:
                        return True, biz_id, invitation_link, None
                    else:
                        logger.warning("⚠️ Business created but no invitation link received.")
                        return False, biz_id, None, "Business created but no invitation link received (TempMail issue or delay)."
                else:
                    logger.warning("⚠️ Business created but setup failed.")
                    return False, biz_id, None, "Business created but setup failed."
            else:
                logger.warning("⚠️ Unexpected response format during business creation.")
                return False, None, None, "Unexpected response format during business creation."
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error during business creation: {e}. Response: {response_create.text[:500]}...")
            return False, None, None, f"JSON decode error: {e}"
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during business creation: {e}")
            return False, None, None, f"Network error: {e}"
        except Exception as e:
            logger.error(f"❌ General error during business creation: {e}")
            return False, None, None, f"General error: {e}"

# Initialize the FacebookCreator class
facebook_creator = FacebookCreator()
