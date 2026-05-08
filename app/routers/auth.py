from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, status
from spotipy.oauth2 import SpotifyOAuth

from app.config import get_auth_settings

router = APIRouter(tags=["auth"])


def get_access_token_from_session(request: Request) -> str:
    """FastAPI dependency that validates the user session and extracts the access token."""
    session = request.session
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session")

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access/refresh token in session",
        )

    return access_token


@lru_cache
def _get_sp_oauth() -> SpotifyOAuth:
    """Cached SpotifyOAuth instance shared across requests."""
    settings = get_auth_settings()
    # https://spotipy.readthedocs.io/en/2.24.0/#module-spotipy.oauth2
    return SpotifyOAuth(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uri=settings.oauth_redirect_uri,
        scope=settings.spotify_scope,
    )


@router.post("/spotify-auth", status_code=status.HTTP_204_NO_CONTENT)
def exchange_token(code: str, request: Request):
    sp_oauth = _get_sp_oauth()
    token_info = sp_oauth.get_access_token(code=code, check_cache=False)
    request.session["access_token"] = token_info["access_token"]
    request.session["refresh_token"] = token_info["refresh_token"]


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_session(request: Request) -> None:
    if not request.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found for given user",
        )
    request.session.clear()
