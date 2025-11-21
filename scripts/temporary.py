# This script will hold all the temporary variables, lists, maps, and tables.

is_recording = False
recording_start_time = None

# Predefined lists for configuration options
bitrates = ["2M", "5M", "10M", "20M", "50M"]

nvenc_presets = ["fast", "medium", "slow", "hq", "bd", "ll", "llhq", "llhp"]

resolutions = [
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 720},
    {"width": 854, "height": 480},
]

codecs = [
    "libx264",
    "h264_nvenc", # NVIDIA's hardware-accelerated H.264 encoder
    "hevc_nvenc", # NVIDIA's hardware-accelerated H.265 (HEVC) encoder
    "mpeg4",
]
