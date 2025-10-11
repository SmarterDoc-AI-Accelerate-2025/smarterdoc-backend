import math
from ..models.schemas import RankRequest, DoctorHit
from .elastic_client import fetch_evidence_ids
from ..util.med_schools import top_tier1_med_schools, top_tier2_meds_schools, top_tier3_med_schools
from ..util.hospitals import us_tier1_specialty_hospitals, us_tier2_specialty_hospitals, us_tier3_specialty_hospitals

WEIGHTS = {
    "specialty_match": 30.0,
    "insurance": 25.0,  # in-network /out-of-network
    "experience": 20.0,
    "reputation": 15.0,
    "pub_recent": 10.0,
    "certification": 12.0,
    "affiliated_hospitals": 15.0,
    "education": 8.0
}


def insurance_score(in_network: bool | None, same_family: bool = False):
    if in_network: return 1.0
    if same_family: return 0.7
    return 0.0


def distance_score(km: float | None, cap: float = 80.0):
    if km is None: return 0.5
    return max(0.0, 1.0 - min(km, cap) / cap)


# TODO: discuss rank factors,
def rank_candidates(req: RankRequest, es=None) -> list[DoctorHit]:
    ranked: list[DoctorHit] = []
    for d in req.candidates:
        # TODO: replace placeholders with real features (from ES/BQ/metadata)
        spec = 1.0  # if specialty matches condition slug;
        ins = insurance_score(d.in_network, False)
        pub = min(10.0, (d.factors or {}).get("pub_recent", 0.0)) / 10.0
        years = (d.factors or {}).get("years_experience", 8)
        exp = math.log1p(years) / math.log(21)
        rep = (d.reputation_proxy or 0.0) / 15.0

        breakdown = {
            "specialty_match": WEIGHTS["specialty_match"] * spec,
            "insurance": WEIGHTS["insurance"] * ins,
            "pub_recent": WEIGHTS["pub_recent"] * pub,
            "experience": WEIGHTS["experience"] * exp,
            "certificaton": WEIGHTS["certification"],  # help me complete this 
            "reputation": WEIGHTS["reputation"] * rep,
            "affiliated_hospital":
            WEIGHTS["affiliated_hospitals"],  # help me complete this
            "education": WEIGHTS["education"]  #help me complete this
        }
        total = sum(breakdown.values())
        d.factors = (d.factors or {}) | breakdown | {"total": total}

        # Attach top evidence ids (can do later in controller)
        if es:
            try:
                d.citations = fetch_evidence_ids(es,
                                                 d.npi,
                                                 req.condition_slug,
                                                 limit=3)
            except Exception:
                d.citations = d.citations or []

        ranked.append(d)

    ranked.sort(key=lambda x: x.factors["total"], reverse=True)
    return ranked
