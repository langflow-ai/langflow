from loguru import logger

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data
import requests
import json
import time
import re
from urllib.parse import urlparse


class BrightDataStructuredDataEnhancedComponent(Component):
    display_name: str = "Bright Data Structured Data Enhanced"
    description: str = "Extract structured data from websites with automatic detection or manual selection"
    name = "BrightDataStructuredDataEnhanced"
    
    documentation: str = "https://docs.brightdata.com/datasets"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="API Token",
            required=True,
            password=True,
            info="Your Bright Data API token",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL to extract structured data from",
            tool_mode=True,
        ),
        BoolInput(
            name="auto_detect",
            display_name="Auto Detect Website",
            value=True,
            info="Automatically detect website type and choose appropriate dataset",
        ),
        DropdownInput(
            name="manual_data_type",
            display_name="Manual Data Type",
            options=[
                "amazon_product",
                "amazon_product_reviews",
                "amazon_product_search",
                "walmart_product",
                "walmart_seller",
                "ebay_product",
                "homedepot_products",
                "zara_products",
                "etsy_products",
                "bestbuy_products",
                "linkedin_person_profile",
                "linkedin_company_profile",
                "linkedin_job_listings",
                "linkedin_posts",
                "linkedin_people_search",
                "crunchbase_company",
                "zoominfo_company_profile",
                "instagram_profiles",
                "instagram_posts",
                "instagram_reels",
                "instagram_comments",
                "facebook_posts",
                "facebook_marketplace_listings",
                "facebook_company_reviews",
                "facebook_events",
                "tiktok_profiles",
                "tiktok_posts",
                "tiktok_shop",
                "tiktok_comments",
                "google_maps_reviews",
                "google_shopping",
                "google_play_store",
                "apple_app_store",
                "reuter_news",
                "github_repository_file",
                "yahoo_finance_business",
                "x_posts",
                "zillow_properties_listing",
                "booking_hotel_listings",
                "youtube_profiles",
                "youtube_videos",
                "youtube_comments",
                "reddit_posts"
            ],
            value="amazon_product",
            info="Manually select data type (used when auto_detect is False)",
        ),
        IntInput(
            name="max_wait_time",
            display_name="Max Wait Time (seconds)",
            value=300,
            info="Maximum time to wait for data collection",
        ),
        MultilineInput(
            name="additional_params",
            display_name="Additional Parameters (JSON)",
            value="{}",
            info="Additional parameters for specific datasets (JSON format). Example: {\"pages_to_search\": \"2\", \"num_of_comments\": \"20\"}",
        ),
    ]

    outputs = [
        Output(display_name="Structured Data", name="data", method="extract_structured_data"),
    ]

    def _get_all_datasets(self) -> dict:
        """Get all available datasets with their configurations and detection patterns"""
        return {
            "amazon_product": {
                "dataset_id": "gd_l7q7dkf244hwjntr0",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/dp/", r"/gp/product/"]
            },
            "amazon_product_reviews": {
                "dataset_id": "gd_le8e811kzy4ggddlq",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/dp/.*#customerReviews", r"/product-reviews/"]
            },
            "amazon_product_search": {
                "dataset_id": "gd_lwdb4vjm1ehb499uxs",
                "inputs": ["keyword", "url", "pages_to_search"],
                "defaults": {"pages_to_search": "1"},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/s\?", r"field-keywords"]
            },
            "walmart_product": {
                "dataset_id": "gd_l95fol7l1ru6rlo116",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["walmart.com"],
                "url_patterns": [r"/ip/"]
            },
            "walmart_seller": {
                "dataset_id": "gd_m7ke48w81ocyu4hhz0",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["walmart.com"],
                "url_patterns": [r"/seller/"]
            },
            "ebay_product": {
                "dataset_id": "gd_ltr9mjt81n0zzdk1fb",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["ebay.com", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.it", "ebay.es", "ebay.ca", "ebay.com.au"],
                "url_patterns": [r"/itm/"]
            },
            "homedepot_products": {
                "dataset_id": "gd_lmusivh019i7g97q2n",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["homedepot.com"],
                "url_patterns": [r"/p/"]
            },
            "zara_products": {
                "dataset_id": "gd_lct4vafw1tgx27d4o0",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zara.com"],
                "url_patterns": [r"/product/"]
            },
            "etsy_products": {
                "dataset_id": "gd_ltppk0jdv1jqz25mz",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["etsy.com"],
                "url_patterns": [r"/listing/"]
            },
            "bestbuy_products": {
                "dataset_id": "gd_ltre1jqe1jfr7cccf",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["bestbuy.com"],
                "url_patterns": [r"/site/"]
            },
            "linkedin_person_profile": {
                "dataset_id": "gd_l1viktl72bvl7bjuj0",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/in/[^/]+/?$"]
            },
            "linkedin_company_profile": {
                "dataset_id": "gd_l1vikfnt1wgvvqz95w",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/company/"]
            },
            "linkedin_job_listings": {
                "dataset_id": "gd_lpfll7v5hcqtkxl6l",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/jobs/"]
            },
            "linkedin_posts": {
                "dataset_id": "gd_lyy3tktm25m4avu764",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/posts/", r"/feed/update/"]
            },
            "linkedin_people_search": {
                "dataset_id": "gd_m8d03he47z8nwb5xc",
                "inputs": ["url", "first_name", "last_name"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/search/results/people/"]
            },
            "crunchbase_company": {
                "dataset_id": "gd_l1vijqt9jfj7olije",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["crunchbase.com"],
                "url_patterns": [r"/organization/"]
            },
            "zoominfo_company_profile": {
                "dataset_id": "gd_m0ci4a4ivx3j5l6nx",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zoominfo.com"],
                "url_patterns": [r"/c/"]
            },
            "instagram_profiles": {
                "dataset_id": "gd_l1vikfch901nx3by4",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/[^/]+/?$"]
            },
            "instagram_posts": {
                "dataset_id": "gd_lk5ns7kz21pck8jpis",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/p/"]
            },
            "instagram_reels": {
                "dataset_id": "gd_lyclm20il4r5helnj",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/reel/"]
            },
            "instagram_comments": {
                "dataset_id": "gd_ltppn085pokosxh13",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/p/", r"/reel/"]
            },
            "facebook_posts": {
                "dataset_id": "gd_lyclm1571iy3mv57zw",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/posts/", r"/permalink/"]
            },
            "facebook_marketplace_listings": {
                "dataset_id": "gd_lvt9iwuh6fbcwmx1a",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/marketplace/"]
            },
            "facebook_company_reviews": {
                "dataset_id": "gd_m0dtqpiu1mbcyc2g86",
                "inputs": ["url", "num_of_reviews"],
                "defaults": {"num_of_reviews": "10"},
                "domains": ["facebook.com"],
                "url_patterns": [r"/[^/]+/?$"]
            },
            "facebook_events": {
                "dataset_id": "gd_m14sd0to1jz48ppm51",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/events/"]
            },
            "tiktok_profiles": {
                "dataset_id": "gd_l1villgoiiidt09ci",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/@[^/]+/?$"]
            },
            "tiktok_posts": {
                "dataset_id": "gd_lu702nij2f790tmv9h",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/video/"]
            },
            "tiktok_shop": {
                "dataset_id": "gd_m45m1u911dsa4274pi",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/shop/"]
            },
            "tiktok_comments": {
                "dataset_id": "gd_lkf2st302ap89utw5k",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/video/"]
            },
            "google_maps_reviews": {
                "dataset_id": "gd_luzfs1dn2oa0teb81",
                "inputs": ["url", "days_limit"],
                "defaults": {"days_limit": "3"},
                "domains": ["google.com", "maps.google.com"],
                "url_patterns": [r"/maps/", r"/@"]
            },
            "google_shopping": {
                "dataset_id": "gd_ltppk50q18kdw67omz",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["google.com"],
                "url_patterns": [r"/shopping/"]
            },
            "google_play_store": {
                "dataset_id": "gd_lsk382l8xei8vzm4u",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["play.google.com"],
                "url_patterns": [r"/store/apps/"]
            },
            "apple_app_store": {
                "dataset_id": "gd_lsk9ki3u2iishmwrui",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["apps.apple.com"],
                "url_patterns": [r"/app/"]
            },
            "reuter_news": {
                "dataset_id": "gd_lyptx9h74wtlvpnfu",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["reuters.com"],
                "url_patterns": [r"/"]
            },
            "github_repository_file": {
                "dataset_id": "gd_lyrexgxc24b3d4imjt",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["github.com"],
                "url_patterns": [r"/blob/", r"/tree/"]
            },
            "yahoo_finance_business": {
                "dataset_id": "gd_lmrpz3vxmz972ghd7",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["finance.yahoo.com"],
                "url_patterns": [r"/quote/"]
            },
            "x_posts": {
                "dataset_id": "gd_lwxkxvnf1cynvib9co",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["x.com", "twitter.com"],
                "url_patterns": [r"/status/"]
            },
            "zillow_properties_listing": {
                "dataset_id": "gd_lfqkr8wm13ixtbd8f5",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zillow.com"],
                "url_patterns": [r"/homedetails/"]
            },
            "booking_hotel_listings": {
                "dataset_id": "gd_m5mbdl081229ln6t4a",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["booking.com"],
                "url_patterns": [r"/hotel/"]
            },
            "youtube_profiles": {
                "dataset_id": "gd_lk538t2k2p1k3oos71",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["youtube.com"],
                "url_patterns": [r"/channel/", r"/c/", r"/@[^/]+/?$"]
            },
            "youtube_videos": {
                "dataset_id": "gd_m5mbdl081229ln6t4a",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["youtube.com"],
                "url_patterns": [r"/watch\?v="]
            },
            "youtube_comments": {
                "dataset_id": "gd_lk9q0ew71spt1mxywf",
                "inputs": ["url", "num_of_comments"],
                "defaults": {"num_of_comments": "10"},
                "domains": ["youtube.com"],
                "url_patterns": [r"/watch\?v="]
            },
            "reddit_posts": {
                "dataset_id": "gd_lvz8ah06191smkebj4",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["reddit.com"],
                "url_patterns": [r"/r/", r"/comments/"]
            }
        }

    def _detect_website_type(self, url: str) -> tuple:
        """Automatically detect website type from URL. Returns (dataset_name, confidence_score)"""
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc.replace('www.', '').replace('m.', '')
        path = parsed_url.path
        query = parsed_url.query
        
        datasets = self._get_all_datasets()
        
        # Score each dataset based on domain and URL pattern matches
        scores = {}
        
        for dataset_name, config in datasets.items():
            score = 0
            
            # Check domain match (high weight)
            for dataset_domain in config.get("domains", []):
                if dataset_domain in domain:
                    score += 100
                    break
            
            # Check URL pattern match (medium weight)
            for pattern in config.get("url_patterns", []):
                if re.search(pattern, path) or re.search(pattern, query):
                    score += 50
                    break
            
            # Special logic for specific cases
            if score > 0:
                # LinkedIn specific detection
                if "linkedin.com" in domain:
                    if "/in/" in path and not ("/company/" in path or "/posts/" in path or "/jobs/" in path):
                        if dataset_name == "linkedin_person_profile":
                            score += 25
                    elif "/company/" in path:
                        if dataset_name == "linkedin_company_profile":
                            score += 25
                    elif "/jobs/" in path:
                        if dataset_name == "linkedin_job_listings":
                            score += 25
                    elif "/posts/" in path or "/feed/update/" in path:
                        if dataset_name == "linkedin_posts":
                            score += 25
                
                # Instagram specific detection
                elif "instagram.com" in domain:
                    if "/p/" in path:
                        if dataset_name == "instagram_posts":
                            score += 25
                    elif "/reel/" in path:
                        if dataset_name == "instagram_reels":
                            score += 25
                    elif re.search(r"/[^/]+/?$", path) and not ("/p/" in path or "/reel/" in path):
                        if dataset_name == "instagram_profiles":
                            score += 25
                
                # Amazon specific detection
                elif any(amazon_domain in domain for amazon_domain in ["amazon.com", "amazon.co.uk", "amazon.de"]):
                    if "/dp/" in path or "/gp/product/" in path:
                        if "#customerReviews" in url or "/product-reviews/" in path:
                            if dataset_name == "amazon_product_reviews":
                                score += 25
                        else:
                            if dataset_name == "amazon_product":
                                score += 25
                    elif "/s?" in path or "field-keywords" in query:
                        if dataset_name == "amazon_product_search":
                            score += 25
                
                # YouTube specific detection  
                elif "youtube.com" in domain:
                    if "/watch?v=" in path or "/watch?v=" in query:
                        if dataset_name == "youtube_videos":
                            score += 25
                    elif "/channel/" in path or "/c/" in path or re.search(r"/@[^/]+/?$", path):
                        if dataset_name == "youtube_profiles":
                            score += 25
            
            if score > 0:
                scores[dataset_name] = score
        
        if scores:
            best_match = max(scores, key=scores.get)
            confidence = scores[best_match]
            logger.info(f"Auto-detection: {best_match} (confidence: {confidence})")
            return best_match, confidence
        
        logger.warning(f"Could not auto-detect dataset for URL: {url}")
        return None, 0

    def _prepare_dataset_payload(self, data_type: str, url: str, additional_params: dict) -> dict:
        """Prepare payload for dataset based on its input requirements"""
        datasets = self._get_all_datasets()
        config = datasets.get(data_type, {})
        
        # Start with URL
        payload = {"url": url}
        
        # Add default values for this dataset
        defaults = config.get("defaults", {})
        payload.update(defaults)
        
        # Override with user-provided additional parameters
        payload.update(additional_params)
        
        return payload

    def extract_structured_data(self) -> Data:
        """Extract structured data using Bright Data's datasets API"""
        # Validate inputs
        if not self.api_token:
            msg = "API token is required"
            raise ValueError(msg)

        if not self.url:
            msg = "URL is required"
            raise ValueError(msg)

        try:
            # Parse additional parameters
            try:
                additional_params = json.loads(self.additional_params) if self.additional_params.strip() else {}
                if not isinstance(additional_params, dict):
                    additional_params = {}
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in additional_params: {str(e)}, using empty dict")
                additional_params = {}
            
            # Determine which dataset to use
            if self.auto_detect:
                detected_type, confidence = self._detect_website_type(self.url)
                if not detected_type:
                    parsed_url = urlparse(self.url)
                    error_msg = f"Could not automatically detect website type for domain: {parsed_url.netloc}. Please disable auto-detect and manually select a data type."
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                data_type = detected_type
                logger.info(f"Auto-detected data type: {data_type} (confidence: {confidence})")
            else:
                data_type = self.manual_data_type
                logger.info(f"Using manual data type: {data_type}")
            
            # Get dataset configuration
            datasets = self._get_all_datasets()
            dataset_config = datasets.get(data_type)
            
            if not dataset_config:
                error_msg = f"Unknown data type: {data_type}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            dataset_id = dataset_config["dataset_id"]
            
            headers = {
                'authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
            }
            
            # Prepare payload
            payload = self._prepare_dataset_payload(data_type, self.url, additional_params)
            trigger_payload = [payload]
            
            logger.info(f"Triggering data collection for dataset {dataset_id} with payload: {payload}")
            
            # Trigger data collection
            trigger_response = requests.post(
                'https://api.brightdata.com/datasets/v3/trigger',
                params={'dataset_id': dataset_id, 'include_errors': True},
                json=trigger_payload,
                headers=headers,
                timeout=30
            )
            
            if trigger_response.status_code != 200:
                error_msg = f"Failed to trigger collection: HTTP {trigger_response.status_code} - {trigger_response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Parse trigger response
            try:
                trigger_data = trigger_response.json()
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse trigger response as JSON: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Handle response format - could be dict or list
            snapshot_id = None
            
            if isinstance(trigger_data, dict):
                snapshot_id = trigger_data.get('snapshot_id')
            elif isinstance(trigger_data, list) and len(trigger_data) > 0:
                first_item = trigger_data[0]
                if isinstance(first_item, dict):
                    snapshot_id = first_item.get('snapshot_id')
                else:
                    error_msg = f"Expected dict in trigger response list, got {type(first_item)}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            else:
                error_msg = f"Unexpected trigger response format: {type(trigger_data)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not snapshot_id:
                error_msg = "No snapshot ID returned from trigger request"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"Got snapshot ID: {snapshot_id}, starting to poll for results")
            
            # Poll for results
            start_time = time.time()
            attempts = 0
            
            while time.time() - start_time < self.max_wait_time:
                attempts += 1
                
                try:
                    snapshot_response = requests.get(
                        f'https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}',
                        params={'format': 'json'},
                        headers=headers,
                        timeout=30
                    )
                    
                    if snapshot_response.status_code == 200:
                        try:
                            snapshot_data = snapshot_response.json()
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse snapshot response as JSON: {str(e)}")
                            time.sleep(5)
                            continue
                        
                        # Handle snapshot response format - could also be dict or list
                        status = None
                        final_data = None
                        
                        if isinstance(snapshot_data, dict):
                            status = snapshot_data.get('status', 'unknown')
                            final_data = snapshot_data
                        elif isinstance(snapshot_data, list) and len(snapshot_data) > 0:
                            # If it's a list, the status might be in the first item or it might be the actual data
                            first_item = snapshot_data[0]
                            if isinstance(first_item, dict) and 'status' in first_item:
                                status = first_item.get('status', 'unknown')
                                final_data = snapshot_data
                            else:
                                # If no status field, assume the data is ready
                                status = 'completed'
                                final_data = snapshot_data
                        else:
                            logger.warning(f"Unexpected snapshot response format: {type(snapshot_data)}")
                            time.sleep(5)
                            continue
                        
                        # Check if data collection is complete
                        if status and status != 'running':
                            logger.info(f"Data collection completed with status: {status}")
                            return Data(
                                data={
                                    "url": self.url,
                                    "data_type": data_type,
                                    "dataset_id": dataset_id,
                                    "snapshot_id": snapshot_id,
                                    "status": "success",
                                    "attempts": attempts,
                                    "auto_detected": self.auto_detect,
                                    "detection_confidence": confidence if self.auto_detect else None,
                                    "payload_used": payload,
                                    "structured_data": final_data
                                }
                            )
                        else:
                            logger.info(f"Still running (attempt {attempts}), waiting...")
                    else:
                        logger.warning(f"Snapshot request failed: HTTP {snapshot_response.status_code}")
                        
                except requests.RequestException as e:
                    logger.warning(f"Polling attempt {attempts} failed: {str(e)}")
                
                # Wait before next poll
                time.sleep(5)
            
            # Timeout reached
            error_msg = f"Timeout after {self.max_wait_time} seconds waiting for data (attempted {attempts} times)"
            logger.error(error_msg)
            raise ValueError(error_msg)
                
        except ValueError:
            # Re-raise ValueError as-is (these are our custom error messages)
            raise
        except Exception as e:
            error_msg = f"Unexpected error during data extraction: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e