import os
import time
import json
import hashlib
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional

import requests
import pandas as pd


class GraphAPIConfig:
    """Configuration for Meta Graph API."""

    def __init__(self):
        self.api_version = os.getenv('GRAPH_API_VERSION', 'v19.0')
        self.request_timeout = int(os.getenv('API_REQUEST_TIMEOUT', '30'))
        self.rate_limit_sleep = int(os.getenv('RATE_LIMIT_SLEEP_SECONDS', '60'))
        self.data_retention_days = int(os.getenv('DATA_RETENTION_DAYS', '15'))


class GraphAPIClient:
    """Client for interacting with Meta Graph API."""

    def __init__(self, account_id: str, access_token: str, config: GraphAPIConfig = None):
        """
        Initialize Graph API client.

        Args:
            account_id: Meta Ads account ID (without 'act_' prefix)
            access_token: Graph API access token
            config: API configuration object
        """
        self.account_id = account_id
        self.access_token = access_token
        self.config = config or GraphAPIConfig()

        self.insights_url = (
            f"https://graph.facebook.com/{self.config.api_version}/"
            f"act_{account_id}/insights"
        )
        self.campaigns_url = (
            f"https://graph.facebook.com/{self.config.api_version}/"
            f"act_{account_id}/campaigns"
        )

    def get_time_range(self) -> Dict[str, str]:
        """
        Get time range for API requests based on data retention configuration.

        Returns:
            Dictionary with 'since' and 'until' date strings
        """
        today = date.today()
        start_date = today - timedelta(days=self.config.data_retention_days)
        return {
            "since": str(start_date),
            "until": str(today)
        }

    def paginate_api(self, url: str, params: Dict) -> List[Dict]:
        """
        Paginate through API results handling rate limits.

        Args:
            url: API endpoint URL
            params: Request parameters

        Returns:
            List of all data items from paginated responses
        """
        all_data = []
        next_url = url
        page_count = 1

        print(f"📡 Starting API request: {url}")

        while next_url:
            try:
                response = requests.get(
                    next_url,
                    params=params if next_url == url else None,
                    timeout=self.config.request_timeout
                )

                if response.status_code != 200:
                    print(f"❌ Error {response.status_code}: {response.text}")

                    # Handle rate limiting
                    if "too many calls" in response.text.lower():
                        print(f"⏳ Rate limit hit, waiting {self.config.rate_limit_sleep}s...")
                        time.sleep(self.config.rate_limit_sleep)
                        continue

                    break

                json_data = response.json()
                data = json_data.get('data', [])
                all_data.extend(data)

                print(f"✅ Page {page_count} - {len(data)} items retrieved")

                # Get next page URL
                next_url = json_data.get('paging', {}).get('next')
                page_count += 1

            except requests.exceptions.RequestException as e:
                print(f"❌ Request error: {e}")
                break

        print(f"📊 Total items retrieved: {len(all_data)}")
        return all_data

    def get_insights(self) -> List[Dict]:
        """
        Fetch ad insights from Graph API.

        Returns:
            List of insight records
        """
        params = {
            "time_increment": 1,
            "time_range": json.dumps(self.get_time_range()),
            "level": "ad",
            "fields": (
                "ad_name,ad_id,adset_name,adset_id,campaign_name,campaign_id,"
                "account_id,account_name,spend,clicks,inline_link_clicks,"
                "impressions,objective,actions,date_start"
            ),
            "access_token": self.access_token
        }

        return self.paginate_api(self.insights_url, params)

    def get_campaigns(self) -> List[Dict]:
        """
        Fetch campaign information from Graph API.

        Returns:
            List of campaign records
        """
        params = {
            "fields": "id,name,status,start_time",
            "access_token": self.access_token
        }

        return self.paginate_api(self.campaigns_url, params)


