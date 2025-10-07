import os
import json
import requests
from typing import Dict, Any, Tuple
from app.config import settings
from app.util.logging import logger 

# Placeholder for the actual Google Search API endpoint or a custom scraper service
# For real use, you would plug in a client library for Google Custom Search or a scraper API here.
SEARCH_API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


class WebSearchClient:
    """
    Client for interacting with external web search APIs to gather
    unstructured profile data, ratings, and image URLs.
    """

    def __init__(self):
        """Initializes the search client with necessary API keys."""
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.cse_id = settings.GOOGLE_SEARCH_CSE_ID  # Custom Search Engine ID

        if not self.api_key or not self.cse_id:
            logger.error(
                "Google Search API Key or CSE ID is missing in configuration. "
                "Web search enrichment will fail.")
            # In a real job, you might raise an exception here or set a flag to skip search.

    def _run_search(self, query: str) -> Dict[str, Any]:
        """Executes the Google Custom Search query."""
        if not self.api_key or not self.cse_id:
            return {"items": []}

        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": 5  # Get top 5 results
        }

        try:
            # Note: This is a synchronous call. For 870 doctors, you will need
            # to run the outer enrichment loop in jobs/indexer.py asynchronously
            # (e.g., using asyncio) to handle this latency efficiently.
            response = requests.get(SEARCH_API_ENDPOINT,
                                    params=params,
                                    timeout=10)
            response.raise_for_status(
            )  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Google Search API request failed for query '{query}': {e}")
            return {"items": []}

    def search_and_extract_bio(
            self, doctor_data: Dict[str, str]) -> Tuple[str, str, str]:
        """
        Runs a targeted search query and consolidates information needed for the LLM.

        Args:
            doctor_data: Dictionary containing 'first_name', 'last_name', 'primary_specialty'.
            
        Returns:
            A tuple: (consolidated_text, best_image_url, review_snippets)
        """

        # 1. Build Targeted Query (focus on biography and official sites)
        query = (f"{doctor_data['first_name']} {doctor_data['last_name']} "
                 f"'{doctor_data['primary_specialty']}' official biography")

        search_results = self._run_search(query)

        # 2. Consolidate Raw Text and Find Image URL
        consolidated_text_chunks = []
        best_image_url = ""
        review_snippets = ""

        items = search_results.get('items', [])

        for item in items:
            # Collect snippet text for the LLM to analyze
            snippet = item.get('snippet', '')
            consolidated_text_chunks.append(
                f"Source: {item.get('displayLink')}\nSnippet: {snippet}")

            # Simple heuristic to find a potential profile picture URL
            if not best_image_url and item.get('pagemap'):
                # Look for image objects in the structured metadata (common on profile sites)
                pagemap = item['pagemap']
                if 'cse_image' in pagemap:
                    image_url = pagemap['cse_image'][0].get('src')
                    best_image_url = image_url

            # Placeholder: Extracting review snippets (often requires dedicated scraping)
            if 'reviews' in item.get(
                    'title', '').lower() or 'reviews' in snippet.lower():
                review_snippets += f"- {snippet}\n"

        # Join the snippets into a single text block for the LLM
        consolidated_text = "\n\n---\n\n".join(consolidated_text_chunks)

        logger.info(
            f"Consolidated data for {doctor_data['last_name']}: {len(consolidated_text)} chars."
        )

        return consolidated_text, best_image_url, review_snippets


# Instantiate the client once for use in the indexer job
web_search_client = WebSearchClient()
