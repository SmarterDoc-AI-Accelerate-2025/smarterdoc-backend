import json
import time
from typing import List, Dict, Any, Tuple
import re
from google import genai
from google.genai import types

from pydantic import BaseModel, Field

from app.config import settings
from app.util.logging import logger


# pydantic schemas
class RatingRecord(BaseModel):
    """Schema for a single rating/review record."""
    source: str = Field(
        description="Name of the review platform. (e.g. ZocDoc)")
    score: float = Field(description="The numerical rating (e.g. 4.5, 5.0).")
    count: int = Field(
        description=
        "The total number of patient reviews counted from this source.")
    link: str = Field(description="URL to the original review page.")


class ApiEnrichedProfileData(BaseModel):
    """The final structured data object to be extracted by the LLM."""
    years_experience: int = Field(
        description=
        "Total years of clinical practice since residency/fellowship completion, calculated by LLM."
    )
    bio_text_consolidated: str = Field(
        description=
        "Comprehensive biographical paragraph summarizing the doctor's experience, education, and special interests."
    )
    publications: List[str] = Field(
        description=
        "A list of titles of 3-5 key professional publications or research papers."
    )
    ratings_summary: List[RatingRecord] = Field(
        description=
        "List of structured rating records from all unique platforms found.")

    testimonial_summary_text: str = Field(
        description=
        "Summary of key patient testimonials and overall feedback to help new patients"
    )
    latitude: float = Field(
        description=
        "The decimal latitude coordinate of the primary practice location.")
    longitude: float = Field(
        description=
        "The decimal longitude coordinate of the primary practice location.")
    education: List[str] = Field(
        description="Medical schools, residencies, fellowships.")
    hospitals: List[str] = Field(
        description="Current hospital or clinical affiliations.")
    certifications: List[str] = Field(description="Board certifications.")


def _clean_llm_artifacts(text: str) -> str:
    """
    Strips out known artifacts (like token indices) that the LLM occasionally 
    embeds into text fields, which corrupt the output.
    """
    if not text:
        return text

    # Pattern 1: Matches [INDEX 1, 2, 3, ...] or [INDEX 1] artifacts
    text = re.sub(r'\[INDEX\s+\d+(?:,\s*\d+)*\]',
                  '',
                  text,
                  flags=re.IGNORECASE)

    # Pattern 2: Matches artifact text like INDEX_1256 that occasionally appears
    text = re.sub(r'INDEX_\d+', '', text, flags=re.IGNORECASE)

    # Pattern 3: Matches leftover JSON keys that might leak out of the structure
    # Example: "{"source": "Vitals", INDEX_123: 0, "score": 4.5}" -> Not perfect, but helps.

    return text.strip()