class GraphAPIDataProcessor:
    """Process and transform Graph API data for database storage."""

    @staticmethod
    def generate_unique_id(row: pd.Series) -> str:
        """
        Generate MD5 hash for row to use as unique identifier.

        Args:
            row: Pandas Series representing a row

        Returns:
            MD5 hash string
        """
        concatenated = "_".join(row.astype(str))
        return hashlib.md5(concatenated.encode()).hexdigest()

    @staticmethod
    def process_insights_data(
        insights: List[Dict],
        campaigns: List[Dict],
        account_id: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Process raw insights and campaigns data into structured DataFrames.

        Args:
            insights: Raw insights data from API
            campaigns: Raw campaigns data from API
            account_id: Meta Ads account ID

        Returns:
            Tuple of (ads_dataframe, actions_dataframe)
        """
        adset_data = []
        actions_data = []

        # Process insights
        for item in insights:
            adset_info = {
                'account_id': account_id,
                'account_name': item.get('account_name'),
                'adset_id': item.get('adset_id'),
                'adset_name': item.get('adset_name'),
                'ad_id': item.get('ad_id'),
                'ad_name': item.get('ad_name'),
                'campaign_id': item.get('campaign_id'),
                'campaign_name': item.get('campaign_name'),
                'objective': item.get('objective'),
                'spend': float(item.get('spend', 0)),
                'clicks': int(item.get('clicks', 0)),
                'inline_link_clicks': int(item.get('inline_link_clicks', 0)),
                'impressions': int(item.get('impressions', 0)),
                'date': item.get('date_start')
            }
            adset_data.append(adset_info)

            # Process actions
            for action in item.get('actions', []):
                actions_data.append({
                    'account_id': account_id,
                    'ad_id': item.get('ad_id'),
                    'action_type': action.get('action_type'),
                    'value': int(action.get('value', 0)),
                    'date': adset_info['date']
                })

        # Create DataFrames
        df_adset = pd.DataFrame(adset_data)
        df_actions = pd.DataFrame(actions_data)

        # Process campaigns
        campaigns_data = []
        for campaign in campaigns:
            campaigns_data.append({
                'account_id': account_id,
                'campaign_id': campaign.get('id'),
                'campaign_name': campaign.get('name'),
                'campaign_status': campaign.get('status'),
                'start_time': campaign.get('start_time')
            })

        df_campaigns = pd.DataFrame(campaigns_data)

        # Merge ads with campaign status
        df_ads = df_adset.merge(
            df_campaigns[['campaign_id', 'campaign_status']],
            on='campaign_id',
            how='left'
        )

        # Add unique identifier
        if not df_ads.empty:
            df_ads['unique_id'] = df_ads.apply(
                GraphAPIDataProcessor.generate_unique_id,
                axis=1
            )

        return df_ads, df_actions


def extract_meta_ads_data(
    account_id: str,
    access_token: str,
    table_name: str,
    actions_table_name: str,
    db_manager,
    schema: str = None
) -> None:
    """
    Main extraction function for Meta Ads data.

    Args:
        account_id: Meta Ads account ID
        access_token: Graph API access token
        table_name: Target table for ads data
        actions_table_name: Target table for actions data
        db_manager: DatabaseManager instance
        schema: Database schema name
    """
    print(f"\n{'='*60}")
    print(f"🚀 Starting extraction for account: {account_id}")
    print(f"{'='*60}\n")

    # Initialize API client
    client = GraphAPIClient(account_id, access_token)

    # Fetch data from API
    print("📥 Fetching insights data...")
    insights = client.get_insights()

    print("📥 Fetching campaigns data...")
    campaigns = client.get_campaigns()

    print("✅ Data extraction completed\n")

    # Process data
    print("🔄 Processing data...")
    processor = GraphAPIDataProcessor()
    df_ads, df_actions = processor.process_insights_data(
        insights, campaigns, account_id
    )

    print(f"📊 Processed {len(df_ads)} ad records")
    print(f"📊 Processed {len(df_actions)} action records\n")

    # Save to database
    print("💾 Saving to database...")
    db_manager.upsert_dataframe(df_ads, table_name, "date", schema)
    db_manager.upsert_dataframe(df_actions, actions_table_name, "date", schema)

    print(f"\n{'='*60}")
    print(f"✅ Extraction completed successfully for account: {account_id}")
    print(f"{'='*60}\n")
