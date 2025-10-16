from app.models.schemas import DoctorHit

MOCK = DoctorHit(npi="1234567890",
          name="Dr. Mock Specialist",
          specialties=["Orthopedic Surgery", "Sports Medicine"],
          metro="nyc",
          distance_km=4.2,
          in_network=True,
          reputation_score=0.95,
          factors={
              "Experience": 25.0,
              "Network": 30.0
          },
          citations=["PubMed(2023)", "Hospital Profile"],
          education=[
              "NYU School of Medicine",
              "Hospital for Special Surgery Residency"
          ],
          hospitals=["NYU Langone", "Mount Sinai"])

# Define the structure for the tool call
def calculate_recommendation_score(
        doctors: list[dict],  # List of dicts containing the 30 doctor profiles
        insurance_weight: float = 0.0,
        hospital_weight: float = 0.0,
        specialty_weight: float = 0.0,
        review_weight: float = 0.0) -> list[dict]:
    """
    Calculates a final personalized score for a list of doctors based on
    dynamically provided user preference weights.
    """
    # 1. Normalize weights if necessary (sum to 1.0)
    # 2. Implement the scoring logic (e.g., Final_Score = w1*feature1 + w2*feature2 + ...)
    #    (This logic MUST be robust and purely deterministic Python code.)

    # Example: score based on average rating and hospital tier
    for doc in doctors:
        doc['final_score'] = (
            (doc.get('ratings_avg', 0) * review_weight) +
            (doc.get('hospital_tier', 0) * hospital_weight) +
            (doc.get('semantic_similarity', 0) * specialty_weight
             )  # Use semantic similarity as a feature
        )

    # 3. Sort and return the top 3
    doctors.sort(key=lambda x: x['final_score'], reverse=True)
    return doctors[:3]


def rank_candidates(req):
    return M
