from fastapi import APIRouter


from app.api._router_factory import ClientConfig, register_client

router = APIRouter()


from app.adapters import client_a
register_client(
    router=router,
    config=ClientConfig(
        request_model=client_a.ClientRequest,
        adapter=client_a,  # the module exposes parse_request + format_response
        endpoint="/schedule",
    ),
)
