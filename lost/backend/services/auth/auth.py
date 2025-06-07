from typing import Optional
import datetime

from models.AuthType import TokenData

def authenticate_user(user_id: str, password: str) -> bool:
    """
    Authenticate a user with username and password.
    In a real application, this would check against a database.
    """
    # TODO: Replace with actual database authentication
    return user_id == 'a' and password == 'a'

def refresh_user_token(token_data: TokenData) -> Optional[str]:
    """
    Refresh a user's token if it's eligible for renewal.
    """
    from services.auth.jwt import generate_jwt_token

    # Check how long the token has been expired
    now = datetime.datetime.utcnow()
    exp = token_data.exp

    # Convert exp to UTC for comparison if it's not already
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=datetime.timezone.utc)

    time_since_expiry = now - exp.replace(tzinfo=None)

    # Allow refresh if token expired less than 1 hour ago
    if time_since_expiry <= datetime.timedelta(hours=1):
        return generate_jwt_token(token_data.user_id)
    else:
        return None
