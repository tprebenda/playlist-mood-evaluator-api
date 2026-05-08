from fastapi import APIRouter, Depends
import spotipy

from app.routers.auth import get_access_token_from_session
from app.models import PlaylistResponse

router = APIRouter(tags=["playlists"])


@router.get("/playlists", status_code=200)
def get_user_playlists(
    access_token: str = Depends(get_access_token_from_session),
) -> list[PlaylistResponse]:
    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()["items"]

    return [
        PlaylistResponse(name=playlist["name"], id=playlist["id"])
        for playlist in playlists
        if playlist["tracks"]["total"] > 0
    ]
