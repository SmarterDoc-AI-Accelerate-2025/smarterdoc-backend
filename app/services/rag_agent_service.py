from typing import List, Dict, Any
from app.services.sparse_client import SparseVectorizerClient
from app.services.vertex_vector_search_service import VertexVectorSearchService  # Stage 1
from app.services.gemini_client import GeminiClient  # LLM & Tool Orchestration
from app.services.ranker import generate_ranking_weights, apply_personalized_reranking  # Stage 3 Tool
from app.models.schemas import FinalRecommendedDoctor
from app.util.hospitals import HOSPITAL_TIERS
from app.util.med_schools import MED_SCHOOL_TIERS
from app.util.logging import logger

# reciprocal rank fusion for hybrid search
DEFAULT_RRF_ALPHA = 0.5


class RagAgentService:

    def __init__(self, vector_search_service, gemini_client: GeminiClient):
        self.vector_search_service = vector_search_service
        self.gemini_client = gemini_client
        self.weight_tool_name = 'generate_ranking_weights'
        self.sparse_client = SparseVectorizerClient()

    def _build_tier_context(self) -> str:
        """Creates a concise, structured context string for the LLM."""

        # 1. Hospital Context
        hospital_context = "Affiliated Hospitals Tiers: "
        for tier, hospitals in HOSPITAL_TIERS.items():
            hospital_context += f"{tier} includes {', '.join(hospitals[:3])} and others. "

        # 2. Education Context
        education_context = "Med School Tiers: "
        for tier, schools in MED_SCHOOL_TIERS.items():
            education_context += f"{tier} includes {', '.join(schools[:2])} and others. "

        return f"Ranking Rules: {hospital_context.strip()} | {education_context.strip()} | Hybrid Search (Alpha={DEFAULT_RRF_ALPHA} to blend semantic and keyword results)."

    async def get_recommended_doctors(
            self, request_data: Dict[str, Any]) -> List[Dict[str, Any]]:

        user_query = request_data.get('query', '')
        specialty_text = request_data.get('specialty', '')
        metadata_filters = None

        dense_query_vector = self.gemini_client.generate_dense_embedding_single(
            user_query)

        # Use the sparse client to generate the sparse vector data
        sparse_query_vector_data = self.sparse_client.get_sparse_embedding(
            specialty_text)

        # 2. STAGE 1: Hybrid Search Retrieval (Fastest Latency, Top 30)
        # Call the new search_hybrid method on your VertexLiveService
        candidates_30 = await self.vector_search_service.search_hybrid(
            dense_vector=dense_query_vector,
            sparse_vector_data=sparse_query_vector_data,
            k=30,
            rrf_alpha=DEFAULT_RRF_ALPHA,  # Blend factor
            metadata_filters=metadata_filters)

        if not candidates_30:
            return []

        # 2. LLM TOOL CALL: Generate Dynamic Weights

        # context
        ranking_rules_context = self._build_tier_context()

        # The LLM's goal is to analyze the query and call the Python tool with optimal weights
        # Note: The actual execution of the ranking logic is still in Python for speed.
        weight_generation_result = await self.gemini_client.generate_content_with_tool(
            prompt=user_query,
            tool=generate_ranking_weights,
            tool_name=self.weight_tool_name,
            initial_context=
            f"The filtered doctor list is ready. Use these ranking rules: {ranking_rules_context}"
        )

        weights = weight_generation_result.get(
            'tool_output')  # This is the Dict of weights

        # 3. STAGE 3: Personalized Reranking (Python Logic)

        # Apply the LLM-generated weights to the actual doctor data
        scored_candidates = apply_personalized_reranking(
            candidates=candidates_30, weights=weights)
        # top_3_doctors = apply_personalized_reranking(candidates=candidates_30,
        #                                              weights=weights)

        # 4. STAGE 4: RAG Generation (Synthesis & Justification)
        top_10_for_justification = scored_candidates[:10]
        # Grounding prompt for the LLM to explain its selection
        justification_prompt = f"""
            You are the final decision-maker. Your task is to select the absolute Top 3 best doctors 
            from the candidates provided below. Use the 'final_weighted_score' as a strong guide, 
            but also use the doctors' BIO and SUMMARY fields to ensure the choice is compassionate, 
            nuanced, and justified. The decision must consider the user query (user may specifically ask for certain qualities).
            
            For EACH of the final Top 3 selected, provide a justification 
            explaining WHY they were chosen (e.g., "Chosen due to high score AND testimonial summary 
            praising bedside manner for complex cases").
            
            CANDIDATES (Scored, Top 10): {top_10_for_justification}
            User's Original Query: {user_query}
            
            FORMAT REQUIREMENT:
            Return the final JSON list of the Top 3 doctors npis, ensuring each object contains 
            a new field: 'agent_reasoning_summary' with your justification.
            """
        justified_top_3_json_str = self.gemini_client.generate_structured_data(
            prompt=justification_prompt,
            schema=List[FinalRecommendedDoctor].model_json_schema(
            )  # Assuming schema is List of the full profile + reasoning
        )

        # Parse the JSON string into Python objects
        try:
            justified_top_3_doctors = FinalRecommendedDoctor.model_validate_json(
                justified_top_3_json_str).model_dump()

            if not isinstance(justified_top_3_doctors, list):
                logger.error(
                    "LLM Structured Output was not a list. Defaulting to empty list."
                )
                justified_top_3_doctors = []
        except Exception as e:
            logger.error(f"Failed to parse Top 3 JSON: {e}")
            justified_top_3_doctors = []

        # 6. FINAL RESPONSE ASSEMBLY

        # Extract NPIs of the justified Top 3 to identify the remaining 27
        top_3_npis = {doc.get('npi') for doc in justified_top_3_doctors}

        # Filter out the justified doctors from the original sorted list (27 candidates remaining)
        remaining_candidates = [
            doc for doc in scored_candidates
            if doc.get('npi') not in top_3_npis
        ]

        # Combine: Top 3 (with justification) + Remaining 27 (without justification)
        # Note: We append the remaining candidates to maintain the scored order
        final_ordered_recommendation_list = justified_top_3_doctors + remaining_candidates

        unordered_full_profiles = await self.fetch_full_profiles_by_npi(
            final_ordered_recommendation_list)

        # 4. Convert list of dicts to a dict for fast O(1) lookup by NPI
        # Ensure NPI is correctly cast to string if needed during key creation
        profile_map = {doc['npi']: doc for doc in unordered_full_profiles}

        # 5. Assemble the Final List in the Agent's Determined Order (length 30)
        final_ordered_doctors = []
        for npi in final_ordered_recommendation_list:
            if npi in profile_map:
                final_ordered_doctors.append(profile_map[npi])

        return final_ordered_doctors
