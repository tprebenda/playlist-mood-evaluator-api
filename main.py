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
    # Disabled for production deployment (uncomment for local dev):
    # "http://127.0.0.1",
    # "https://127.0.0.1",
    # "http://127.0.0.1:3000",
    # "https://127.0.0.1:3000",
    "https://playlistmoodevaluator.com",
    "https://playlistmoodevaluator.com:3000",
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
    # 3600s = 1hr, the life of spotify access token
    max_age=3600,
    same_site="none",
    # domain="127.0.0.1",  # LOCAL DEV
    domain=".playlistmoodevaluator.com",
)

CLIENT_ID = "5b9ee404632b45f6a6d6cc35824554a6"
CLIENT_SECRET = "920902c5825344b4a9ebf76b4096db3a"
# OAUTH_REDIRECT_URI = "http://127.0.0.1:3000/callback"  # LOCAL DEV
OAUTH_REDIRECT_URI = "https://playlistmoodevaluator.com/callback"
SCOPE = "playlist-read-private playlist-read-collaborative user-read-private user-read-email"

# Docs: https://spotipy.readthedocs.io/en/2.24.0/#module-spotipy.oauth2
sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=OAUTH_REDIRECT_URI, scope=SCOPE
)

UNWATED_TRACK_KEYS = (
    "analysis_url",
    "duration_ms",
    "key",
    "liveness",
    "loudness",
    "mode",
    "tempo",
    "time_signature",
    "track_href",
    "type",
    "uri",
    # TODO: remove ID as well?
)


class UserResponse(BaseModel):
    display_name: str


class PlaylistResponse(BaseModel):
    name: str
    id: str


class MoodResponse(BaseModel):
    mood: str
    top_features: list
    top_tracks: list


# TODO: HOW TO PROTECT THIS ENDPOINT??
# Performs OAuth token exchange using provided auth code from frontend, and creates user session
@app.post("/spotify-auth", tags=["auth"], status_code=status.HTTP_204_NO_CONTENT)
def exchange_token(code: str, request: Request):
    # Exchanges token, with check_cache=False to ensure new users can be registered
    token_info = sp_oauth.get_access_token(code=code, check_cache=False)
    # https://www.starlette.io/middleware/#sessionmiddleware
    # TODO: store whole 'token_info' or no?
    request.session["access_token"] = token_info["access_token"]
    request.session["refresh_token"] = token_info["refresh_token"]


# Logs out of user session
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


# Retrieves all playlist names and their corresponding ID's
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


# Generates mood for given playlist, and returns top songs that contributed to this mood rating
@app.get("/mood/{playlistId}", tags=["spotify account"], status_code=status.HTTP_200_OK)
async def getPlaylistMood(playlistId: str, request: Request) -> MoodResponse:
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

    # TODO: loop in batches of 100
    track_ids = [track["track"]["id"] for track in tracks][:100]
    audio_features = sp.audio_features(track_ids)
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
    # print(averages)

    top_three_features = filter_and_sort_averages(all_averages, 3)
    mood = weigh_averages_for_mood(top_three_features, **all_averages)
    print(f"Mood: {mood}")

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

    top_audio_features = sp.audio_features(top_track_ids)
    top_track_details = sp.tracks(top_track_ids)["tracks"]
    top_tracks = merge_track_details_and_audio_features(top_audio_features, top_track_details)

    # print(top_tracks)
    return {
        "mood": mood,
        "top_features": list(top_feature_categories),
        "top_tracks": top_tracks,
    }


def get_avg_for_audio_feature(feature: dict[str, float]) -> float:
    feature_values = feature.values()
    return sum(feature_values) / len(feature_values)


# Filter out averages under 0.45, return top (len) entries
def filter_and_sort_averages(d: dict[str, str], len: int) -> dict[str, str]:
    filtered_top_songs = {key: avg for (key, avg) in d.items() if avg >= 0.45}
    return dict(sorted(filtered_top_songs.items(), key=lambda x: x[1], reverse=True)[:len])


