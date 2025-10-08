import requests
from google.cloud import storage
from typing import Dict, Any, Optional
from app.config import settings
from app.util.logging import logger

# --- Configuration (using Google Custom Search API as placeholder) ---
# TODO: configure a Google Custom Search Engine (CSE) with Image Search enabled
# to get valid API_KEY and CSE_ID.
SEARCH_API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


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
            "num": 1  # Only need the top result
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
        
        Args:
            external_url: The temporary URL found by the search.
            blob_name: The target filename in GCS (e.g., 'npi-12345.jpg').
            
        Returns:
            The permanent, public GCS URL.
        """
        if not self.bucket_name:
            return None

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"doctor_media/{blob_name}")

        try:
            # 1. Download image data
            image_response = requests.get(external_url,
                                          stream=True,
                                          timeout=15)
            image_response.raise_for_status(
            )  # Raise exception for bad status codes

            # 2. Upload to GCS
            blob.upload_from_string(image_response.content,
                                    content_type=image_response.headers.get(
                                        'Content-Type', 'image/jpeg'))

            # 3. Make the file publicly readable (required for easy frontend display)
            blob.make_public()

            logger.info(f"Successfully uploaded {blob_name} to GCS.")
            return blob.public_url  # Returns the permanent storage URL

        except Exception as e:
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
