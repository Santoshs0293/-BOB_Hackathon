from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.get("/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    return {"user": "demo_user", "scopes": ["read", "write"]}
