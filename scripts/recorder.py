# scripts/recorder.py
# Video : mss (DXGI Desktop Duplication) -> OpenCV VideoWriter (MJPG) -> ffmpeg libx264 (H.264)
# Audio : pyaudiowpatch WASAPI loopback (system out) + mic (system in)
#         both captured in parallel threads -> WAV written incrementally (streaming)
# Mux   : imageio_ffmpeg binary combines video + mixed audio -> final .mkv / .mp4
#
# --- SEGMENT PIPELINE ---
# Muxing is offloaded to a background ThreadPoolExecutor so that the next
# segment's frame capture begins the instant the previous segment's frames
# end.  No artificial delay; mss context is reused across segments.
#
# --- AUDIO MEMORY ---
# Audio data is written incrementally to the WAV file rather than
# accumulated in a list.  Peak RAM per audio device is now one chunk
# (~8-16 KB) rather than 600+ MB for a 1-hour session.
#
# --- CPU THREADING ---
# ffmpeg is passed -threads 0 (auto-detect all logical cores) and
# -filter_threads equal to CPU count for filter-graph parallelism.
# numpy / OpenCV / mss already auto-enable SIMD (SSE2, AVX, AVX2) via
# their pre-built wheels; no extra wiring is needed there.
#
# Encoding quality is driven by the video_compression and audio_compression
# profiles stored in persistent.json and resolved through configure.py.

import concurrent.futures
import ctypes
import os
import struct
import subprocess
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
# Audio format
# ---------------------------------------------------------------------------
AUDIO_FORMAT = pyaudio.paInt16

# AUDIO_CHUNK is set during init based on available RAM:
#   >= 4 GB available : 8 192  (fewer OS read calls, lower CPU overhead)
#   >= 2 GB available : 4 096  (balanced)
#   <  2 GB available : 2 048  (conservative)
# Larger values reduce per-call overhead at the cost of slightly higher
# audio latency; for a non-real-time recorder this trade-off is ideal.
AUDIO_CHUNK = 4096  # overridden by _detect_audio_chunk() at init

# ---------------------------------------------------------------------------
# Segment duration
# ---------------------------------------------------------------------------
SPLIT_DURATION = 3600.0  # seconds per segment (1 hour)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
is_capturing        = False
capture_thread      = None
_pa                 = None       # PyAudio instance – kept alive for the session
last_output_file    = None       # path of most-recently completed segment
last_segment_count  = 0          # segments saved in the last session
capture_start_time  = None       # time.time() when current capture started
current_temp_video  = None       # path of the in-progress temp AVI
current_segment_num = 1          # 1-based segment counter (live)
_segment_start_time = None       # time.time() when current segment started

# Mux pipeline ---------------------------------------------------------------
pending_mux_count  = 0           # segments currently being encoded in BG
_pending_mux_lock  = threading.Lock()
_mux_executor: concurrent.futures.ThreadPoolExecutor | None = None
_mux_futures: list[concurrent.futures.Future] = []

# CPU info cache -------------------------------------------------------------
_cpu_info: dict | None = None

