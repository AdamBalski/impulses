import fastapi
from src import state

def raise_unauthenticated():
    raise fastapi.HTTPException(status_code = 401, detail = "Invalidity or lack of token")

async def check_token(x_token: str = fastapi.Header(),
                      state: state.AppState = fastapi.Depends(state.get_state)):
    if x_token != state.app_token:
        raise_unauthenticated()
        
