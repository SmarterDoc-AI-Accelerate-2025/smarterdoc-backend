from ..models.schemas import BookRequest


def initiate_call(req: BookRequest) -> tuple[bool, str]:
    # Minimal stub: pretend it worked
    return True, f"Stubbed call for NPI {req.npi}"
