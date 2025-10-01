from fastapi import APIRouter
from ...models.schemas import BookRequest, BookResponse
from ...services.telephony import initiate_call

router = APIRouter()


# TODO: implement appointment assistant
@router.post("/book", response_model=BookResponse)
def book(req: BookRequest):
    ok, msg = initiate_call(req)
    return BookResponse(status=("initiated" if ok else "failed"), message=msg)