# Uses Spotify Audio Features to determine the general mood for the playlist
# Docs:
# https://developer.spotify.com/documentation/web-api/reference/get-several-audio-features
def weigh_averages_for_mood(
    top_features: dict[str, float],
    danceability: float,
    energy: float,
    valence: float,
    instrumentalness: float,
    acousticness: float,
    speechiness: float,
):
    mood_evals = []
    top_feature_categories = top_features.keys()
    for feature, feature_avg in top_features.items():
        mood_info = ""
        if feature_avg >= 0.75:
            mood_info += "very "
        match feature:
            case "danceability":
                # EDM
                if acousticness < 0.4:
                    mood_info += "bass-heavy, rhythmic"
                # Rap
                elif speechiness > 0.33 and speechiness < 0.66:
                    mood_info += "hip-hop/rap"
                else:
                    mood_info += "lively, rhythmic"
                mood_evals.append(mood_info)
            case "energy":
                # Heavy metal
                if "instrumentalness" in top_feature_categories and valence < 0.5:
                    mood_info += "dark, heavy"
                # Jazz
                elif "instrumentalness" in top_feature_categories and valence >= 0.5:
                    mood_info += "jazzy, vibrant"
                else:
                    mood_info += "high intensity, energetic"
                mood_evals.append(mood_info)
            case "instrumentalness":
                # already handled (above), so skip
                if "energy" in top_feature_categories:
                    continue
                # Joyous orchestral
                if energy < 0.5 and valence > 0.5:
                    mood_info += "beautiful, orchestral"
                # Somber orchestral
                elif energy < 0.5 and valence < 0.5:
                    mood_info += "emotional, orchestral"
                # Chill guitar
                elif acousticness > 0.5:
                    mood_info += "chill, acoustic"
                mood_evals.append(mood_info)
            case "speechiness":
                # Podcasts/talk shows
                if speechiness > 0.66:
                    mood_info += "talkative, informative"
                mood_evals.append(mood_info)
            case "acousticness":
                # already handled (above), so skip
                if "instrumentalness" in top_feature_categories:
                    continue
                # Sad accoustic
                if valence < 0.5:
                    mood_info += "beautiful, sentimental"
                # Country
                else:
                    mood_info += "balladic, folk"
                mood_evals.append(mood_info)
            case "valence":
                # already handled by other categories
                continue
            case _:
                raise Exception(f"Invalid audio feature found: {feature}")

    if len(mood_evals) == 1:
        return f"A {mood_evals[0]} playlist."
    if len(mood_evals) == 2:
        return f"A {mood_evals[0]} playlist with {mood_evals[1]} elements."
    if len(mood_evals) == 3:
        return (
            f"A {mood_evals[0]} playlist, that also has {mood_evals[1]} "
            f"and {mood_evals[2]} elements."
        )


# Merges audio features (valence, energy, etc) with track details (song name, artist name, etc)
# Also removes keys that are returned from Spotify API but not used
def merge_track_details_and_audio_features(
    top_track_features: list[dict], top_track_details: list[dict]
) -> list[dict]:
    top_tracks_merged = []
    for track_features in top_track_features:
        cleaned_track = track_features
        # trim payload by removing unneeded keys
        for key in UNWATED_TRACK_KEYS:
            cleaned_track.pop(key, None)
        track_id = track_features["id"]
        # https://stackoverflow.com/a/25373204/11972470
        track_details = list(filter(lambda track: track["id"] == track_id, top_track_details)).pop()
        track_name = track_details["name"]
        track_album = track_details["album"]["name"]
        artists = []
        for artist_details in track_details["artists"]:
            artists.append(artist_details["name"])
        track_url = track_details["external_urls"]["spotify"]
        cleaned_track["name"] = track_name
        cleaned_track["album"] = track_album
        cleaned_track["artists"] = ", ".join(artists)
        cleaned_track["url"] = track_url
        top_tracks_merged.append(cleaned_track)

    return top_tracks_merged
