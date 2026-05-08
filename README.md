# Spotify Mood Evaluator API

Backend API for Playlist Mood Evaluator frontend application. Analyzes Spotify playlists using audio features (danceability, energy, valence, etc.) to generate a mood description and surface the top tracks that contributed to it.

## Project Structure

```
app/
  config.py          # Environment variable configuration (pydantic-settings)
  constants.py       # Application constants
  models.py          # Pydantic models and response schemas
  routers/
    auth.py          # POST /spotify-auth, POST /logout
    playlists.py     # GET /playlists
    mood.py          # GET /mood/{playlist_id}
  services/
    spotify.py       # Spotify API helpers (batch audio features, track merging)
    mood.py          # Mood analysis logic
main.py              # FastAPI app entrypoint
```

## Environment Variables

Create a `.env` file or set these in your environment:

| Variable | Description |
|----------|-------------|
| `CLIENT_ID` | Spotify OAuth client ID |
| `CLIENT_SECRET` | Spotify OAuth client secret |
| `SESSION_SECRET_KEY` | Secret key for session middleware |
| `ALLOWED_ORIGIN` | CORS allowed origin (e.g. `https://playlistmoodevaluator.com`) |
| `APP_DOMAIN` | Cookie domain (e.g. `.playlistmoodevaluator.com`) |
| `OAUTH_REDIRECT_URI` | Spotify OAuth callback URL |
| `SPOTIFY_SCOPE` | Spotify permission scopes |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spotify-auth?code={code}` | Exchange OAuth code for session tokens |
| `POST` | `/logout` | Clear user session |
| `GET` | `/playlists` | List user's non-empty playlists |
| `GET` | `/mood/{playlist_id}` | Analyze playlist mood and return top tracks |

## Local Development

To spin up the API locally:

```bash
fastapi dev main.py
```

This will launch a Uvicorn server on `http://127.0.0.1:8000`.

API docs available at `http://127.0.0.1:8000/docs`.

## Deployment

To deploy changes to remote Fly.io server:

```bash
fly deploy
```
