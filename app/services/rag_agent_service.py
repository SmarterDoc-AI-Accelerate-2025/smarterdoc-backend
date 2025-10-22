from fastapi import HTTPException
from typing import List, Dict, Any
from app.services.vertex_vector_search_service import VertexVectorSearchService  # Stage 1
from app.services.gemini_client import GeminiClient  # LLM & Tool Orchestration
from app.services.ranker import generate_ranking_weights, apply_personalized_reranking  # Stage 3 Tool
from app.models.schemas import FinalRecommendedDoctor, FinalRecommendationList, Top3SelectionResult
from app.util.hospitals import HOSPITAL_TIERS
from app.util.med_schools import MED_SCHOOL_TIERS
from app.util.logging import logger


class RagAgentService:

    def __init__(self, vector_search_service, gemini_client: GeminiClient):
        self.vector_search_service = vector_search_service
        self.gemini_client = gemini_client
        self.weight_tool_name = 'generate_ranking_weights'

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

        return f"Ranking Rules: {hospital_context.strip()} | {education_context.strip()} | Dense Embedding Search for semantic similarity."

    async def get_recommended_doctors(
            self, request_data: Dict[str, Any]) -> List[Dict[str, Any]]:

        user_query = request_data.get('query', '')
        specialty_text = request_data.get('specialty', '')
        metadata_filters = None

        # Combine user_query and specialty_text for dense embedding search
        combined_query = f"{user_query} {specialty_text}".strip()

        # Generate dense embedding for the combined query
        dense_query_vector = self.gemini_client.generate_dense_embedding_single(
            combined_query)

        # 2. STAGE 1: Dense Embedding Search Retrieval (Fastest Latency, Top 30)
        # Call the new search_dense method on your VertexVectorSearchService
        candidates_30 = await self.vector_search_service.search_dense(
            dense_vector=dense_query_vector,
            k=30,
            metadata_filters=metadata_filters)

        if dense_query_vector is None:
            logger.error("Embedding generation failed and returned None.")
            # Fallback to empty list or raise a specific error
            raise HTTPException(status_code=503,
                                detail="Embedding Service Failed.")
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
        logger.info(f"=======Agent weights: {weights}")
        # 3. STAGE 3: Personalized Reranking (Python Logic)

        # Apply the LLM-generated weights to the actual doctor data
        scored_candidates = apply_personalized_reranking(
            candidates=candidates_30, weights=weights)
        # top_3_doctors = apply_personalized_reranking(candidates=candidates_30,
        #                                              weights=weights)
        logger.info(f"=======Agent scored candidates: {scored_candidates[:3]}")

        # Grounding prompt for the LLM to explain its selection
        justification_prompt = f"""
            You are the final decision-maker. Your task is to select the absolute Top 3 best doctors 
            from the candidates provided below. Use the 'final_weighted_score' as a strong guide, 
            but also use the doctors' BIO and SUMMARY fields to ensure the choice is compassionate, 
            nuanced, and justified. The decision must consider the user query (user may specifically ask for certain qualities)
            pay attention to technical medical conditions or keywords in the query.
            
            For EACH of the final Top 3 selected, provide a justification 
            explaining WHY they were chosen (e.g., "Chosen due to high score AND testimonial summary 
            praising bedside manner for complex cases").
            
            CANDIDATES (Scored, Top 30): {scored_candidates}
            User's Original Query: {user_query}
            
            FORMAT REQUIREMENT:
             Return ONLY the Top 3 NPIs with their reasoning. Each object should contain:
             - npi: the doctor's NPI
             - agent_reasoning_summary: your justification for why this doctor was selected
            """
        top_3_selection_json_str = self.gemini_client.generate_structured_data(
            prompt=justification_prompt, schema=Top3SelectionResult)

        # Parse the JSON string into Python objects
        try:
            result = Top3SelectionResult.model_validate_json(
                top_3_selection_json_str)
            top_3_selections = [
                selection.model_dump() for selection in result.top_3_selections
            ]
            logger.info(
                f"=====DEBUG CHECK: Top 3 NPI selections: {top_3_selections}"
            )
        except Exception as e:
            logger.error(f"Failed to parse Top 3 selection JSON: {e}")
            top_3_selections = []

        # Extract NPIs and reasoning from top 3 selections
        top_3_npis = [selection.get('npi') for selection in top_3_selections]
        top_3_reasoning = {selection.get('npi'): selection.get('agent_reasoning_summary', '') 
                          for selection in top_3_selections}
        
        logger.info(f"===== Top 3 NPIs: {top_3_npis}")
        logger.info(f"===== Top 3 reasoning: {top_3_reasoning}")

        # Filter out top 3 from the rest of candidates
        top_3_npis_set = set(top_3_npis)
        rest_27_filtered = list(
            filter(lambda x: x.get('npi') not in top_3_npis_set,
                   scored_candidates))
        
        logger.info(
            f"===== CHECK REST 27 FILTERED FIELDS, {list(rest_27_filtered[0].keys()) if rest_27_filtered else 'No rest candidates'}"
        )
        
        # Extract top 3 doctors from scored_candidates and add reasoning
        top_3_full_data = []
        if top_3_npis:
            # Find the top 3 doctors in scored_candidates by NPI
            for candidate in scored_candidates:
                if candidate.get('npi') in top_3_npis:
                    # Create a copy and add reasoning
                    doctor_with_reasoning = candidate.copy()
                    npi = doctor_with_reasoning.get('npi')
                    if npi in top_3_reasoning:
                        doctor_with_reasoning['agent_reasoning_summary'] = top_3_reasoning[npi]
                    top_3_full_data.append(doctor_with_reasoning)

        # Combine top 3 with reasoning and rest candidates
        final_result = top_3_full_data + rest_27_filtered
        
        logger.info(f"===== Final result: {len(final_result)} doctors (top 3 with reasoning + rest 27)")
        
        return final_result
