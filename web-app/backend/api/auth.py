from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional
import datetime

from models.AuthType import LoginRequest, TokenResponse, SimpleTokenResponse, TokenData, User, LoginData
from services.auth.jwt import generate_jwt_token, get_token_data

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    # This will be handled by the auth service
    from services.auth.auth import authenticate_user

    if not request.user_id or not request.password:
        raise HTTPException(status_code=400, detail="Missing user_id or password")

    # Authenticate user
    if authenticate_user(request.user_id, request.password):
        token = generate_jwt_token(request.user_id)

        # Create user object (in a real app, this would come from database)
        user = User(id=1, username=request.user_id)

        # Create the response data
        login_data = LoginData(token=token, user=user)

        return TokenResponse(
            data=login_data,
            status="success",
            message="Login successful"
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid user_id or password")

@router.post("/refresh", response_model=SimpleTokenResponse)
async def refresh_token(token_data: TokenData = Depends(get_token_data)):
    """Refresh an existing JWT token"""
    from services.auth.auth import refresh_user_token

    # Refresh the token
    new_token = refresh_user_token(token_data)
    if new_token:
        return {"token": new_token}
    else:
        raise HTTPException(status_code=403, detail="Token is no longer secure")
