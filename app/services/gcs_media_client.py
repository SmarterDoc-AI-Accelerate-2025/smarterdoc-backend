# app/services/gcs_media_client.py

import requests
from google.cloud import storage
from typing import Dict, Any, Optional
from app.config import settings
from app.util.logging import logger

# --- Configuration (using Google Custom Search API as placeholder) ---
SEARCH_API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# FIX: Define AGGRESSIVE HEADERS to bypass hotlinking and anti-scraping measures.
HEADERS = {
    # 1. User-Agent: Pretend to be a common browser
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    # 2. Referer: Pretend the request came from Google Images itself (crucial for bypassing hotlink blocks)
    'Referer': 'https://www.google.com/',
    # 3. Accept: Tell the server we only want image data
    'Accept':
    'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
}


class GCSMediaClient:
    """
    Client for orchestrating image search, download, and permanent upload to GCS.
    """

    def __init__(self):
        """Initializes the GCS client and search configurations."""
        self.bucket_name = settings.GCP_MEDIA_BUCKET
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.search_api_key = settings.GOOGLE_SEARCH_API_KEY
        self.cse_id = settings.GOOGLE_SEARCH_CSE_ID

        if not self.bucket_name:
            logger.error(
                "GCP_MEDIA_BUCKET is not set. Media uploads will fail.")

    def _find_image_url(self, doctor_name: str) -> Optional[str]:
        """
        Uses the search API to find the URL of the highest ranked profile image.
        """
        if not self.search_api_key or not self.cse_id:
            logger.warning(
                "Search credentials missing. Skipping image search.")
            return None

        query = f"Dr. {doctor_name} professional profile picture"

        params = {
            "key": self.search_api_key,
            "cx": self.cse_id,
            "q": query,
            "searchType": "image",  # Crucial for Google Image Search
            "num": 1
        }

        try:
            response = requests.get(SEARCH_API_ENDPOINT,
                                    params=params,
                                    timeout=10).json()

            # Extract the direct image link from the top result
            if response.get('items') and response['items'][0].get('link'):
                return response['items'][0]['link']

            return None
        except Exception as e:
            logger.error(f"Image search failed for {doctor_name}: {e}")
            return None

    def upload_from_url(self, external_url: str,
                        blob_name: str) -> Optional[str]:
        """
        Downloads the image from the external URL and uploads it to GCS.
        """
        if not self.bucket_name:
            return None

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"doctor_media/{blob_name}")

        try:
            # 1. Download image data (FIX: Inject Aggressive Headers here)
            image_response = requests.get(external_url,
                                          stream=True,
                                          timeout=15,
                                          headers=HEADERS)  # <-- FIX IS HERE
            image_response.raise_for_status(
            )  # Will raise 403 Forbidden if headers fail

            # 2. Upload to GCS
            blob.upload_from_string(image_response.content,
                                    content_type=image_response.headers.get(
                                        'Content-Type', 'image/jpeg'))

            # 3. Make the file publicly readable
            blob.make_public()

            logger.info(f"Successfully uploaded {blob_name} to GCS.")
            return blob.public_url

        except Exception as e:
            # This catch will now log the specific 403 or 404 if the headers still fail.
            logger.error(f"Failed to upload image {external_url}: {e}")
            return None

    def acquire_and_upload_profile_pic(self, doctor_data: Dict[str, Any],
                                       npi: str) -> Optional[str]:
        """
        Orchestrates the search and upload process.
        """
        full_name = f"{doctor_data['first_name']} {doctor_data['last_name']} {doctor_data['primary_specialty']}"

        # 1. Find a working image URL from the web
        external_url = self._find_image_url(full_name)

        if not external_url:
            logger.warning(
                f"Could not find valid external image URL for NPI {npi}.")
            return None

        # 2. Upload the found image to a permanent GCS location
        blob_name = f"profile_{npi}.jpg"
        permanent_url = self.upload_from_url(external_url, blob_name)

        return permanent_url


gcs_media_client = GCSMediaClient()
