import time

from more_itertools import chunked
from spotipy import Spotify
from spotipy.exceptions import SpotifyException

from app.models import AudioFeatureMap, TrackDetails

UNWANTED_TRACK_KEYS = (
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
)


def batch_retrieve_audio_features(track_ids: list[str], spotipy_client: Spotify) -> list[dict]:
    """Retrieves Spotify track audio features in batches of 100, accounting for rate limiting."""
    audio_features: list[dict] = []
    for chunk in chunked(track_ids, 100):
        while True:
            try:
                features = spotipy_client.audio_features(chunk)
                audio_features.extend(features)
                break
            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = int(e.headers.get("Retry-After", 5))
                    print(f"Rate limited. Retrying in {retry_after} seconds...")
                    time.sleep(retry_after)
                else:
                    raise Exception(f"Spotipy failed to retrieve audio features due to error: {e}")

    return audio_features


def extract_feature_maps(audio_features: list[dict]) -> dict[str, AudioFeatureMap]:
    """Groups raw audio feature dicts into per-feature maps of {track_id: value}."""
    feature_names = ["danceability", "energy", "valence", "acousticness", "instrumentalness", "speechiness"]
    feature_maps: dict[str, AudioFeatureMap] = {name: {} for name in feature_names}

    for track in audio_features:
        track_id = track["id"]
        for name in feature_names:
            feature_maps[name][track_id] = track[name]

    return feature_maps


def merge_track_details_and_audio_features(
    top_track_features: list[dict], top_track_details: list[dict]
) -> list[TrackDetails]:
    """Merges audio features with track details and strips unused Spotify API fields."""
    details_by_id = {track["id"]: track for track in top_track_details}
    merged: list[TrackDetails] = []

    for track_features in top_track_features:
        cleaned = {k: v for k, v in track_features.items() if k not in UNWANTED_TRACK_KEYS}
        track_details = details_by_id[cleaned["id"]]
        artists = ", ".join(artist["name"] for artist in track_details["artists"])

        merged.append(
            TrackDetails(
                **cleaned,
                name=track_details["name"],
                album=track_details["album"]["name"],
                artists=artists,
                url=track_details["external_urls"]["spotify"],
            )
        )

    return merged
