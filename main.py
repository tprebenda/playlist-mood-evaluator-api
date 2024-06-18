from fastapi import FastAPI
from pydantic import BaseModel
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
)

_API_BASE_URL = "https://api.spotify.com/v1"
_DEFAULT_SPOTIFY_USERNAME = "Spotify User"

@app.get("/whoami")
async def getUserId(auth_token: str) -> dict[str, str]:
    endpoint = f"{_API_BASE_URL}/me"
    headers = { "Authorization": f"Bearer {auth_token}" }
    r = requests.get(url=endpoint, headers=headers)
    print(r.status_code)
    if r.status_code != 200:
        print("USER ID RETRIEVAL error")
        return ""
    
    json_response = r.json()
    display_name = json_response['display_name'] or _DEFAULT_SPOTIFY_USERNAME
    id = json_response['id']
    print(json_response)
    return { 'display_name': display_name, 'id': id }


# class UserPlaylistRequest(BaseModel):
#     auth_token: str
#     user_id: str

# Retrievals all playlist names and their corresponding ID's, per `user_id` provided
@app.get("/playlists")
async def getUserPlaylists(auth_token: str, user_id: str) -> dict[str, str]:
    endpoint = f"{_API_BASE_URL}/users/{user_id}/playlists"
    headers = { "Authorization": f"Bearer {auth_token}" }
    r = requests.get(endpoint, headers=headers)
    
    if r.status_code != 200:
        print("PLAYLIST RETRIEVAL error")
        return []
    
    items = r.json()['items']
    d = {}
    for playlist in items:
        d[playlist['name']] = playlist['id']
    return d