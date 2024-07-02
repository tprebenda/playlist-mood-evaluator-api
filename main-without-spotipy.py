import base64
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import secrets
import requests
import urllib

app = FastAPI()

# generated via cmd: 'openssl rand -hex 32'
SECRET_KEY = "c813fdf7e5026818638730c587e417dbe58168f0fa2a05300a3392ca7e04ee01"

origins = [
    "http://localhost",
    "https://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "https://accounts.spotify.com",  # TODO: remove?
]

# https://www.starlette.io/middleware/#corsmiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # allow_headers=["Access-Control-Allow-Headers", 'Content-Type', 'Authorization', 'Access-Control-Allow-Origin'],
)

# https://www.starlette.io/middleware/#sessionmiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True,
    max_age=3600,  # 3600s = 1hr, the life of spotify access token
    same_site="none",  # TODO: remove? use "strict" when both API and UI are on same domain...?
)

CLIENT_ID = "5b9ee404632b45f6a6d6cc35824554a6"
CLIENT_SECRET = "920902c5825344b4a9ebf76b4096db3a"
OAUTH_REDIRECT_URI = "http://localhost:3000/callback"
SPOTIFY_TOKEN_ENDPOINT = "https://accounts.spotify.com/api/token"
SCOPE = "playlist-read-private playlist-read-collaborative user-read-private user-read-email"
STATE_KEY = "spotify_auth_state"

# TODO:
# - MAKE PYDANTIC MODEL FOR 'token_info' (returned from spotipy.get_access_token())

@app.get("/test-login", tags=["auth"])
async def authenticate_user(request: Request):
    state = secrets.token_hex(20)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "state": state,
    }
    response = RedirectResponse(
        url="https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    )
    response.set_cookie(key=STATE_KEY, value=state)
    return response


#  Helper function for generating request headers
def get_spotify_auth_headers():
    request_string = CLIENT_ID + ":" + CLIENT_SECRET
    encoded_bytes = base64.b64encode(request_string.encode("utf-8"))
    encoded_string = str(encoded_bytes, "utf-8")
    return {
        "Authorization": "Basic " + encoded_string,
        'content-type': 'application/x-www-form-urlencoded'
    }


@app.post("/spotify-auth", tags=["auth"])
async def exchange_token(code: str, state: str, request: Request):
    if state is None or state != request.cookies.get(STATE_KEY):
        raise HTTPException(status_code=400, detail="State mismatch")

    header = get_spotify_auth_headers()

    form_data = {
        "code": code,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    api_response = requests.post(SPOTIFY_TOKEN_ENDPOINT, data=form_data, headers=header)
    print(api_response.text)
    print(api_response.status_code)

    if api_response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to exchange auth code for access token")

    data = api_response.json()
    token_info = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"]
    }
    request.session.update({"token_info": json.dumps(token_info)})
    print(f"access token retrieved: {token_info['access_token']}")
    return {"tokenSaved": True}


@app.post("/logout", tags=["auth"])
async def logout_session(
    request: Request,
):
    request.session.clear()
    return {"success": True}
