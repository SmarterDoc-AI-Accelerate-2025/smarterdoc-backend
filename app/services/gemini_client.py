# app/services/gemini_client.py

from google.cloud import aiplatform
from google.cloud.aiplatform import types as aiplatform_types
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Tuple  # ADDED Tuple for return type

from app.config import settings
from app.util.logging import logger
import json
import time

# pydantic schemas


class RatingRecord(BaseModel):
    """Schema for a single rating/review record."""
    source: str = Field(
        description="Name of the review platform. (e.g. ZocDoc)")
    score: float = Field(
        description="The numerical rating (e.g. 4.5/5.0, 5.0/5.0).")
    count: int = Field(
        description=
        "The total number of patient reviews counted from this source.")
    link: str = Field(description="URL to the original review page.")


class EnrichedProfileData(BaseModel):
    """The final structured data object to be extracted by the LLM."""
    years_experience: int = Field(
        description=
        "Total years of clinical practice since residency/fellowship completion, calculated by LLM."
    )
    profile_picture_url: str = Field(
        description=
        "Public URL found for the doctor's portrait or profile image.")
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


class GeminiClient:
    """
    Handles interactions with the Vertex AI Gemini API for structured extraction 
    and vector embeddings.
    """

    EMBEDDING_MODEL = "text-embedding-004"

    def __init__(self):
        """Initializes Vertex AI project and client settings."""
        aiplatform.init(project=settings.GCP_PROJECT_ID,
                        location=settings.GCP_REGION)
        self.llm_model = settings.GEMINI_MODEL

        # for embeddings
        self.prediction_client = aiplatform.services.PredictionServiceClient(
            client_options={
                "api_endpoint":
                f"{settings.GCP_REGION}-aiplatform.googleapis.com"
            })

    def _call_gemini_api(
            self, prompt_text: str,
            config: aiplatform_types.GenerateContentConfig) -> Any:
        try:
            model = aiplatform.preview.generative_models.GenerativeModel(
                model_name=self.llm_model)

            response = model.generate_content(
                contents=[prompt_text],
                config=config,
            )

            # successful response ends with "STOP"
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

        schema = EnrichedProfileData.model_json_schema()

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

        config = aiplatform_types.GenerateContentConfig(
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

        try:
            # Validate and convert the JSON string to a Python dictionary
            extracted_dict = EnrichedProfileData.model_validate_json(
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

        schema = EnrichedProfileData.model_json_schema()
        empty_result = {}, []

        config = aiplatform_types.GenerateContentConfig(
            # This enables Google Search grounding tool
            tools=[{
                "google_search": {}
            }],
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
        try:
            extracted_dict = EnrichedProfileData.model_validate_json(
                json_str).model_dump()
        except Exception as e:
            logger.error(
                f"Pydantic validation failed for Grounding output: {e}. Raw JSON: {json_str[:200]}..."
            )
            return empty_result

        # grounding metadata for sources
        sources = []
        if candidate.grounding_metadata and candidate.grounding_metadata.grounding_attributions:
            for attribution in candidate.grounding_metadata.grounding_attributions:
                if attribution.web:
                    sources.append({
                        'url': attribution.web.uri,
                        'title': attribution.web.title,
                    })

        return extracted_dict, sources

    def generate_embedding(self, text_list: List[str]) -> List[List[float]]:
        """
        Generates text embeddings (vectors) for a list of texts using the 
        gemini-embedding-001 model via the Prediction Service client.
        """
        if not text_list:
            return []

        # Prepare the instances payload for the PredictionServiceClient
        instances = [{
            "content": text,
            "task_type": "RETRIEVAL_DOCUMENT"
        } for text in text_list]

        endpoint = f"projects/{settings.GCP_PROJECT_ID}/locations/{settings.GCP_REGION}/publishers/google/models/{self.EMBEDDING_MODEL}"

        request_body = {
            "instances": instances,
            "parameters": {
                "autoTruncate": True
            }
        }

        try:
            response = self.prediction_client.predict(
                endpoint=endpoint,
                instances=request_body['instances'],
                parameters=request_body['parameters'])

            # get vector values from the predictions
            embeddings = []
            for prediction in response.predictions:
                # The prediction structure is nested: prediction['embeddings']['values']
                if 'embeddings' in prediction and 'values' in prediction[
                        'embeddings']:
                    embeddings.append(prediction['embeddings']['values'])
                else:
                    embeddings.append([0.0] * 768)  # Fallback vector size

            logger.info(f"Generated embeddings for {len(embeddings)} texts.")
            return embeddings

        except Exception as e:
            logger.error(f"Vertex AI Embeddings API call failed. Error: {e}")
            # Return a list of empty vectors equal to the number of input texts
            return [[0.0] * 768] * len(text_list)
