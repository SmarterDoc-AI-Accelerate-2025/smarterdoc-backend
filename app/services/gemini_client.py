import json
import time
from typing import List, Dict, Any, Tuple, Callable
import re
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from app.services.ranker import DynamicRankingWeights
from app.config import settings
from app.util.logging import logger
from app.models.schemas import FinalRecommendationList


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

    text = re.sub(r'\[INDEX\s+\d+(?:,\s*\d+)*\]',
                  '',
                  text,
                  flags=re.IGNORECASE)

    text = re.sub(r'INDEX_\d+', '', text, flags=re.IGNORECASE)

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
        self.EMBEDDING_DIMENSION = 3072

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

    def generate_embedding(
            self,
            text_list: List[str],
            task_type="RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """
        Generates text embeddings (vectors) for a list of texts using the 
        embed_content method of the Gen AI SDK.
        This is for dense embeddings.
        """
        if not text_list:
            return []

        try:
            response = self.client.models.embed_content(
                model=settings.EMBEDDING_MODEL_NAME,
                contents=text_list,  # contents argument takes a list of strings
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    auto_truncate=True,
                    output_dimensionality=self.EMBEDDING_DIMENSION))

            # response object now contains the embeddings property
            embeddings = [p.values for p in response.embeddings]

            logger.info(f"Generated embeddings for {len(embeddings)} texts.")
            return embeddings

        except Exception as e:
            logger.error(f"Gemini Embeddings API call failed. Error: {e}")
            # Return a list of empty vectors equal to the number of input texts
            return [[0.0] * self.EMBEDDING_DIMENSION] * len(text_list)

    def generate_dense_embedding_single(self, text: str) -> List[float]:
        """
        Generates a single dense embedding vector for a query text by calling 
        the batch method and extracting the single result.
        """
        if not text:
            return [0.0] * self.EMBEDDING_DIMENSION

        # 1. Call the batch method: Returns List[List[float]]
        list_of_vectors = self.generate_embedding([text],
                                                  task_type="RETRIEVAL_QUERY")

        # 2. Extract the single inner list: Returns List[float]
        if list_of_vectors and isinstance(list_of_vectors[0], list):
            # Successfully extracted the single vector
            return list_of_vectors[0]

        # Handle unexpected empty or malformed result
        return [0.0] * self.EMBEDDING_DIMENSION

    async def generate_content_with_tool(
            self,
            prompt: str,
            tool:
        Callable,  # The Python function to be called (e.g., calculate_ranking_weights)
            tool_name: str,
            initial_context: str = "") -> Dict[str, Any]:
        """
        Uses the Gemini model to analyze a prompt, generate parameters for a 
        specific tool, execute the tool, and return the result.
        
        For simplicity, this implementation assumes the LLM call 
        is the single step required.
        """

        tool_config = [types.Tool.from_function(tool)]

        # 1. First Call: Ask the LLM to determine the tool arguments (weights)

        # The prompt guides the LLM to use the tool
        system_instruction = (
            "You are an expert personalized recommendation agent. "
            "Analyze the user query below and determine the numeric weights (0.0 to 1.0) "
            "that reflect the user's explicit priorities. You MUST call the "
            f"'{tool_name}' function with the appropriate weights. Do NOT output text first. Ignore insurance for now, assume all doctors accept all insurance."
            "General Guidelines: - Assign higher weights to semantic_score, reputation_rating, and experience_years in general if "
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tool_config,
            temperature=
            0.0  # Keep this low for deterministic tool-argument output
        )

        response = self._call_gemini_api(
            f"User Query: {prompt}\nContext: {initial_context}", config)

        # Check for tool call in the response
        if (response is None or not response.candidates
                or not response.candidates[0].function_calls):
            logger.warning(
                "LLM failed to call the ranking tool. Using default weights.")
            return {
                "tool_output": tool(**DynamicRankingWeights().model_dump())
            }  # Use default weights

        # 2. Execute the Tool (Weight Generation)
        function_call = response.candidates[0].function_calls[0]
        args = dict(function_call.args)

        logger.info(f"LLM determined dynamic weights: {args}")

        # The tool output will be the list of Top 3 Doctors with scores
        tool_output = tool(**args)

        return {"tool_output": tool_output}

    def generate_text(self, prompt: str) -> str:
        # Simple text generation method for the final justification (Stage 4)
        config = types.GenerateContentConfig(temperature=0.7)
        response = self._call_gemini_api(prompt, config)

        if response and response.candidates:
            return response.candidates[0].content.parts[0].text
        return "Could not generate a full recommendation summary."

    def generate_structured_data(self, prompt: str, schema: Dict[str,
                                                                 Any]) -> str:
        """
        Generates content structured according to a JSON schema.
        """
        system_instruction = (
            "You are a structured data engine. Your sole task is to analyze the context "
            "and output a single, valid JSON object that strictly adheres to the provided schema. "
            "Do not include any preambles or explanations outside the JSON block."
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0)

        response = self._call_gemini_api(prompt, config)

        if response is None or not response.candidates:
            return json.dumps({"recommendations": []})

        json_str = response.candidates[0].content.parts[0].text.strip()

        # Optional: Add error handling/cleanup like _clean_llm_artifacts(json_str) here

        return json_str
