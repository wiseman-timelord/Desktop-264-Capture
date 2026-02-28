# scripts/recorder.py
# Video : mss (DXGI Desktop Duplication) -> OpenCV VideoWriter (MJPG) -> ffmpeg libx264 (H.264)
# Audio : pyaudiowpatch WASAPI loopback (system out) + mic (system in)
#         both captured in parallel threads -> separate temp WAVs
# Mux   : imageio_ffmpeg binary combines video + mixed audio -> final .mkv
#
# Encoding quality is driven by the video_compression and audio_compression
# profiles stored in persistent.json and resolved through configure.py.

import os
import tempfile
import threading
import time
import wave

import cv2
import mss
import numpy as np
import pyaudiowpatch as pyaudio

import scripts.configure as configure

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHUNK  = 1024     # frames per read

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
is_capturing       = False
capture_thread     = None
_pa                = None    # PyAudio instance, kept alive for the session
last_output_file   = None    # path of most recently completed recording / segment
last_segment_count = 0       # how many segments were saved in the last session
capture_start_time = None    # time.time() when current capture started
current_temp_video = None    # path of the in-progress temp AVI (for size polling)
current_segment_num    = 1   # 1-based segment counter (live, for monitor display)
_segment_start_time    = None  # time.time() when current segment started


# ---------------------------------------------------------------------------
# Segment elapsed helper  (called by displays.recording_monitor)
# ---------------------------------------------------------------------------
def current_segment_elapsed() -> float:
    """Seconds elapsed in the current recording segment (0.0 if not recording)."""
    if _segment_start_time is None:
        return 0.0
    return time.time() - _segment_start_time


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
def init_capture_system() -> bool:
    """Verify all runtime deps and codec availability. Returns True on success."""
    global _pa

    missing = []
    for mod in ("cv2", "mss", "numpy", "pyaudiowpatch", "imageio_ffmpeg"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print(f"ERROR: missing packages: {', '.join(missing)}")
        print("       Please run the installer (option 2 in the batch menu).")
        return False

    # Keep one PyAudio instance open for the session
    _pa = pyaudio.PyAudio()

    print("Capture system initialised  (mss + MJPG/ffmpeg libx264 + pyaudiowpatch).")
    return True


# ---------------------------------------------------------------------------
# Audio device helpers
# ---------------------------------------------------------------------------
def _get_loopback_device(pa: pyaudio.PyAudio):
    """Return device-info dict for the WASAPI loopback of the default output, or None."""
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        print("WARNING: WASAPI not available - system audio will not be recorded.")
        return None

    default_out = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])

    for lb in pa.get_loopback_device_info_generator():
        if default_out["name"] in lb["name"]:
            return lb

    print("WARNING: could not find a loopback device for the default output.")
    return None


def _get_default_mic(pa: pyaudio.PyAudio):
    """Return device-info dict for the default WASAPI microphone input, or None."""
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        print("WARNING: WASAPI not available - microphone will not be recorded.")
        return None

    idx = wasapi["defaultInputDevice"]
    if idx < 0:
        print("WARNING: no default input device found.")
        return None
    info = pa.get_device_info_by_index(idx)
    return info if info["maxInputChannels"] > 0 else None


# ---------------------------------------------------------------------------
# Audio capture thread
# ---------------------------------------------------------------------------
def _audio_capture_thread(pa: pyaudio.PyAudio, device_info: dict,
                          wav_path: str, stop_event: threading.Event):
    """
    Stream audio from device_info into a WAV file.
    For loopback devices pyaudiowpatch exposes output channels as input channels.
    Runs until stop_event is set.
    """
    is_loopback = device_info.get("isLoopbackDevice", False)

    if is_loopback:
        channels = int(device_info["maxOutputChannels"]) or 2
    else:
        channels = int(device_info["maxInputChannels"]) or 1

    rate = int(device_info["defaultSampleRate"])

    try:
        stream = pa.open(
            format             = AUDIO_FORMAT,
            channels           = channels,
            rate               = rate,
            input              = True,
            input_device_index = device_info["index"],
            frames_per_buffer  = AUDIO_CHUNK,
        )
    except OSError as e:
        print(f"WARNING: could not open audio stream for '{device_info['name']}': {e}")
        return

    frames = []
    while not stop_event.is_set():
        try:
            data = stream.read(AUDIO_CHUNK, exception_on_overflow=False)
            frames.append(data)
        except OSError:
            break

    stream.stop_stream()
    stream.close()

    if not frames:
        return

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))


