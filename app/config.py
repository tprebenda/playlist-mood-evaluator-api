from functools import lru_cache

from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    client_id: str
    client_secret: str
    session_secret_key: str
    allowed_origin: str
    app_domain: str
    oauth_redirect_uri: str
    spotify_scope: str


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
