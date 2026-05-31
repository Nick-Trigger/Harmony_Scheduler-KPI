from fastapi import APIRouter

from app.adapters import client_a
from app.api._router_factory import RouterFactory


router = APIRouter()
RouterFactory(
    router=router,
    request_model=client_a.ClientRequest,
    adapter=client_a,
    endpoint="/schedule",
).create_schedule()