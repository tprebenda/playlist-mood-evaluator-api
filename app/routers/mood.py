from fastapi import APIRouter, Depends
import spotipy

from app.constants import EMPTY_MOOD_RESPONSE
from app.models import MoodResponse
from app.routers.auth import get_access_token_from_session
from app.services.mood import (
    collect_top_track_ids,
    filter_and_sort_averages,
    get_avg_for_audio_feature,
    weigh_averages_for_mood,
)
from app.services.spotify import (
    batch_retrieve_audio_features,
    extract_feature_maps,
    merge_track_details_and_audio_features,
)

router = APIRouter(tags=["mood"])


@router.get("/mood/{playlist_id}", status_code=200)
def get_playlist_mood(
    playlist_id: str,
    access_token: str = Depends(get_access_token_from_session),
) -> MoodResponse:
    sp = spotipy.Spotify(auth=access_token)

    tracks_response = sp.playlist_tracks(playlist_id)
    tracks = tracks_response["items"]
    while tracks_response["next"]:
        tracks_response = sp.next(tracks_response)
        tracks.extend(tracks_response["items"])

    # Skip invalid or locally uploaded tracks to prevent Spotipy error:
    # https://github.com/spotipy-dev/spotipy/issues/1156
    track_ids = [
        track["track"]["id"]
        for track in tracks
        if track["track"] and track["track"]["id"] and not track["is_local"]
    ]
    if not track_ids:
        return EMPTY_MOOD_RESPONSE

    audio_features = batch_retrieve_audio_features(track_ids=track_ids, spotipy_client=sp)
    feature_maps = extract_feature_maps(audio_features)

    all_averages = {name: get_avg_for_audio_feature(fmap) for name, fmap in feature_maps.items()}

    top_three_features = filter_and_sort_averages(all_averages, 3)
    mood = weigh_averages_for_mood(top_three_features, **all_averages)

    top_track_ids = collect_top_track_ids(list(top_three_features.keys()), feature_maps)

    top_track_details = sp.tracks(list(top_track_ids))["tracks"]
    top_audio_features = [t for t in audio_features if t["id"] in top_track_ids]
    top_tracks = merge_track_details_and_audio_features(top_audio_features, top_track_details)

    return MoodResponse(
        mood=mood,
        top_features=list(top_three_features.keys()),
        top_tracks=top_tracks,
    )
