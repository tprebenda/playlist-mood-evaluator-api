from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = FastAPI()

# generated via cmd: 'openssl rand -hex 32'
SECRET_KEY = "c813fdf7e5026818638730c587e417dbe58168f0fa2a05300a3392ca7e04ee01"

origins = [
    "http://127.0.0.1",
    "https://127.0.0.1",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
]

# References for CORS + Session Middleware:
# https://www.starlette.io/middleware/#corsmiddleware
# https://stackoverflow.com/a/71131572/11972470
# https://stackoverflow.com/questions/73962743/fastapi-is-not-returning-cookies-to-react-frontend

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True,
    max_age=3600,  # 3600s = 1hr, the life of spotify access token
    same_site="none",
    domain="127.0.0.1"  # TODO: update to `.{exampleDomain}` when both frontend and backend are deployed on real servers
)

CLIENT_ID = "5b9ee404632b45f6a6d6cc35824554a6"
CLIENT_SECRET = "920902c5825344b4a9ebf76b4096db3a"
OAUTH_REDIRECT_URI = "http://127.0.0.1:3000/callback"
SCOPE = "playlist-read-private playlist-read-collaborative user-read-private user-read-email"

# Docs: https://spotipy.readthedocs.io/en/2.24.0/#module-spotipy.oauth2
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=OAUTH_REDIRECT_URI, scope=SCOPE)


class UserResponse(BaseModel):
    display_name: str


class PlaylistResponse(BaseModel):
    name: str
    id: str

@app.post("/spotify-auth", tags=["auth"], status_code=status.HTTP_204_NO_CONTENT)
def exchange_token(code: str, request: Request):
    # Exchanges token, with check_cache=False to ensure new users can be registered
    token_info = sp_oauth.get_access_token(code=code, check_cache=False)
    # print(token_info)
    # https://www.starlette.io/middleware/#sessionmiddleware
    # TODO: store whole 'token_info' or no?
    request.session["access_token"] = token_info["access_token"]
    request.session["refresh_token"] = token_info["refresh_token"]


@app.post("/logout", tags=["auth"], status_code=status.HTTP_204_NO_CONTENT)
def logout_session(
    request: Request,
):
    if not request.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found for given user",
        )
    request.session.clear()


# Retrives display name for current user
@app.get("/user", tags=["spotify account"], status_code=status.HTTP_200_OK)
def getUserDisplayName(request: Request) -> UserResponse:
    access_token = request.session.get("access_token", None)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Must authenticate through Spotify OAuth",
        )

    sp = spotipy.Spotify(auth=access_token)
    user = sp.current_user()
    return {"display_name": user["display_name"]}


# Retrieves all playlist names and their corresponding ID's for current user
@app.get("/playlists", tags=["spotify account"], status_code=status.HTTP_200_OK)
def getUserPlaylists(request: Request) -> list[PlaylistResponse]:
    access_token = request.session.get("access_token", None)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Must authenticate through Spotify OAuth",
        )

    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()["items"]

    formattedPlaylists = []
    for playlist in playlists:
        formattedPlaylists.append({"name": playlist["name"], "id": playlist["id"]})
    return formattedPlaylists

# Retrieves all playlist names and their corresponding ID's for current user
@app.get("/mood/{playlistId}", tags=["spotify account"], status_code=status.HTTP_200_OK)
async def getPlaylistMood(playlistId: str, request: Request):
    access_token = request.session.get("access_token", None)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Must authenticate through Spotify OAuth",
        )

    sp = spotipy.Spotify(auth=access_token)
    tracks_response = sp.playlist_tracks(playlistId)
    tracks = tracks_response["items"]
    while tracks_response["next"]:
        tracks_response = sp.next(tracks_response)
        tracks.extend(tracks_response["items"])

    track_ids = [track["track"]["id"] for track in tracks]
    audio_features = sp.audio_features(track_ids)
    danceability = []
    energy = []
    valence = []
    for track_features in audio_features:
        danceability.append(track_features["danceability"])
        energy.append(track_features["energy"])
        valence.append(track_features["valence"])

    print(danceability)
    print(energy)
    print(valence)
    # TODO: loop through all tracks (in batches of 100), add values for each
    # return mood
