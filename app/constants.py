from app.models import MoodResponse

EMPTY_MOOD_RESPONSE = MoodResponse(
    mood="No Mood (No Tracks Found). Playlist is either empty or a specialized playlist.",
    top_features=["none"],
    top_tracks=[],
)
