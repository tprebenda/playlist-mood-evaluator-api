import os
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from index import PlaylistResponse, MoodResponse, EMPTY_MOOD_RESPONSE
from utils import (
    batch_retrieve_audio_features,
    filter_and_sort_averages,
    get_avg_for_audio_feature,
    merge_track_details_and_audio_features,
    weigh_averages_for_mood,
)

app = FastAPI()


CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
SESSION_SECRET_KEY = os.environ["SESSION_SECRET_KEY"]

ALLOWED_ORIGIN = os.environ["ALLOWED_ORIGIN"]
APP_DOMAIN = os.environ["APP_DOMAIN"]
OAUTH_REDIRECT_URI = os.environ["OAUTH_REDIRECT_URI"]
SPOTIFY_SCOPE = os.environ["SPOTIFY_SCOPE"]


# References for CORS + Session Middleware:
# https://www.starlette.io/middleware/#corsmiddleware
# https://stackoverflow.com/a/71131572/11972470
# https://stackoverflow.com/questions/73962743/fastapi-is-not-returning-cookies-to-react-frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    https_only=True,
    max_age=3600,  # 1hr, the life of Spotify access token
    same_site="strict",
    domain=APP_DOMAIN,
)

# TODO: extract to auth script??
# Docs: https://spotipy.readthedocs.io/en/2.24.0/#module-spotipy.oauth2
sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=OAUTH_REDIRECT_URI, scope=SPOTIFY_SCOPE
)


# Performs OAuth token exchange using provided auth code from frontend, and creates user session
@app.post("/spotify-auth", tags=["auth"], status_code=status.HTTP_204_NO_CONTENT)
def exchange_token(code: str, request: Request):
    # Exchanges token, with check_cache=False to ensure new users can be registered
    token_info = sp_oauth.get_access_token(code=code, check_cache=False)
    # https://www.starlette.io/middleware/#sessionmiddleware
    # TODO: store whole 'token_info' or no?
    request.session["access_token"] = token_info["access_token"]
    request.session["refresh_token"] = token_info["refresh_token"]


# Dependency to validate user session for API requests
def get_access_token_from_session(request: Request) -> str:
    session = request.session
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session")

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access/refresh token in session"
        )

    return access_token


# Logs out of user session
@app.post("/logout", tags=["auth"], status_code=status.HTTP_204_NO_CONTENT)
def logout_session(request: Request) -> None:
    if not request.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found for given user",
        )
    request.session.clear()


# Retrieves all playlist names and their corresponding ID's
@app.get("/playlists", tags=["spotify account"], status_code=status.HTTP_200_OK)
def getUserPlaylists(
    request: Request, access_token: str = Depends(get_access_token_from_session)
) -> list[PlaylistResponse]:
    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()["items"]

    return [
        {"name": playlist["name"], "id": playlist["id"]}
        for playlist in playlists
        if playlist["tracks"]["total"] > 0
    ]


# Generates mood for given playlist, and returns top songs that contributed to this mood rating
@app.get("/mood/{playlistId}", tags=["spotify account"], status_code=status.HTTP_200_OK)
async def getPlaylistMood(
    playlistId: str, request: Request, access_token: str = Depends(get_access_token_from_session)
) -> MoodResponse:
    access_token = request.session.get("access_token")
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

    # Skip invalid tracks, or locally uploaded tracks to prevent Spotipy error:
    # https://github.com/spotipy-dev/spotipy/issues/1156
    track_ids = [
        track["track"]["id"]
        for track in tracks
        if track["track"] and track["track"]["id"] and not track["is_local"]
    ]
    if not track_ids:
        return EMPTY_MOOD_RESPONSE

    audio_features = batch_retrieve_audio_features(track_ids=track_ids, spotipy_client=sp)
    (
        danceability,
        energy,
        valence,
        acousticness,
        instrumentalness,
        speechiness,
    ) = (
        {},
        {},
        {},
        {},
        {},
        {},
    )

    for track_features in audio_features:
        track_id = track_features["id"]
        danceability[track_id] = track_features["danceability"]
        energy[track_id] = track_features["energy"]
        valence[track_id] = track_features["valence"]
        instrumentalness[track_id] = track_features["instrumentalness"]
        acousticness[track_id] = track_features["acousticness"]
        speechiness[track_id] = track_features["speechiness"]

    all_averages = {
        "danceability": get_avg_for_audio_feature(danceability),
        "energy": get_avg_for_audio_feature(energy),
        "valence": get_avg_for_audio_feature(valence),
        "instrumentalness": get_avg_for_audio_feature(instrumentalness),
        "acousticness": get_avg_for_audio_feature(acousticness),
        "speechiness": get_avg_for_audio_feature(speechiness),
    }

    top_three_features = filter_and_sort_averages(all_averages, 3)
    mood = weigh_averages_for_mood(top_three_features, **all_averages)

    # get top 20 songs for each category in top features
    top_track_ids = set()
    top_feature_categories = top_three_features.keys()
    for feature in top_feature_categories:
        match feature:
            case "danceability":
                top_danceable_songs = filter_and_sort_averages(danceability, 20)
                top_track_ids.update(list(top_danceable_songs.keys()))
            case "energy":
                top_energy_songs = filter_and_sort_averages(energy, 20)
                top_track_ids.update(list(top_energy_songs.keys()))
            case "valence":
                top_valence_songs = filter_and_sort_averages(valence, 20)
                top_track_ids.update(list(top_valence_songs.keys()))
            case "instrumentalness":
                top_instrumental_songs = filter_and_sort_averages(instrumentalness, 20)
                top_track_ids.update(list(top_instrumental_songs.keys()))
            case "acousticness":
                top_acoustic_songs = filter_and_sort_averages(acousticness, 20)
                top_track_ids.update(list(top_acoustic_songs.keys()))
            case "speechiness":
                top_speech_songs = filter_and_sort_averages(speechiness, 20)
                top_track_ids.update(list(top_speech_songs.keys()))
            case _:
                raise Exception(f"Invalid audio feature found: {feature}")

    top_track_details = sp.tracks(top_track_ids)["tracks"]
    top_audio_features = [track for track in audio_features if track["id"] in top_track_ids]
    top_tracks = merge_track_details_and_audio_features(top_audio_features, top_track_details)

    return {
        "mood": mood,
        "top_features": list(top_feature_categories),
        "top_tracks": top_tracks,
    }
