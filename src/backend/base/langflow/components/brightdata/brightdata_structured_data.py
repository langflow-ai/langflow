# brightdata_structured_data.py
from loguru import logger
from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data
import requests
import json
import time
import re
from urllib.parse import urlparse
from typing import Dict, Tuple, Optional, Any, List, Union


class BrightDataStructuredDataEnhancedComponent(Component):
    display_name: str = "Bright Data Structured Data"
    description: str = "Extract structured data from 40+ real-time specialized datasets using AI-powered auto detection"
    name = "BrightDataStructuredData"
    icon = "BrightData"
    
    documentation: str = "https://docs.brightdata.com/datasets"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="🔑 API Token",
            required=True,
            password=True,
            info="Your Bright Data API token from account settings",
            placeholder="Enter your Bright Data API token...",
        ),
        MessageTextInput(
            name="url_input",
            display_name="🔍 URL Input",
            required=True,
            info="The webpage URL to extract structured data from - can be connected from another component or entered manually",
            tool_mode=True,
            placeholder="https://example.com/page",
        ),
        BoolInput(
            name="auto_detect",
            display_name="🤖 Auto-Detect Dataset",
            value=True,
            info="Automatically detect the best dataset using AI-powered URL analysis (max confidence: 175 points)",
        ),
        DropdownInput(
            name="manual_data_type",
            display_name="📊 Manual Dataset Selection",
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
            info="Choose a specific dataset when auto-detect is disabled",
        ),
        IntInput(
            name="max_wait_time",
            display_name="⏱️ Timeout (seconds)",
            value=300,
            info="Maximum time to wait for data collection (30-600 seconds)",
            advanced=True,
        ),
        MultilineInput(
            name="additional_params",
            display_name="⚙️ Additional Parameters",
            value="{}",
            info="Dataset-specific parameters in JSON format\nExamples:\n• {\"pages_to_search\": \"3\"}\n• {\"num_of_comments\": \"20\", \"days_limit\": \"7\"}",
            placeholder='{"pages_to_search": "2", "num_of_comments": "10"}',
            advanced=True,
        ),
        BoolInput(
            name="show_detection_details",
            display_name="🔍 Show Detection Details",
            value=False,
            info="Include detailed auto-detection scoring and confidence analysis in output",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Structured Data", name="data", method="extract_structured_data"),
        Output(display_name="Detection Info", name="detection_info", method="get_detection_info"),
    ]

    def _get_all_datasets(self) -> Dict[str, Dict[str, Any]]:
        """Get all available datasets with enhanced configurations and detection patterns"""
        return {
            "amazon_product": {
                "dataset_id": "gd_l7q7dkf244hwjntr0",
                "display_name": "Amazon Product",
                "category": "E-commerce",
                "description": "Product details, pricing, ratings, and specifications",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/dp/", r"/gp/product/"],
                "confidence_weight": 30,
                "keywords": ["product", "dp"]
            },
            "amazon_product_reviews": {
                "dataset_id": "gd_le8e811kzy4ggddlq",
                "display_name": "Amazon Product Reviews",
                "category": "E-commerce",
                "description": "Customer reviews, ratings, and feedback",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/dp/.*#customerReviews", r"/product-reviews/"],
                "confidence_weight": 25,
                "keywords": ["reviews", "customerReviews"]
            },
            "amazon_product_search": {
                "dataset_id": "gd_lwdb4vjm1ehb499uxs",
                "display_name": "Amazon Product Search",
                "category": "E-commerce",
                "description": "Search results and product listings",
                "inputs": ["keyword", "url", "pages_to_search"],
                "defaults": {"pages_to_search": "1"},
                "domains": ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.ca", "amazon.com.au", "amazon.co.jp"],
                "url_patterns": [r"/s\?", r"field-keywords"],
                "confidence_weight": 20,
                "keywords": ["search", "field-keywords"]
            },
            "walmart_product": {
                "dataset_id": "gd_l95fol7l1ru6rlo116",
                "display_name": "Walmart Product",
                "category": "E-commerce",
                "description": "Walmart product information and pricing",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["walmart.com"],
                "url_patterns": [r"/ip/"],
                "confidence_weight": 30,
                "keywords": ["product", "ip"]
            },
            "walmart_seller": {
                "dataset_id": "gd_m7ke48w81ocyu4hhz0",
                "display_name": "Walmart Seller",
                "category": "E-commerce",
                "description": "Walmart seller profiles and information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["walmart.com"],
                "url_patterns": [r"/seller/"],
                "confidence_weight": 25,
                "keywords": ["seller"]
            },
            "ebay_product": {
                "dataset_id": "gd_ltr9mjt81n0zzdk1fb",
                "display_name": "eBay Product",
                "category": "E-commerce",
                "description": "eBay product listings and auction data",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["ebay.com", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.it", "ebay.es", "ebay.ca", "ebay.com.au"],
                "url_patterns": [r"/itm/"],
                "confidence_weight": 30,
                "keywords": ["itm"]
            },
            "homedepot_products": {
                "dataset_id": "gd_lmusivh019i7g97q2n",
                "display_name": "Home Depot Products",
                "category": "E-commerce",
                "description": "Home improvement and hardware products",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["homedepot.com"],
                "url_patterns": [r"/p/"],
                "confidence_weight": 30,
                "keywords": ["product"]
            },
            "zara_products": {
                "dataset_id": "gd_lct4vafw1tgx27d4o0",
                "display_name": "Zara Products",
                "category": "E-commerce",
                "description": "Fashion and clothing products from Zara",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zara.com"],
                "url_patterns": [r"/product/"],
                "confidence_weight": 30,
                "keywords": ["product"]
            },
            "etsy_products": {
                "dataset_id": "gd_ltppk0jdv1jqz25mz",
                "display_name": "Etsy Products",
                "category": "E-commerce",
                "description": "Handmade and vintage items from Etsy",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["etsy.com"],
                "url_patterns": [r"/listing/"],
                "confidence_weight": 30,
                "keywords": ["listing"]
            },
            "bestbuy_products": {
                "dataset_id": "gd_ltre1jqe1jfr7cccf",
                "display_name": "Best Buy Products",
                "category": "E-commerce",
                "description": "Electronics and tech products from Best Buy",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["bestbuy.com"],
                "url_patterns": [r"/site/"],
                "confidence_weight": 30,
                "keywords": ["product", "site"]
            },
            "linkedin_person_profile": {
                "dataset_id": "gd_l1viktl72bvl7bjuj0",
                "display_name": "LinkedIn Person Profile",
                "category": "Social Media",
                "description": "Professional profiles and career information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/in/[^/]+/?$"],
                "confidence_weight": 35,
                "keywords": ["profile", "professional"]
            },
            "linkedin_company_profile": {
                "dataset_id": "gd_l1vikfnt1wgvvqz95w",
                "display_name": "LinkedIn Company Profile",
                "category": "Business Intelligence",
                "description": "Company information and business details",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/company/"],
                "confidence_weight": 35,
                "keywords": ["company", "business"]
            },
            "linkedin_job_listings": {
                "dataset_id": "gd_lpfll7v5hcqtkxl6l",
                "display_name": "LinkedIn Job Listings",
                "category": "Business Intelligence",
                "description": "Job postings and career opportunities",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/jobs/"],
                "confidence_weight": 30,
                "keywords": ["jobs", "career"]
            },
            "linkedin_posts": {
                "dataset_id": "gd_lyy3tktm25m4avu764",
                "display_name": "LinkedIn Posts",
                "category": "Social Media",
                "description": "Professional posts and updates",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/posts/", r"/feed/update/"],
                "confidence_weight": 25,
                "keywords": ["posts", "feed", "update"]
            },
            "linkedin_people_search": {
                "dataset_id": "gd_m8d03he47z8nwb5xc",
                "display_name": "LinkedIn People Search",
                "category": "Business Intelligence",
                "description": "Professional network search results",
                "inputs": ["url", "first_name", "last_name"],
                "defaults": {},
                "domains": ["linkedin.com"],
                "url_patterns": [r"/search/results/people/"],
                "confidence_weight": 20,
                "keywords": ["search", "people"]
            },
            "crunchbase_company": {
                "dataset_id": "gd_l1vijqt9jfj7olije",
                "display_name": "Crunchbase Company",
                "category": "Business Intelligence",
                "description": "Startup and company funding information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["crunchbase.com"],
                "url_patterns": [r"/organization/"],
                "confidence_weight": 35,
                "keywords": ["organization", "company"]
            },
            "zoominfo_company_profile": {
                "dataset_id": "gd_m0ci4a4ivx3j5l6nx",
                "display_name": "ZoomInfo Company",
                "category": "Business Intelligence",
                "description": "B2B company intelligence and contact data",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zoominfo.com"],
                "url_patterns": [r"/c/"],
                "confidence_weight": 35,
                "keywords": ["company"]
            },
            "instagram_profiles": {
                "dataset_id": "gd_l1vikfch901nx3by4",
                "display_name": "Instagram Profiles",
                "category": "Social Media",
                "description": "Instagram user profiles and bio information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/[^/]+/?$"],
                "confidence_weight": 30,
                "keywords": ["profile"]
            },
            "instagram_posts": {
                "dataset_id": "gd_lk5ns7kz21pck8jpis",
                "display_name": "Instagram Posts",
                "category": "Social Media",
                "description": "Instagram posts, photos, and engagement",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/p/"],
                "confidence_weight": 30,
                "keywords": ["post"]
            },
            "instagram_reels": {
                "dataset_id": "gd_lyclm20il4r5helnj",
                "display_name": "Instagram Reels",
                "category": "Social Media",
                "description": "Instagram Reels and short-form video content",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/reel/"],
                "confidence_weight": 30,
                "keywords": ["reel", "video"]
            },
            "instagram_comments": {
                "dataset_id": "gd_ltppn085pokosxh13",
                "display_name": "Instagram Comments",
                "category": "Social Media",
                "description": "Comments and engagement on Instagram posts",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["instagram.com"],
                "url_patterns": [r"/p/", r"/reel/"],
                "confidence_weight": 20,
                "keywords": ["comments"]
            },
            "facebook_posts": {
                "dataset_id": "gd_lyclm1571iy3mv57zw",
                "display_name": "Facebook Posts",
                "category": "Social Media",
                "description": "Facebook posts and social engagement",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/posts/", r"/permalink/"],
                "confidence_weight": 30,
                "keywords": ["posts", "permalink"]
            },
            "facebook_marketplace_listings": {
                "dataset_id": "gd_lvt9iwuh6fbcwmx1a",
                "display_name": "Facebook Marketplace",
                "category": "E-commerce",
                "description": "Facebook Marketplace product listings",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/marketplace/"],
                "confidence_weight": 30,
                "keywords": ["marketplace"]
            },
            "facebook_company_reviews": {
                "dataset_id": "gd_m0dtqpiu1mbcyc2g86",
                "display_name": "Facebook Company Reviews",
                "category": "Business Intelligence",
                "description": "Company reviews and ratings on Facebook",
                "inputs": ["url", "num_of_reviews"],
                "defaults": {"num_of_reviews": "10"},
                "domains": ["facebook.com"],
                "url_patterns": [r"/[^/]+/?$"],
                "confidence_weight": 20,
                "keywords": ["reviews"]
            },
            "facebook_events": {
                "dataset_id": "gd_m14sd0to1jz48ppm51",
                "display_name": "Facebook Events",
                "category": "Social Media",
                "description": "Facebook events and gatherings",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["facebook.com"],
                "url_patterns": [r"/events/"],
                "confidence_weight": 30,
                "keywords": ["events"]
            },
            "tiktok_profiles": {
                "dataset_id": "gd_l1villgoiiidt09ci",
                "display_name": "TikTok Profiles",
                "category": "Social Media",
                "description": "TikTok user profiles and creator information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/@[^/]+/?$"],
                "confidence_weight": 30,
                "keywords": ["profile", "creator"]
            },
            "tiktok_posts": {
                "dataset_id": "gd_lu702nij2f790tmv9h",
                "display_name": "TikTok Posts",
                "category": "Social Media",
                "description": "TikTok videos and viral content",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/video/"],
                "confidence_weight": 30,
                "keywords": ["video"]
            },
            "tiktok_shop": {
                "dataset_id": "gd_m45m1u911dsa4274pi",
                "display_name": "TikTok Shop",
                "category": "E-commerce",
                "description": "TikTok Shop products and social commerce",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/shop/"],
                "confidence_weight": 30,
                "keywords": ["shop", "product"]
            },
            "tiktok_comments": {
                "dataset_id": "gd_lkf2st302ap89utw5k",
                "display_name": "TikTok Comments",
                "category": "Social Media",
                "description": "Comments and engagement on TikTok videos",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["tiktok.com"],
                "url_patterns": [r"/video/"],
                "confidence_weight": 20,
                "keywords": ["comments"]
            },
            "google_maps_reviews": {
                "dataset_id": "gd_luzfs1dn2oa0teb81",
                "display_name": "Google Maps Reviews",
                "category": "Business Intelligence",
                "description": "Local business reviews and ratings",
                "inputs": ["url", "days_limit"],
                "defaults": {"days_limit": "3"},
                "domains": ["google.com", "maps.google.com"],
                "url_patterns": [r"/maps/", r"/@"],
                "confidence_weight": 25,
                "keywords": ["maps", "reviews"]
            },
            "google_shopping": {
                "dataset_id": "gd_ltppk50q18kdw67omz",
                "display_name": "Google Shopping",
                "category": "E-commerce",
                "description": "Google Shopping product listings and prices",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["google.com"],
                "url_patterns": [r"/shopping/"],
                "confidence_weight": 30,
                "keywords": ["shopping", "product"]
            },
            "google_play_store": {
                "dataset_id": "gd_lsk382l8xei8vzm4u",
                "display_name": "Google Play Store",
                "category": "Technology",
                "description": "Android apps and games from Play Store",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["play.google.com"],
                "url_patterns": [r"/store/apps/"],
                "confidence_weight": 35,
                "keywords": ["apps", "store"]
            },
            "apple_app_store": {
                "dataset_id": "gd_lsk9ki3u2iishmwrui",
                "display_name": "Apple App Store",
                "category": "Technology",
                "description": "iOS apps and games from App Store",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["apps.apple.com"],
                "url_patterns": [r"/app/"],
                "confidence_weight": 35,
                "keywords": ["app", "ios"]
            },
            "reuter_news": {
                "dataset_id": "gd_lyptx9h74wtlvpnfu",
                "display_name": "Reuters News",
                "category": "News & Content",
                "description": "News articles and financial reporting",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["reuters.com"],
                "url_patterns": [r"/"],
                "confidence_weight": 25,
                "keywords": ["news", "article"]
            },
            "github_repository_file": {
                "dataset_id": "gd_lyrexgxc24b3d4imjt",
                "display_name": "GitHub Repository",
                "category": "Technology",
                "description": "Code repositories and file contents",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["github.com"],
                "url_patterns": [r"/blob/", r"/tree/"],
                "confidence_weight": 30,
                "keywords": ["code", "repository"]
            },
            "yahoo_finance_business": {
                "dataset_id": "gd_lmrpz3vxmz972ghd7",
                "display_name": "Yahoo Finance",
                "category": "Business Intelligence",
                "description": "Stock quotes, financial data, and market news",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["finance.yahoo.com"],
                "url_patterns": [r"/quote/"],
                "confidence_weight": 35,
                "keywords": ["finance", "stock", "quote"]
            },
            "x_posts": {
                "dataset_id": "gd_lwxkxvnf1cynvib9co",
                "display_name": "X (Twitter) Posts",
                "category": "Social Media",
                "description": "Social media posts and trending content",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["x.com", "twitter.com"],
                "url_patterns": [r"/status/"],
                "confidence_weight": 30,
                "keywords": ["tweet", "status"]
            },
            "zillow_properties_listing": {
                "dataset_id": "gd_lfqkr8wm13ixtbd8f5",
                "display_name": "Zillow Properties",
                "category": "Real Estate",
                "description": "Real estate listings and property data",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["zillow.com"],
                "url_patterns": [r"/homedetails/"],
                "confidence_weight": 35,
                "keywords": ["property", "real estate"]
            },
            "booking_hotel_listings": {
                "dataset_id": "gd_m5mbdl081229ln6t4a",
                "display_name": "Booking.com Hotels",
                "category": "Travel & Hospitality",
                "description": "Hotel listings, rates, and reviews",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["booking.com"],
                "url_patterns": [r"/hotel/"],
                "confidence_weight": 35,
                "keywords": ["hotel", "accommodation"]
            },
            "youtube_profiles": {
                "dataset_id": "gd_lk538t2k2p1k3oos71",
                "display_name": "YouTube Profiles",
                "category": "Social Media",
                "description": "YouTube channels and creator information",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["youtube.com"],
                "url_patterns": [r"/channel/", r"/c/", r"/@[^/]+/?$"],
                "confidence_weight": 30,
                "keywords": ["channel", "creator"]
            },
            "youtube_videos": {
                "dataset_id": "gd_lk538t2k2p1k3oos72",
                "display_name": "YouTube Videos",
                "category": "Social Media",
                "description": "Video content, metadata, and analytics",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["youtube.com"],
                "url_patterns": [r"/watch\?v="],
                "confidence_weight": 35,
                "keywords": ["video", "watch"]
            },
            "youtube_comments": {
                "dataset_id": "gd_lk9q0ew71spt1mxywf",
                "display_name": "YouTube Comments",
                "category": "Social Media",
                "description": "Video comments and engagement metrics",
                "inputs": ["url", "num_of_comments"],
                "defaults": {"num_of_comments": "10"},
                "domains": ["youtube.com"],
                "url_patterns": [r"/watch\?v="],
                "confidence_weight": 20,
                "keywords": ["comments"]
            },
            "reddit_posts": {
                "dataset_id": "gd_lvz8ah06191smkebj4",
                "display_name": "Reddit Posts",
                "category": "Social Media",
                "description": "Reddit posts, discussions, and community content",
                "inputs": ["url"],
                "defaults": {},
                "domains": ["reddit.com"],
                "url_patterns": [r"/r/", r"/comments/"],
                "confidence_weight": 30,
                "keywords": ["reddit", "post", "discussion"]
            }
        }

    def _detect_website_type(self, url: str) -> Tuple[Optional[str], int, Dict[str, Any]]:
        """Enhanced auto-detection with detailed scoring and confidence analysis"""
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc.replace('www.', '').replace('m.', '')
        path = parsed_url.path
        query = parsed_url.query
        fragment = parsed_url.fragment
        
        datasets = self._get_all_datasets()
        all_scores = []
        
        for dataset_name, config in datasets.items():
            score_breakdown = {
                "dataset": dataset_name,
                "display_name": config["display_name"],
                "category": config["category"],
                "total_score": 0,
                "domain_score": 0,
                "pattern_score": 0,
                "keyword_score": 0,
                "specificity_bonus": 0,
                "matched_patterns": [],
                "matched_keywords": [],
                "matched_domain": None
            }
            
            # Domain matching (highest weight)
            for dataset_domain in config.get("domains", []):
                if dataset_domain in domain:
                    domain_score = config.get("confidence_weight", 20)
                    score_breakdown["domain_score"] = domain_score
                    score_breakdown["matched_domain"] = dataset_domain
                    break
            
            # URL pattern matching
            full_url = f"{path}?{query}#{fragment}".lower()
            for pattern in config.get("url_patterns", []):
                if re.search(pattern, full_url):
                    pattern_score = 25
                    score_breakdown["pattern_score"] += pattern_score
                    score_breakdown["matched_patterns"].append(pattern)
                    break
            
            # Keyword matching in URL
            for keyword in config.get("keywords", []):
                if keyword.lower() in full_url:
                    keyword_score = 10
                    score_breakdown["keyword_score"] += keyword_score
                    score_breakdown["matched_keywords"].append(keyword)
            
            # Calculate total score
            base_score = score_breakdown["domain_score"] + score_breakdown["pattern_score"] + score_breakdown["keyword_score"]
            
            # Apply specificity bonuses for precise matches
            if score_breakdown["domain_score"] > 0 and score_breakdown["pattern_score"] > 0:
                # Enhanced scoring for specific platform matches
                specificity_bonus = self._calculate_specificity_bonus(dataset_name, url, domain, path, query)
                score_breakdown["specificity_bonus"] = specificity_bonus
                base_score += specificity_bonus
            
            score_breakdown["total_score"] = base_score
            
            if base_score > 0:
                all_scores.append(score_breakdown)
        
        # Sort by total score
        all_scores.sort(key=lambda x: x["total_score"], reverse=True)
        
        detection_details = {
            "url": url,
            "parsed_domain": domain,
            "total_datasets_checked": len(datasets),
            "datasets_with_scores": len(all_scores),
            "all_scores": all_scores[:10],  # Top 10 for brevity
            "detection_method": "enhanced_ai_scoring"
        }
        
        if all_scores and all_scores[0]["total_score"] >= 15:
            best_match = all_scores[0]
            logger.info(f"Auto-detected dataset: {best_match['dataset']} (confidence: {best_match['total_score']})")
            return best_match["dataset"], best_match["total_score"], detection_details
        
        logger.warning(f"Could not auto-detect dataset for URL: {url}")
        return None, 0, detection_details

    def _calculate_specificity_bonus(self, dataset_name: str, url: str, domain: str, path: str, query: str) -> int:
        """Calculate specificity bonus based on precise pattern matching"""
        bonus = 0
        url_lower = url.lower()
        
        # LinkedIn specific bonuses
        if "linkedin.com" in domain:
            if dataset_name == "linkedin_person_profile" and re.search(r"/in/[^/]+/?$", path):
                bonus += 20
            elif dataset_name == "linkedin_company_profile" and "/company/" in path:
                bonus += 20
            elif dataset_name == "linkedin_job_listings" and "/jobs/" in path:
                bonus += 15
            elif dataset_name == "linkedin_posts" and ("/posts/" in path or "/feed/update/" in path):
                bonus += 15
        
        # Amazon specific bonuses
        elif any(amazon_domain in domain for amazon_domain in ["amazon.com", "amazon.co.uk", "amazon.de"]):
            if dataset_name == "amazon_product" and ("/dp/" in path or "/gp/product/" in path):
                if "#customerreviews" not in url_lower and "/product-reviews/" not in path:
                    bonus += 20
            elif dataset_name == "amazon_product_reviews":
                if "#customerreviews" in url_lower or "/product-reviews/" in path:
                    bonus += 25
            elif dataset_name == "amazon_product_search" and ("/s?" in path or "field-keywords" in query):
                bonus += 15
        
        # YouTube specific bonuses
        elif "youtube.com" in domain:
            if dataset_name == "youtube_videos" and "/watch?v=" in url_lower:
                bonus += 25
            elif dataset_name == "youtube_profiles":
                if "/channel/" in path or "/c/" in path or re.search(r"/@[^/]+/?$", path):
                    bonus += 20
        
        # Instagram specific bonuses
        elif "instagram.com" in domain:
            if dataset_name == "instagram_posts" and "/p/" in path:
                bonus += 20
            elif dataset_name == "instagram_reels" and "/reel/" in path:
                bonus += 20
            elif dataset_name == "instagram_profiles" and re.search(r"/[^/]+/?$", path):
                if "/p/" not in path and "/reel/" not in path:
                    bonus += 15
        
        # TikTok specific bonuses
        elif "tiktok.com" in domain:
            if dataset_name == "tiktok_posts" and "/video/" in path:
                bonus += 20
            elif dataset_name == "tiktok_profiles" and re.search(r"/@[^/]+/?$", path):
                bonus += 20
            elif dataset_name == "tiktok_shop" and "/shop/" in path:
                bonus += 20
        
        # E-commerce platform bonuses
        elif "ebay.com" in domain and dataset_name == "ebay_product" and "/itm/" in path:
            bonus += 20
        elif "etsy.com" in domain and dataset_name == "etsy_products" and "/listing/" in path:
            bonus += 20
        elif "walmart.com" in domain:
            if dataset_name == "walmart_product" and "/ip/" in path:
                bonus += 20
            elif dataset_name == "walmart_seller" and "/seller/" in path:
                bonus += 20
        
        # App store bonuses
        elif "play.google.com" in domain and dataset_name == "google_play_store" and "/store/apps/" in path:
            bonus += 25
        elif "apps.apple.com" in domain and dataset_name == "apple_app_store" and "/app/" in path:
            bonus += 25
        
        # Real estate and travel bonuses
        elif "zillow.com" in domain and dataset_name == "zillow_properties_listing" and "/homedetails/" in path:
            bonus += 25
        elif "booking.com" in domain and dataset_name == "booking_hotel_listings" and "/hotel/" in path:
            bonus += 25
        
        return bonus
    
    def get_url_from_input(self) -> str:
        """Extract URL from the input, handling both Message and string types"""
        # Langflow automatically converts inputs to appropriate types
        # We just need to handle Message vs string cases
        if hasattr(self.url_input, 'text'):
            # It's a Message object
            return str(self.url_input.text).strip()
        else:
            # It's already a string or can be converted to string
            return str(self.url_input or "").strip()
        
    def _prepare_dataset_payload(self, data_type: str, url: str, additional_params: Dict[str, Any]) -> Dict[str, Any]:
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
        """Extract structured data using Bright Data's datasets API with enhanced error handling"""
        # Validate inputs
        if not self.api_token:
            msg = "API token is required"
            raise ValueError(msg)

        url = self.get_url_from_input()
        if not url:
            msg = "URL is required"
            raise ValueError(msg)
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        self.url = url

        try:
            # Parse additional parameters
            try:
                additional_params = json.loads(self.additional_params) if self.additional_params.strip() else {}
                if not isinstance(additional_params, dict):
                    additional_params = {}
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in additional_params: {str(e)}, using empty dict")
                additional_params = {}
            
            # Store detection details for output
            detection_details = None
            
            # Determine which dataset to use
            if self.auto_detect:
                detected_type, confidence, detection_details = self._detect_website_type(url)
                if not detected_type:
                    parsed_url = urlparse(self.url)
                    available_domains = self._get_supported_domains()
                    error_msg = (f"Could not automatically detect website type for domain: {parsed_url.netloc}\n"
                               f"Supported domains include: {', '.join(available_domains[:10])}...\n"
                               f"Please disable auto-detect and manually select a data type.")
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                data_type = detected_type
                logger.info(f"Auto-detected data type: {data_type} (confidence: {confidence})")
            else:
                data_type = self.manual_data_type
                confidence = None
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
            payload = self._prepare_dataset_payload(data_type, url, additional_params)
            trigger_payload = [payload]
            
            logger.info(f"Triggering data collection for dataset {dataset_id} ({dataset_config['display_name']}) with payload: {payload}")
            
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
            
            # Poll for results with progress tracking
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
                        final_data: Union[Dict[str, Any], List[Any], None] = None
                        
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
                            logger.info(f"Data collection completed with status: {status} after {attempts} attempts")
                            
                            # Prepare comprehensive output data
                            output_data = {
                                "url": url,
                                "dataset_key": data_type,
                                "dataset_name": dataset_config["display_name"],
                                "dataset_category": dataset_config["category"],
                                "dataset_id": dataset_id,
                                "snapshot_id": snapshot_id,
                                "status": "success",
                                "collection_time_seconds": round(time.time() - start_time, 2),
                                "attempts": attempts,
                                "auto_detected": self.auto_detect,
                                "payload_used": payload,
                                "structured_data": final_data
                            }
                            
                            if self.auto_detect and confidence is not None:
                                output_data["detection_confidence"] = confidence
                                if self.show_detection_details and detection_details:
                                    output_data["detection_details"] = detection_details
                            
                            return Data(data=output_data)
                        else:
                            elapsed = round(time.time() - start_time, 1)
                            logger.info(f"Still running (attempt {attempts}, elapsed: {elapsed}s), waiting...")
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

    def get_detection_info(self) -> Data:
        """Get detailed information about the auto-detection process"""
        if not self.auto_detect:
            return Data(data={
                "auto_detect_enabled": False,
                "message": "Auto-detection is disabled. Enable it to see detection analysis."
            })
        
        try:
            # Run detection analysis
            url = self.get_url_from_input()
            detected_type, confidence, detection_details = self._detect_website_type(url)
            
            analysis_data = {
                "auto_detect_enabled": True,
                "url_analyzed": url,
                "detection_successful": detected_type is not None,
                "recommended_dataset": detected_type,
                "confidence_score": confidence,
                "max_possible_confidence": 175,  # Theoretical maximum
                "threshold_used": 15,
                "detection_details": detection_details,
                "available_datasets_count": len(self._get_all_datasets()),
                "supported_domains": self._get_supported_domains()
            }
            
            if detected_type:
                dataset_config = self._get_all_datasets()[detected_type]
                analysis_data["recommended_dataset_info"] = {
                    "display_name": dataset_config["display_name"],
                    "category": dataset_config["category"],
                    "description": dataset_config["description"],
                }
            
            return Data(data=analysis_data)
            
        except Exception as e:
            logger.error(f"Error generating detection info: {str(e)}")
            return Data(data={
                "error": str(e),
                "auto_detect_enabled": True,
                "detection_successful": False
            })

    def _get_supported_domains(self) -> List[str]:
        """Get list of all supported domains"""
        domains = set()
        for config in self._get_all_datasets().values():
            domains.update(config.get("domains", []))
        return sorted(list(domains))