# ---------------------------------------------------------------------------
# ffmpeg mux  (now config-driven)
# ---------------------------------------------------------------------------
def _mux(video_path: str, loopback_wav, mic_wav, output_path: str,
         config: dict):
    """
    Mux video (MJPG intermediate -> libx264 re-encode) with up to two
    audio WAV sources.  System audio and microphone are blended with
    ffmpeg's amix filter.  Output container is MKV.

    Video params (preset, crf, tune, pix_fmt) come from the active
    video_compression profile.  Audio bitrate is the effective value
    after the audio_compression cap is applied.
    """
    import subprocess
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd    = [ffmpeg, "-y"]

    # ---- inputs ----
    cmd += ["-i", video_path]

    audio_src_indices = []   # 1-based ffmpeg input indices for audio
    for wav in (loopback_wav, mic_wav):
        if wav and os.path.exists(wav) and os.path.getsize(wav) > 44:
            cmd += ["-i", wav]
            audio_src_indices.append(len(audio_src_indices) + 1)

    # ---- filter graph (video + audio) ----
    # Video filters: mpdecimate drops duplicate frames, vsync vfr keeps
    # variable framerate so those dropped frames actually save space.
    video_filter = "mpdecimate"

    if len(audio_src_indices) == 2:
        # Mix loopback + mic; normalize=0 keeps original levels
        fc = (f"[0:v]{video_filter}[vout];"
              f"[{audio_src_indices[0]}:a][{audio_src_indices[1]}:a]"
              f"amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        cmd += ["-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                "-vsync", "vfr"]
    elif len(audio_src_indices) == 1:
        cmd += ["-vf", video_filter,
                "-vsync", "vfr",
                "-map", "0:v", "-map", f"{audio_src_indices[0]}:a"]
    else:
        cmd += ["-vf", video_filter,
                "-vsync", "vfr",
                "-map", "0:v"]

    # ---- video codec: libx264 with profile-driven params ----
    video_params = configure.get_video_params(config)
    cmd += ["-c:v", "libx264"] + video_params

    # ---- audio codec: AAC at effective bitrate ----
    bitrate_kbps = configure.effective_audio_bitrate(config)
    cmd += ["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"]

    cmd += [output_path]

    print("Muxing video + audio ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("WARNING: ffmpeg mux failed - video-only fallback saved.")
        print(result.stderr[-2000:])
        try:
            import shutil
            base_no_ext = os.path.splitext(output_path)[0]
            fallback = f"{base_no_ext}_video_only.avi"
            shutil.copy2(video_path, fallback)
            print(f"  Fallback saved: {fallback}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Segment capture  (inner loop – captures one segment worth of frames)
# ---------------------------------------------------------------------------
SPLIT_DURATION = 3600.0   # seconds per segment (1 hour)


def _capture_segment(config: dict, segment_num: int,
                     split_limit: float | None) -> str:
    """
    Capture frames into one temp AVI for up to `split_limit` seconds
    (or indefinitely when split_limit is None).

    Returns:
        "split"  – stopped because the segment time limit was reached
                   (is_capturing is still True)
        "done"   – stopped because is_capturing went False
    """
    global current_temp_video, last_output_file, _segment_start_time
    global current_segment_num

    current_segment_num = segment_num

    w       = config["resolution"]["width"]
    h       = config["resolution"]["height"]
    fps     = config["fps"]
    out_dir = config["output_path"]
    os.makedirs(out_dir, exist_ok=True)

    stamp   = int(time.time())
    tmp_dir = tempfile.gettempdir()
    vid_tmp = os.path.join(tmp_dir, f"d264_video_{stamp}_s{segment_num:03d}.avi")
    lb_wav  = os.path.join(tmp_dir, f"d264_loopback_{stamp}_s{segment_num:03d}.wav")
    mic_wav = os.path.join(tmp_dir, f"d264_mic_{stamp}_s{segment_num:03d}.wav")

    # Build output filename.
    # When splits are enabled every segment always gets the _SNNN suffix so
    # the files sort cleanly even when there ends up being only one segment.
    container = config.get("container_format", "MKV").lower()
    date_str  = time.strftime("%Y_%m_%d")
    if split_limit is not None:
        base_name = f"Desktop_Video_{date_str}_S{segment_num:03d}"
    else:
        base_name = f"Desktop_Video_{date_str}"
    base  = os.path.join(out_dir, base_name)
    final = f"{base}.{container}"
    ctr   = 1
    while os.path.exists(final):
        final = f"{base}_{ctr:03d}.{container}"
        ctr  += 1

    current_temp_video = vid_tmp

    # ---- Identify audio devices ----
    loopback_info = _get_loopback_device(_pa)
    mic_info      = _get_default_mic(_pa)

    if segment_num == 1:
        if loopback_info:
            print(f"  System audio  : {loopback_info['name']}")
        else:
            print("  System audio  : unavailable")
        if mic_info:
            print(f"  Microphone    : {mic_info['name']}")
        else:
            print("  Microphone    : unavailable")

    # ---- Start audio threads ----
    stop_audio    = threading.Event()
    audio_threads = []

    if loopback_info:
        t = threading.Thread(target=_audio_capture_thread,
                             args=(_pa, loopback_info, lb_wav, stop_audio),
                             daemon=True)
        t.start()
        audio_threads.append(t)

    if mic_info:
        t = threading.Thread(target=_audio_capture_thread,
                             args=(_pa, mic_info, mic_wav, stop_audio),
                             daemon=True)
        t.start()
        audio_threads.append(t)

    # ---- Open video writer ----
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(vid_tmp, fourcc, fps, (w, h))

    if not writer.isOpened():
        print(f"ERROR: VideoWriter (MJPG) failed to open for segment {segment_num}. "
              "Segment aborted.")
        stop_audio.set()
        for t in audio_threads:
            t.join()
        return "done"

    seg_label = f"S{segment_num:03d}" if split_limit else "recording"
    print(f"Recording {seg_label} -> {final}")

    frame_dur  = 1.0 / fps
    next_tick  = time.perf_counter()
    _segment_start_time = time.time()
    result     = "done"   # default: stopped by is_capturing flag

    with mss.mss() as sct:
        monitor = sct.monitors[1]   # primary desktop

        while is_capturing:
            # Check segment time limit
            if split_limit is not None:
                if (time.time() - _segment_start_time) >= split_limit:
                    result = "split"
                    break

            now = time.perf_counter()
            if now < next_tick:
                time.sleep(max(0.0, next_tick - now - 0.001))
                continue

            raw   = sct.grab(monitor)
            frame = np.asarray(raw, dtype=np.uint8)
            bgr   = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            if bgr.shape[1] != w or bgr.shape[0] != h:
                bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LINEAR)

            writer.write(bgr)
            next_tick += frame_dur

    writer.release()

    # ---- Stop audio threads ----
    stop_audio.set()
    for t in audio_threads:
        t.join(timeout=5)

    # ---- Mux to final file ----
    _mux(vid_tmp,
         lb_wav if loopback_info else None,
         mic_wav if mic_info     else None,
         final, config)

    # Tidy temp files
    for p in (vid_tmp, lb_wav, mic_wav):
        try:
            os.remove(p)
        except OSError:
            pass

    last_output_file   = final
    current_temp_video = None
    _segment_start_time = None
    print(f"Segment saved: {final}")
    return result


# ---------------------------------------------------------------------------
# Main capture loop  (outer – manages segment iteration)
# ---------------------------------------------------------------------------
def _capture_loop(config: dict):
    global is_capturing, last_segment_count, current_segment_num

    splits_enabled = config.get("video_splits", False)
    split_limit    = SPLIT_DURATION if splits_enabled else None

    segment_num    = 1
    last_segment_count = 0

    while is_capturing:
        outcome = _capture_segment(config, segment_num, split_limit)
        last_segment_count += 1

        if outcome == "split" and is_capturing:
            segment_num += 1
            # Brief pause so filesystem flushes before next segment starts
            time.sleep(0.25)
        else:
            break   # stopped by user or error

    current_segment_num = 1   # reset for next session


# ---------------------------------------------------------------------------
# Public API  (called by launcher.py)
# ---------------------------------------------------------------------------
def start_capture(config: dict):
    global is_capturing, capture_thread, capture_start_time
    global last_output_file, current_temp_video
    global last_segment_count, current_segment_num, _segment_start_time

    if is_capturing:
        print("Already capturing.")
        return

    last_output_file    = None
    current_temp_video  = None
    last_segment_count  = 0
    current_segment_num = 1
    _segment_start_time = None
    capture_start_time  = time.time()
    is_capturing        = True
    capture_thread      = threading.Thread(target=_capture_loop, args=(config,),
                                           daemon=True)
    capture_thread.start()


def stop_capture():
    global is_capturing, capture_thread

    if not is_capturing:
        print("Not currently capturing.")
        return

    is_capturing = False
    if capture_thread and capture_thread.is_alive():
        print("Finalising recording (muxing audio) - please wait ...")
        capture_thread.join(timeout=60)

    capture_thread = None


def cleanup():
    """Called on application exit - releases PyAudio."""
    if is_capturing:
        stop_capture()
    global _pa
    if _pa:
        _pa.terminate()
        _pa = None