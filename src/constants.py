COLORS = {
    "bg": "#0B0F17",
    "panel": "#111827",
    "panel_2": "#182235",
    "panel_3": "#202B3F",
    "preview": "#05070B",

    "text": "#F8FAFC",
    "text1": "#F8FAFC",
    "muted": "#94A3B8",
    "muted_2": "#64748B",

    "accent": "#6D7DFF",
    "accent_hover": "#8491FF",
    "accent_soft": "#202A66",

    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#EF4444",

    "border": "#263244",
    "border_soft": "#1E293B",

    "chip": "#1E293B",
    "chip_hover": "#273449",
    "disabled_tile": "#0F172A",

    "toast_bg": "#182235",
    "toast_error_bg": "#2A1620",
    "toast_warning_bg": "#2A2112",
    "toast_border": "#334155",
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