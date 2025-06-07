import jwt
import datetime
from typing import Optional
from fastapi import HTTPException, Header

from models.AuthType import TokenData
from config.settings import get_settings

# Get settings
settings = get_settings()

# Function to generate JWT token
def generate_jwt_token(user_id: str) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token if isinstance(token, str) else token.decode('utf-8')

# Dependency for JWT token verification
async def get_token_data(authorization: str = Header(None)) -> TokenData:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token is missing")

    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

        return TokenData(
            user_id=payload.get('user_id'),
            exp=datetime.datetime.fromtimestamp(payload.get('exp'))
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except (jwt.InvalidTokenError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        # Catch any other JWT-related errors
        raise HTTPException(status_code=401, detail="Invalid token")