import time
from more_itertools import chunked
from index import AudioFeaturesObject, TrackDetails
from spotipy.exceptions import SpotifyException

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
)


# Retrieves Spotify track audio features in batches of 100, accounting for rate limiting
def batch_retrieve_audio_features(track_ids: list[str], spotipy_client) -> list[AudioFeaturesObject]:
    audio_features = []
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
                    # retry current batch (don't break out of while loop)
                else:
                    raise Exception("Spotipy failed to retrieve audio features due to error: {e}")

    return audio_features


# TODO: add pydantic model(s) for these mysterious dictionaries....
def get_avg_for_audio_feature(feature: dict[str, float]) -> float:
    feature_values = feature.values()
    return sum(feature_values) / len(feature_values)


# Filter out averages under 0.45, return top (len) entries
def filter_and_sort_averages(d: dict[str, float], len: int) -> dict[str, str]:
    filtered_top_songs = {feature: avg for (feature, avg) in d.items() if avg >= 0.45}
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
        return f"A {mood_evals[0]} playlist, that also has {mood_evals[1]} and {mood_evals[2]} elements."


# Merges audio features (valence, energy, etc) with track details (song name, artist name, etc)
# Also removes keys that are returned from Spotify API but not used
def merge_track_details_and_audio_features(
    top_track_features: list[dict], top_track_details: list[dict]
) -> list[TrackDetails]:
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
