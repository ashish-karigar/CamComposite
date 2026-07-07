# constants.py
COLORS = {
    "bg": "#0f1115",
    "panel": "#171a21",
    "panel_2": "#1d212b",
    "text": "#f5f7fb",
    "text1": "#000000",
    "muted": "#a7b0c0",
    "accent": "#7C8CFF",
    "accent_hover": "#95a2ff",
    "border": "#262c38",
    "preview": "#0b0d12",
    "chip": "#222838",
    "disabled_tile": "#141821",
    "error": "#ff6b6b",
}

WINDOW = {
    "title": "CamComposite",
    "size": "1180x780",
}

VIDEO_PROFILES = {
    "low": {
        "label": "Low",
        "width": 1280,
        "height": 720,
        "fps": 24,
    },
    "balanced": {
        "label": "Balanced",
        "width": 1920,
        "height": 1080,
        "fps": 30,
    },
    "high": {
        "label": "High",
        "width": 1920,
        "height": 1080,
        "fps": 60,
    },
}

DEFAULT_VIDEO_PROFILE = "balanced"


def get_video_profile(profile_name=None):
    profile_name = profile_name or DEFAULT_VIDEO_PROFILE
    return VIDEO_PROFILES.get(profile_name, VIDEO_PROFILES[DEFAULT_VIDEO_PROFILE])