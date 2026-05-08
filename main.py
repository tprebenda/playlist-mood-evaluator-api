from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_auth_settings
from app.routers import auth, mood, playlists

app = FastAPI()

settings = get_auth_settings()

# References for CORS + Session Middleware:
# https://www.starlette.io/middleware/#corsmiddleware
# https://stackoverflow.com/a/71131572/11972470
# https://stackoverflow.com/questions/73962743/fastapi-is-not-returning-cookies-to-react-frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=True,
    max_age=3600,  # 1hr, the life of Spotify access token
    same_site="strict",
    domain=settings.app_domain,
)

app.include_router(auth.router)
app.include_router(playlists.router)
app.include_router(mood.router)
