from pydantic import BaseModel
from typing import Literal


# ------ Response Schemas ------


class PlaylistResponse(BaseModel):
    name: str
    id: str


class TrackDetails(BaseModel):
    id: str
    name: str
    album: str
    artists: str
    url: str
    danceability: float
    energy: float
    speechiness: float
    acousticness: float
    instrumentalness: float
    valence: float


class MoodResponse(BaseModel):
    mood: str
    top_features: list[str]
    top_tracks: list[TrackDetails]


# ------ Spotify / Spotipy Types ------


# https://developer.spotify.com/documentation/web-api/reference/get-audio-features
class AudioFeaturesObject(BaseModel):
    id: str
    acousticness: float
    danceability: float
    duration_ms: float
    energy: float
    instrumentalness: float
    valence: float
    speechiness: float

    analysis_url: str
    key: int
    liveness: float
    loudness: float
    mode: int
    tempo: float
    time_signature: int
    track_href: str
    type: Literal["audio_features"]
    uri: str


# Maps track IDs to their audio feature scores (e.g. {"track_id": 0.85})
AudioFeatureMap = dict[str, float]