# ---------------------------------------------------------------------------
# RAM detection  (Windows – ctypes, no extra packages)
# ---------------------------------------------------------------------------
def _get_available_ram_gb() -> float:
    """Return available physical RAM in GiB using GlobalMemoryStatusEx."""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength",                ctypes.c_ulong),
                ("dwMemoryLoad",            ctypes.c_ulong),
                ("ullTotalPhys",            ctypes.c_ulonglong),
                ("ullAvailPhys",            ctypes.c_ulonglong),
                ("ullTotalPageFile",        ctypes.c_ulonglong),
                ("ullAvailPageFile",        ctypes.c_ulonglong),
                ("ullTotalVirtual",         ctypes.c_ulonglong),
                ("ullAvailVirtual",         ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullAvailPhys / (1024 ** 3)
    except Exception:
        return 2.0  # safe default if ctypes fails


def _detect_audio_chunk() -> int:
    """Choose AUDIO_CHUNK size based on available RAM."""
    ram = _get_available_ram_gb()
    if ram >= 4.0:
        return 8192
    if ram >= 2.0:
        return 4096
    return 2048


# ---------------------------------------------------------------------------
# CPU feature detection  (Windows – IsProcessorFeaturePresent)
# ---------------------------------------------------------------------------
# PF_ constants from winnt.h
_PF = {
    "SSE2":          10,
    "SSE3":          13,  # PF_SSE3_INSTRUCTIONS_AVAILABLE (may not be present on all OS)
    "XSAVE":         17,
}

# For AVX / AVX2 / AVX-512 we use the CPUID instruction via inline assembly
# emulated through ctypes + a small struct; fall back gracefully on error.
def _cpuid(leaf: int, subleaf: int = 0) -> tuple[int, int, int, int]:
    """
    Execute CPUID with eax=leaf, ecx=subleaf.
    Returns (eax, ebx, ecx, edx).  Raises RuntimeError on failure.
    """
    # Build a tiny x86-64 CPUID shellcode and call it via ctypes VirtualAlloc.
    # The shellcode: push rbx; mov eax, ecx (leaf); mov ecx, edx (subleaf);
    #                cpuid; mov [r8], eax; mov [r9], ebx; ...
    # This is complex and Windows-specific; use a simpler heuristic instead.
    raise RuntimeError("direct CPUID not implemented; use fallback")


def _detect_avx_support() -> dict[str, bool]:
    """
    Detect AVX / AVX2 / AVX-512 by inspecting numpy's CPU dispatch flags.
    numpy exposes which SIMD targets it was compiled with and which it will
    use at runtime via numpy.lib._version (private) or sys / platform.

    We also check IsProcessorFeaturePresent for basic SSE2 presence.
    """
    result = {"SSE2": False, "AVX": False, "AVX2": False, "AVX512F": False}

    # --- Basic features via IsProcessorFeaturePresent ---
    try:
        k32 = ctypes.windll.kernel32
        result["SSE2"] = bool(k32.IsProcessorFeaturePresent(10))
    except Exception:
        pass

    # --- AVX / AVX2 / AVX-512 from numpy's runtime CPU info ---
    try:
        # numpy >= 1.21 exposes __cpu_features__  (dict of feature -> bool)
        cpu_features = np.__cpu_features__          # type: ignore[attr-defined]
        result["AVX"]    = bool(cpu_features.get("AVX",    False))
        result["AVX2"]   = bool(cpu_features.get("AVX2",   False))
        result["AVX512F"] = bool(cpu_features.get("AVX512F", False))
        return result
    except AttributeError:
        pass

    # Fallback: probe via numpy's optimised dispatch (older numpy)
    try:
        conf = np.__config__.blas_opt_info           # type: ignore[attr-defined]
        extra = " ".join(str(v) for v in conf.values())
        if "avx512" in extra.lower():
            result["AVX512F"] = True
            result["AVX2"]    = True
            result["AVX"]     = True
        elif "avx2" in extra.lower():
            result["AVX2"]  = True
            result["AVX"]   = True
        elif "avx" in extra.lower():
            result["AVX"]   = True
    except Exception:
        pass

    return result


def get_cpu_info() -> dict:
    """
    Return a cached dict with CPU name, logical core count, and SIMD flags.
    Called by displays.system_info_screen().
    """
    global _cpu_info
    if _cpu_info is not None:
        return _cpu_info

    info: dict = {
        "name":         "Unknown",
        "logical_cores": os.cpu_count() or 1,
        "avx":          False,
        "avx2":         False,
        "avx512f":      False,
        "sse2":         False,
        "numpy_threads": 1,
    }

    # CPU name via WMIC (Windows)
    try:
        out = subprocess.check_output(
            ["wmic", "cpu", "get", "Name", "/value"],
            text=True, timeout=5, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if line.startswith("Name="):
                info["name"] = line.split("=", 1)[1].strip()
                break
    except Exception:
        pass

    # SIMD flags
    avx = _detect_avx_support()
    info["sse2"]    = avx.get("SSE2",    False)
    info["avx"]     = avx.get("AVX",     False)
    info["avx2"]    = avx.get("AVX2",    False)
    info["avx512f"] = avx.get("AVX512F", False)

    # numpy thread count
    try:
        info["numpy_threads"] = np.__config__.blas_opt_info.get(    # type: ignore
            "num_threads", os.cpu_count() or 1)
    except Exception:
        info["numpy_threads"] = os.cpu_count() or 1

    _cpu_info = info
    return info


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
    """Verify all runtime deps, choose buffer sizes, open PyAudio. Returns True on success."""
    global _pa, AUDIO_CHUNK

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

    # Size audio chunk based on available RAM
    AUDIO_CHUNK = _detect_audio_chunk()

    # Warm up CPU info cache
    ci = get_cpu_info()

    # One PyAudio instance for the whole session
    _pa = pyaudio.PyAudio()

    simd = []
    if ci["sse2"]:    simd.append("SSE2")
    if ci["avx"]:     simd.append("AVX")
    if ci["avx2"]:    simd.append("AVX2")
    if ci["avx512f"]: simd.append("AVX-512F")
    simd_str = ", ".join(simd) if simd else "none detected"

    ram_gb = _get_available_ram_gb()
    print(f"Capture system initialised  (mss + MJPG/ffmpeg libx264 + pyaudiowpatch).")
    print(f"  CPU         : {ci['name']}")
    print(f"  Logical CPUs: {ci['logical_cores']}   SIMD: {simd_str}")
    print(f"  Free RAM    : {ram_gb:.1f} GB   Audio chunk: {AUDIO_CHUNK} frames")
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
# Audio capture thread  —  STREAMING WAV WRITE (O(1) RAM)
# ---------------------------------------------------------------------------
def _audio_capture_thread(pa: pyaudio.PyAudio, device_info: dict,
                          wav_path: str, stop_event: threading.Event):
    """
    Stream audio from device_info directly into a WAV file one chunk at a time.

    Previous design accumulated all frames in a Python list and wrote them
    in a single wf.writeframes() call at the end.  For a 1-hour session at
    44 100 Hz / stereo int16 that meant ~630 MB held in RAM per device.

    This version writes each chunk to disk immediately; peak in-memory usage
    per device is a single AUDIO_CHUNK (8–16 KB).

    The wave module updates the file header on close(), so the WAV is valid
    even if the process is interrupted after the file is opened.
    """
    is_loopback = device_info.get("isLoopbackDevice", False)
    channels    = int(device_info["maxOutputChannels"] if is_loopback
                      else device_info["maxInputChannels"]) or (2 if is_loopback else 1)
    rate        = int(device_info["defaultSampleRate"])

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

    wrote_any = False
    try:
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
            wf.setframerate(rate)

            while not stop_event.is_set():
                try:
                    data = stream.read(AUDIO_CHUNK, exception_on_overflow=False)
                    wf.writeframes(data)
                    wrote_any = True
                except OSError:
                    break
    finally:
        stream.stop_stream()
        stream.close()

    # Remove zero-length WAV so the mux step skips it gracefully
    if not wrote_any and os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# ffmpeg mux  (config-driven, multi-threaded)
# ---------------------------------------------------------------------------
def _mux(video_path: str, loopback_wav, mic_wav, output_path: str,
         config: dict):
    """
    Mux video (MJPG intermediate -> libx264 re-encode) with up to two
    audio WAV sources.  System audio and microphone are blended with
    ffmpeg's amix filter.

    -threads 0         : ffmpeg auto-uses all logical CPU cores for encoding
    -filter_threads N  : parallelise filter-graph work across N threads
    -filter_complex_threads N: same for complex filter graphs

    Video params (preset, crf, tune, pix_fmt) come from the active
    video_compression profile.  Audio bitrate is the effective value
    after the audio_compression cap is applied.
    """
    import imageio_ffmpeg

    cpu_count    = os.cpu_count() or 2
    ffmpeg       = imageio_ffmpeg.get_ffmpeg_exe()
    cmd          = [ffmpeg, "-y"]

    # ---- thread control ----
    cmd += ["-threads", "0"]                        # libx264 thread pool

    # ---- inputs ----
    cmd += ["-i", video_path]

    audio_src_indices = []
    for wav in (loopback_wav, mic_wav):
        if wav and os.path.exists(wav) and os.path.getsize(wav) > 44:
            cmd += ["-i", wav]
            audio_src_indices.append(len(audio_src_indices) + 1)

    # ---- filter graph ----
    # mpdecimate: drop duplicate frames (huge savings on static screens)
    # vsync vfr:  variable-rate so dropped frames actually shrink the file
    video_filter = "mpdecimate"

    if len(audio_src_indices) == 2:
        fc = (f"[0:v]{video_filter}[vout];"
              f"[{audio_src_indices[0]}:a][{audio_src_indices[1]}:a]"
              f"amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        cmd += ["-filter_complex", fc,
                "-filter_complex_threads", str(cpu_count),
                "-map", "[vout]", "-map", "[aout]",
                "-vsync", "vfr"]
    elif len(audio_src_indices) == 1:
        cmd += ["-vf", video_filter,
                "-filter_threads", str(cpu_count),
                "-vsync", "vfr",
                "-map", "0:v", "-map", f"{audio_src_indices[0]}:a"]
    else:
        cmd += ["-vf", video_filter,
                "-filter_threads", str(cpu_count),
                "-vsync", "vfr",
                "-map", "0:v"]

    # ---- video codec: libx264 with profile-driven params ----
    video_params = configure.get_video_params(config)
    cmd += ["-c:v", "libx264"] + video_params

    # ---- audio codec: AAC at effective bitrate ----
    bitrate_kbps = configure.effective_audio_bitrate(config)
    cmd += ["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"]

    cmd += [output_path]

    print(f"Muxing (BG)  -> {os.path.basename(output_path)}"
          f"  [threads={cpu_count}]")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: ffmpeg mux failed for {os.path.basename(output_path)}.")
        print(result.stderr[-2000:])
        try:
            import shutil
            base_no_ext = os.path.splitext(output_path)[0]
            fallback    = f"{base_no_ext}_video_only.avi"
            shutil.copy2(video_path, fallback)
            print(f"  Fallback saved: {fallback}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Background mux-and-cleanup task
# ---------------------------------------------------------------------------
def _mux_and_cleanup(vid_tmp: str, lb_wav: str | None, mic_wav: str | None,
                     final_path: str, config: dict):
    """
    Runs in a ThreadPoolExecutor worker.
    1. Mux video + audio to final_path.
    2. Delete temp files.
    3. Update shared globals (last_output_file, pending_mux_count).
    """
    global last_output_file, pending_mux_count

    try:
        _mux(vid_tmp, lb_wav, mic_wav, final_path, config)
    finally:
        # Always clean up temp files and decrement counter
        for p in filter(None, (vid_tmp, lb_wav, mic_wav)):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

        with _pending_mux_lock:
            pending_mux_count = max(0, pending_mux_count - 1)

    if os.path.exists(final_path):
        last_output_file = final_path
        print(f"Segment saved : {final_path}")
    else:
        print(f"WARNING: expected output not found: {final_path}")


# ---------------------------------------------------------------------------
# Segment capture  (inner – captures one segment of frames, returns immediately)
# ---------------------------------------------------------------------------
def _capture_segment(config: dict, segment_num: int,
                     split_limit: float | None,
                     sct: mss.base.MSSBase
                     ) -> tuple | None:
    """
    Capture frames into one temp AVI for up to `split_limit` seconds
    (or indefinitely when split_limit is None).

    The mss screen-capture context (sct) is passed in so it can be
    reused across segments – this avoids DXGI re-initialisation overhead.

    Returns a 5-tuple:
        (outcome, vid_tmp, lb_wav_or_None, mic_wav_or_None, final_path)

    outcome:
        "split" – stopped because the segment time limit was reached
        "done"  – stopped because is_capturing went False
    Returns None on a fatal VideoWriter error.
    """
    global current_temp_video, _segment_start_time, current_segment_num

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
                             daemon=True, name=f"audio-lb-s{segment_num}")
        t.start()
        audio_threads.append(t)

    if mic_info:
        t = threading.Thread(target=_audio_capture_thread,
                             args=(_pa, mic_info, mic_wav, stop_audio),
                             daemon=True, name=f"audio-mic-s{segment_num}")
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
            t.join(timeout=5)
        current_temp_video = None
        return None

    seg_label = f"S{segment_num:03d}" if split_limit else "recording"
    print(f"Capturing {seg_label} -> {final}")

    frame_dur            = 1.0 / fps
    next_tick            = time.perf_counter()
    _segment_start_time  = time.time()
    result               = "done"

    # Re-query monitor each segment in case display setup changed
    monitor = sct.monitors[1]

    while is_capturing:
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
        t.join(timeout=10)

    # Resolve actual wav paths (thread writes to these; None if file absent)
    actual_lb_wav  = lb_wav  if (loopback_info and os.path.exists(lb_wav))  else None
    actual_mic_wav = mic_wav if (mic_info      and os.path.exists(mic_wav)) else None

    current_temp_video  = None
    _segment_start_time = None

    return result, vid_tmp, actual_lb_wav, actual_mic_wav, final


# ---------------------------------------------------------------------------
# Main capture loop  (outer – manages segment pipeline)
# ---------------------------------------------------------------------------
def _capture_loop(config: dict):
    """
    Outer loop managing multi-segment capture with a pipelined mux.

    KEY CHANGE FROM ORIGINAL:
    After each segment's frame capture ends, the mux is submitted to a
    background ThreadPoolExecutor and the next segment begins immediately.
    The previous design ran the mux inside _capture_segment() and blocked
    the loop for the entire ffmpeg encoding time (potentially several minutes
    for a 1-hour MJPG -> H.264 re-encode), causing a visible gap.

    We use max_workers=1 so that only one ffmpeg process runs at a time.
    This keeps CPU load predictable: one core-pool for capture (mss /
    OpenCV / numpy), one core-pool for encoding (ffmpeg -threads 0).
    """
    global is_capturing, last_segment_count, current_segment_num
    global pending_mux_count, _mux_executor, _mux_futures

    splits_enabled = config.get("video_splits", False)
    split_limit    = SPLIT_DURATION if splits_enabled else None

    # One ffmpeg at a time; capture and encode share the machine without fighting.
    executor       = concurrent.futures.ThreadPoolExecutor(max_workers=1,
                                                           thread_name_prefix="mux")
    _mux_executor  = executor
    futures: list[concurrent.futures.Future] = []
    _mux_futures   = futures

    segment_num        = 1
    last_segment_count = 0

    # Reuse a single mss context for the entire session (avoids DXGI re-init
    # overhead between segments, which can take hundreds of milliseconds).
    with mss.mss() as sct:
        while is_capturing:
            result = _capture_segment(config, segment_num, split_limit, sct)

            if result is None:
                # VideoWriter fatal error; stop cleanly
                break

            outcome, vid_tmp, lb_wav, mic_wav, final_path = result
            last_segment_count += 1

            # Increment BEFORE submitting so the display shows it immediately
            with _pending_mux_lock:
                pending_mux_count += 1

            future = executor.submit(
                _mux_and_cleanup, vid_tmp, lb_wav, mic_wav, final_path, config
            )
            futures.append(future)

            if outcome == "split" and is_capturing:
                segment_num += 1
                # No sleep – next segment capture starts immediately.
                # The previous 0.25 s delay is eliminated; mss context is
                # already warm and VideoWriter opens in < 1 ms.
            else:
                break   # user stopped, or not splitting

    # Frame capture done.  _mux_futures is readable by stop_capture() for
    # waiting.  We do NOT wait here – _capture_loop returns so that the
    # capture_thread finishes quickly, and stop_capture() handles the wait.
    current_segment_num = 1


# ---------------------------------------------------------------------------
# Public API  (called by launcher.py / displays.py)
# ---------------------------------------------------------------------------
def start_capture(config: dict):
    global is_capturing, capture_thread, capture_start_time
    global last_output_file, current_temp_video
    global last_segment_count, current_segment_num, _segment_start_time
    global pending_mux_count, _mux_futures

    if is_capturing:
        print("Already capturing.")
        return

    last_output_file    = None
    current_temp_video  = None
    last_segment_count  = 0
    current_segment_num = 1
    _segment_start_time = None
    pending_mux_count   = 0
    _mux_futures        = []
    capture_start_time  = time.time()
    is_capturing        = True

    capture_thread = threading.Thread(target=_capture_loop, args=(config,),
                                      daemon=True, name="capture-loop")
    capture_thread.start()


def stop_capture():
    """
    Signal the capture loop to stop, then wait for all background mux jobs.

    The capture_thread itself finishes quickly (it just returns from
    _capture_loop after setting the flag).  The potentially long wait is
    for the executor futures (ffmpeg encoding).  No arbitrary timeout is
    applied to the mux wait because encoding a 1-hour segment can legitimately
    take several minutes.
    """
    global is_capturing, capture_thread, _mux_executor

    if not is_capturing:
        print("Not currently capturing.")
        return

    is_capturing = False

    # Wait for the frame-capture thread to exit (fast – just finishes current frame)
    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=15)

    capture_thread = None

    # Wait for all background mux jobs
    futures_to_wait = list(_mux_futures)   # snapshot
    if futures_to_wait:
        remaining = sum(1 for f in futures_to_wait if not f.done())
        if remaining:
            print(f"  Waiting for {remaining} segment mux job(s) to complete ...")
        for future in futures_to_wait:
            try:
                future.result()            # blocks until this mux finishes
            except Exception as e:
                print(f"  Mux error: {e}")

    if _mux_executor is not None:
        _mux_executor.shutdown(wait=False)
        _mux_executor = None


def cleanup():
    """Called on application exit – releases PyAudio."""
    if is_capturing:
        stop_capture()
    global _pa
    if _pa:
        _pa.terminate()
        _pa = None