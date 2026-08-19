from fastapi import APIRouter, Depends
from .auth_middleware import require_auth

router = APIRouter()

@router.get("/me", dependencies=[Depends(require_auth)])
def get_current_user():
    raise NotImplementedError