class GeminiClient:
    """
    Handles all interactions with the Google Gen AI SDK (Vertex AI API).
    """

    EMBEDDING_MODEL = "text-embedding-004"

    def __init__(self):
        """Initializes the unified Gen AI Client for Vertex AI."""
        self.client = genai.Client(vertexai=True,
                                   project=settings.GCP_PROJECT_ID,
                                   location=settings.GCP_REGION)
        self.llm_model = settings.GEMINI_MODEL

    def _call_gemini_api(self, prompt_text: str,
                         config: types.GenerateContentConfig) -> Any:
        """Internal function to call the models.generate_content method."""
        try:
            response = self.client.models.generate_content(
                model=self.llm_model,
                contents=prompt_text,
                config=config,
            )

            if response.candidates[0].finish_reason.name != "STOP":
                logger.warning(
                    f"LLM finished unexpectedly: {response.candidates[0].finish_reason.name}"
                )
                return response

            return response

        except Exception as e:
            logger.error(f"Gemini API call failed. Error: {e}")
            return None

    def extract_structured_data(self,
                                unstructured_text: str) -> Dict[str, Any]:
        """
        FALLBACK PATH. Extracts data fields from a block of unstructured text.
        """
        if not unstructured_text:
            return {}

        schema = ApiEnrichedProfileData.model_json_schema()

        system_instruction = (
            "You are an expert medical data extractor. Your task is to analyze the "
            "provided unstructured text about a doctor and extract specific details. "
            "You must strictly adhere to the provided JSON schema. "
            "Calculate 'years_experience' based on the earliest date of residency/fellowship completion found. "
            "Only return the JSON object.")

        prompt_text = (
            f"Doctor's consolidated profile text:\n\n---\n{unstructured_text}\n---\n\n"
            "Please extract all requested information into the JSON structure."
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )

        # Retrieve full response object
        response = self._call_gemini_api(prompt_text, config)

        # Check for critical failure
        if response is None or not response.candidates:
            return {}

        json_str = response.candidates[0].content.parts[0].text.strip()
        if not json_str:
            return {}

        json_str = _clean_llm_artifacts(json_str)

        try:
            # Validate and convert the JSON string to a Python dictionary
            extracted_dict = ApiEnrichedProfileData.model_validate_json(
                json_str).model_dump()
            return extracted_dict
        except Exception as e:
            logger.error(
                f"Pydantic validation failed for Gemini output: {e}. Raw JSON: {json_str[:200]}..."
            )
            return {}

    def extract_structured_data_with_grounding(
        self, prompt_instruction: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        PRIMARY PATH. Uses Gemini's built-in Google Search tool to find information 
        and return structured results PLUS the grounding sources.
        """

        schema = ApiEnrichedProfileData.model_json_schema()
        empty_result = {}, []

        config = types.GenerateContentConfig(
            max_output_tokens=16384,
            # model grounding
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.1,
        )

        # Retrieve full response object
        response = self._call_gemini_api(prompt_instruction, config)

        # Check for critical failure or empty candidate list
        if response is None or not response.candidates:
            return empty_result

        # ------------DEBUG------------
        logger.info(
            f"----FOR DEBUGGING--- Full API Response --- \n{response}========="
        )
        # -----------------------------------

        candidate = response.candidates[0]
        json_str = candidate.content.parts[0].text.strip()

        if not json_str:
            logger.warning(
                f"Gemini returned empty JSON string. Reason: {candidate.finish_reason.name}"
            )
            return empty_result

        json_str = _clean_llm_artifacts(json_str)

        try:
            extracted_dict = ApiEnrichedProfileData.model_validate_json(
                json_str).model_dump()

            extracted_dict['bio_text_consolidated'] = _clean_llm_artifacts(
                extracted_dict.get('bio_text_consolidated', ''))
            extracted_dict['testimonial_summary_text'] = _clean_llm_artifacts(
                extracted_dict.get('testimonial_summary_text', ''))
        except Exception as e:
            # This handles the JSONDecodeError (EOF) and Pydantic validation errors
            logger.error(
                f"Pydantic validation failed for Grounding output: {e}. Raw JSON: {json_str[:200]}..."
            )
            return empty_result

        # grounding metadata for sources
        sources = []
        if candidate.grounding_metadata:
            # Use getattr to safely check for 'attributions' attribute
            source_list_container = getattr(candidate.grounding_metadata,
                                            'attributions', None)

            if source_list_container:
                for attribution in source_list_container:
                    if attribution.web:
                        sources.append({
                            'url': attribution.web.uri,
                            'title': attribution.web.title,
                        })

        return extracted_dict, sources

    def generate_embedding(self, text_list: List[str]) -> List[List[float]]:
        """
        Generates text embeddings (vectors) for a list of texts using the 
        embed_content method of the Gen AI SDK.
        """
        if not text_list:
            return []

        try:
            response = self.client.models.embed_content(
                model=settings.EMBEDDING_MODEL_NAME,
                contents=text_list,  # contents argument takes a list of strings
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT",
                                                auto_truncate=True))

            # response object now contains the embeddings property
            embeddings = [p.values for p in response.embeddings]

            logger.info(f"Generated embeddings for {len(embeddings)} texts.")
            return embeddings

        except Exception as e:
            logger.error(f"Gemini Embeddings API call failed. Error: {e}")
            # Return a list of empty vectors equal to the number of input texts
            return [[0.0] * 768] * len(text_list)
