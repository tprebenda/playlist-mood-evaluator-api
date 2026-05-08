from app.models import AudioFeatureMap


def get_avg_for_audio_feature(feature_map: AudioFeatureMap) -> float:
    values = feature_map.values()
    return sum(values) / len(values)


def filter_and_sort_averages(d: dict[str, float], limit: int) -> dict[str, float]:
    """Filter out entries under 0.45 and return the top `limit` entries by value descending."""
    filtered = {k: v for k, v in d.items() if v >= 0.45}
    return dict(sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:limit])


def weigh_averages_for_mood(
    top_features: dict[str, float],
    danceability: float,
    energy: float,
    valence: float,
    instrumentalness: float,
    acousticness: float,
    speechiness: float,
) -> str:
    """
    Uses Spotify Audio Features to determine the general mood for the playlist.
    https://developer.spotify.com/documentation/web-api/reference/get-several-audio-features
    """
    mood_evals: list[str] = []
    top_feature_categories = top_features.keys()

    for feature, feature_avg in top_features.items():
        mood_info = ""
        if feature_avg >= 0.75:
            mood_info += "very "
        match feature:
            case "danceability":
                if acousticness < 0.4:
                    mood_info += "bass-heavy, rhythmic"
                elif 0.33 < speechiness < 0.66:
                    mood_info += "hip-hop/rap"
                else:
                    mood_info += "lively, rhythmic"
                mood_evals.append(mood_info)
            case "energy":
                if "instrumentalness" in top_feature_categories and valence < 0.5:
                    mood_info += "dark, heavy"
                elif "instrumentalness" in top_feature_categories and valence >= 0.5:
                    mood_info += "jazzy, vibrant"
                else:
                    mood_info += "high intensity, energetic"
                mood_evals.append(mood_info)
            case "instrumentalness":
                if "energy" in top_feature_categories:
                    continue
                if energy < 0.5 and valence > 0.5:
                    mood_info += "beautiful, orchestral"
                elif energy < 0.5 and valence < 0.5:
                    mood_info += "emotional, orchestral"
                elif acousticness > 0.5:
                    mood_info += "chill, acoustic"
                mood_evals.append(mood_info)
            case "speechiness":
                if speechiness > 0.66:
                    mood_info += "talkative, informative"
                mood_evals.append(mood_info)
            case "acousticness":
                if "instrumentalness" in top_feature_categories:
                    continue
                if valence < 0.5:
                    mood_info += "beautiful, sentimental"
                else:
                    mood_info += "balladic, folk"
                mood_evals.append(mood_info)
            case "valence":
                continue
            case _:
                raise ValueError(f"Invalid audio feature: {feature}")

    if len(mood_evals) == 1:
        return f"A {mood_evals[0]} playlist."
    if len(mood_evals) == 2:
        return f"A {mood_evals[0]} playlist with {mood_evals[1]} elements."
    if len(mood_evals) == 3:
        return f"A {mood_evals[0]} playlist, that also has {mood_evals[1]} and {mood_evals[2]} elements."

    return "A unique playlist."


def collect_top_track_ids(
    top_feature_categories: list[str],
    feature_maps: dict[str, AudioFeatureMap],
    limit: int = 20,
) -> set[str]:
    """Collects the top track IDs across the given feature categories."""
    top_track_ids: set[str] = set()
    for feature in top_feature_categories:
        top_songs = filter_and_sort_averages(feature_maps[feature], limit)
        top_track_ids.update(top_songs.keys())
    return top_track_ids
