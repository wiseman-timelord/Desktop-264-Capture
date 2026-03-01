# scripts/recorder.py
# Video : mss (DXGI Desktop Duplication) -> ffmpeg libx264 (H.264) via stdin pipe
# Audio : pyaudiowpatch WASAPI loopback (system out) + mic (system in)
#         both captured in parallel threads -> WAV written incrementally (streaming)
# Mux   : imageio_ffmpeg binary combines pre-encoded video + mixed audio -> final .mkv / .mp4
#         Video is STREAM-COPIED (-c:v copy); mux completes in seconds, not minutes.
#
# --- WHY THE OLD APPROACH CAUSED FROZEN VIDEO (last ~15 min of every segment) ---
#
# ROOT CAUSE — Disk Space Exhaustion from Competing MJPG AVI Temp Files
# -----------------------------------------------------------------------
# The previous design wrote each captured segment to a large MJPG AVI
# intermediate in the system temp directory (typically C:\Users\...\AppData\
# Local\Temp).  At 1080p / 30 fps with OpenCV's default MJPG quality, those
# files grew at roughly 3-8 MB/s, producing files of 10-20 GB per hour.
#
# The background _mux_and_cleanup job had to re-encode that entire MJPG AVI
# with libx264 before it could delete it.  On a mid-range PC that re-encode
# takes 30-60+ minutes.  This meant:
#
#   t =  0 min  Segment 1 starts; d264_video_T_s001.avi grows on temp drive.
#   t = 60 min  Segment 1 ends; mux starts in background (still reading s001.avi).
#   t = 60 min  Segment 2 starts; d264_video_T_s002.avi also grows on temp drive.
#               BOTH AVI files now exist simultaneously.
#   t = 75 min  (example) Temp drive fills up.  cv2.VideoWriter.write() starts
#               silently failing — OpenCV raises no exception on disk-full writes.
#               The grab loop, the frame timer, and the audio threads all continue
#               normally.  Only video frames are lost.
#   t = 105 min Mux finishes; s001.avi deleted.  But 30 minutes of segment 2
#               are already missing.  Segment 2 will have ~45 min of video and
#               60 min of audio -> last 15 min appears frozen in every player.
#
# The "last 15 minutes of every segment" symptom was consistent precisely
# because the mux duration was consistent (~45 min), making the disk-full
# moment arrive at a predictable 45-minute offset into each segment.
#
# SECONDARY CAUSE — mpdecimate + vsync vfr Frame Dropping
# ---------------------------------------------------------
# The mux pass applied mpdecimate (drops "duplicate" frames) and -vsync vfr
# (variable frame rate).  On static or slow-moving screen content — menus,
# loading screens, inventory, cutscenes — mpdecimate aggressively classified
# legitimate frames as duplicates and removed them.  With VFR output, the
# gaps appear as visible freezes in many media players.  This compounded the
# disk issue and could independently cause short freeze artefacts even when
# disk space was not a problem.
#
# --- HOW THIS VERSION FIXES IT ---
#
# 1.  No MJPG AVI intermediate.  Raw BGR frames are piped directly to an
#     ffmpeg subprocess (stdin pipe) which encodes them in real time with
#     libx264.  The temp file is already H.264-compressed MKV; it is 1-5 GB/
#     hour instead of 10-20 GB/hour.
#
# 2.  Mux step uses -c:v copy (stream copy).  Video is already encoded, so
#     the mux only has to encode audio (AAC) and rewrite the container.
#     Mux time drops from 30-60 min to 5-60 seconds.  The previous segment's
#     temp file is deleted almost immediately, so the two temp files never
#     coexist for meaningful duration.  Peak temp disk usage: ~2-6 GB.
#
# 3.  mpdecimate is removed.  Frame rates are constant and correct; no
#     duplicate-frame heuristics introduce freeze artefacts.
#
# 4.  A dedicated pipe-writer thread drains a bounded queue, so the grab
#     loop is never blocked by stdin I/O.  If the encoder genuinely falls
#     behind, frames are dropped with a printed warning rather than the
#     queue growing without bound.
#
# --- AUDIO MEMORY ---
# Audio data is written incrementally to the WAV file (one AUDIO_CHUNK at a
# time).  Peak RAM per audio device is ~8-16 KB regardless of recording length.
#
# --- CPU THREADING ---
# _thread_cap (25/50/75 % of logical cores) is applied to the real-time
# ffmpeg libx264 encoder and to the mux-step audio AAC encoder.  The
# remaining percentage is reserved for the OS and the game being recorded.

import concurrent.futures
import ctypes
import os
import queue as _queue
import shutil
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
#   >= 4 GB available : 8 192
#   >= 2 GB available : 4 096
#   <  2 GB available : 2 048
AUDIO_CHUNK = 4096  # overridden by _detect_audio_chunk() at init

# ---------------------------------------------------------------------------
# Segment duration
# ---------------------------------------------------------------------------
SPLIT_DURATION = 3600.0  # seconds per segment (1 hour)

# ---------------------------------------------------------------------------
# Pipe writer queue depth
# ---------------------------------------------------------------------------
# Number of raw BGR frames buffered between the grab loop and the ffmpeg
# stdin writer thread.  Each 1080p BGR frame is ~6 MB; 30 frames ≈ 180 MB.
# Absorbs short encoder stalls without dropping frames.  If the encoder
# falls further behind, frames are dropped rather than RAM exhausted.
_PIPE_QUEUE_DEPTH = 30   # frames

# ---------------------------------------------------------------------------
# CPU thread budget
# ---------------------------------------------------------------------------
_THREAD_BUDGET_DEFAULT = 75
_thread_cap: int = max(1, int((os.cpu_count() or 2) * _THREAD_BUDGET_DEFAULT / 100))

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
is_capturing        = False
capture_thread      = None
_pa                 = None
last_output_file    = None
last_segment_count  = 0
capture_start_time  = None
current_temp_video  = None
current_segment_num = 1
_segment_start_time = None

# Mux pipeline ---------------------------------------------------------------
pending_mux_count  = 0
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
        return 2.0


def _detect_audio_chunk() -> int:
    """Choose AUDIO_CHUNK size based on available RAM."""
    ram = _get_available_ram_gb()
    if ram >= 4.0:
        return 8192
    if ram >= 2.0:
        return 4096
    return 2048


# ---------------------------------------------------------------------------
# CPU feature detection  (Windows – IsProcessorFeaturePresent + numpy)
# ---------------------------------------------------------------------------
_PF = {
    "SSE2":  10,
    "SSE3":  13,
    "XSAVE": 17,
}

def _cpuid(leaf: int, subleaf: int = 0) -> tuple[int, int, int, int]:
    raise RuntimeError("direct CPUID not implemented; use fallback")


def _detect_avx_support() -> dict[str, bool]:
    result = {"SSE2": False, "AVX": False, "AVX2": False, "AVX512F": False}

    try:
        k32 = ctypes.windll.kernel32
        result["SSE2"] = bool(k32.IsProcessorFeaturePresent(10))
    except Exception:
        pass

    try:
        cpu_features = np.__cpu_features__          # type: ignore[attr-defined]
        result["AVX"]     = bool(cpu_features.get("AVX",    False))
        result["AVX2"]    = bool(cpu_features.get("AVX2",   False))
        result["AVX512F"] = bool(cpu_features.get("AVX512F", False))
        return result
    except AttributeError:
        pass

    try:
        conf  = np.__config__.blas_opt_info          # type: ignore[attr-defined]
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
    """Return a cached dict with CPU name, logical core count, and SIMD flags."""
    global _cpu_info
    if _cpu_info is not None:
        return _cpu_info

    info: dict = {
        "name":          "Unknown",
        "logical_cores":  os.cpu_count() or 1,
        "avx":           False,
        "avx2":          False,
        "avx512f":       False,
        "sse2":          False,
        "numpy_threads":  1,
        "thread_cap":    _thread_cap,
    }

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

    avx = _detect_avx_support()
    info["sse2"]    = avx.get("SSE2",    False)
    info["avx"]     = avx.get("AVX",     False)
    info["avx2"]    = avx.get("AVX2",    False)
    info["avx512f"] = avx.get("AVX512F", False)

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

    AUDIO_CHUNK = _detect_audio_chunk()
    cv2.setNumThreads(_thread_cap)

    ci = get_cpu_info()
    _pa = pyaudio.PyAudio()

    simd = []
    if ci["sse2"]:    simd.append("SSE2")
    if ci["avx"]:     simd.append("AVX")
    if ci["avx2"]:    simd.append("AVX2")
    if ci["avx512f"]: simd.append("AVX-512F")
    simd_str = ", ".join(simd) if simd else "none detected"

    ram_gb = _get_available_ram_gb()
    print(f"Capture system initialised  (mss + ffmpeg libx264 pipe + pyaudiowpatch).")
    print(f"  CPU         : {ci['name']}")
    print(f"  Logical CPUs: {ci['logical_cores']}   SIMD: {simd_str}")
    print(f"  Thread cap  : {_thread_cap} core(s) (fallback – updated at recording start)")
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
    Peak in-memory usage per device is a single AUDIO_CHUNK (8-16 KB).
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

    if not wrote_any and os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# ffmpeg mux  —  STREAM COPY for video (seconds, not minutes)
# ---------------------------------------------------------------------------
def _mux(video_path: str, loopback_wav, mic_wav, output_path: str, config: dict):
    """
    Mux a pre-encoded H.264 video with up to two audio WAV sources.

    VIDEO IS STREAM-COPIED (-c:v copy).  Because the capture stage already
    encoded the video with libx264 in real time, there is nothing to re-encode.
    This reduces mux time from 30-60 minutes (old: MJPG AVI -> libx264 re-encode)
    to typically 5-60 seconds (container remux + AAC audio encode only).

    The fast mux means the previous segment's temp MKV file is deleted almost
    immediately after the segment ends, so temp disk usage stays low throughout
    a multi-hour session and the disk-exhaustion / frozen-video problem cannot
    recur.
    """
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd    = [ffmpeg, "-y"]

    # Thread control (for the audio filter graph and AAC encoder only;
    # video requires no threads because it is stream-copied).
    cmd += ["-threads", str(_thread_cap)]

    # ---- inputs ----
    cmd += ["-i", video_path]   # pre-encoded H.264 MKV (video only, no audio track)

    audio_src_indices = []
    for wav in (loopback_wav, mic_wav):
        if wav and os.path.exists(wav) and os.path.getsize(wav) > 44:
            cmd += ["-i", wav]
            audio_src_indices.append(len(audio_src_indices) + 1)

    # ---- video: stream copy, zero re-encode cost ----
    cmd += ["-c:v", "copy"]

    # ---- audio: mix if both present, then encode AAC ----
    if len(audio_src_indices) == 2:
        fc = (f"[{audio_src_indices[0]}:a][{audio_src_indices[1]}:a]"
              f"amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        cmd += ["-filter_complex", fc,
                "-filter_complex_threads", str(_thread_cap),
                "-map", "0:v", "-map", "[aout]"]
    elif len(audio_src_indices) == 1:
        cmd += ["-map", "0:v", "-map", f"{audio_src_indices[0]}:a"]
    else:
        cmd += ["-map", "0:v"]

    if audio_src_indices:
        bitrate_kbps = configure.effective_audio_bitrate(config)
        cmd += ["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"]

    cmd += [output_path]

    print(f"Muxing (BG)  -> {os.path.basename(output_path)}"
          f"  [stream copy + AAC, threads={_thread_cap}/{os.cpu_count() or 2}]")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: ffmpeg mux failed for {os.path.basename(output_path)}.")
        print(result.stderr[-2000:])
        try:
            base_no_ext = os.path.splitext(output_path)[0]
            fallback    = f"{base_no_ext}_video_only.mkv"
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
    1. Mux video + audio to final_path  (fast: stream copy + AAC only).
    2. Delete temp files.
    3. Update shared globals.
    """
    global last_output_file, pending_mux_count

    try:
        _mux(vid_tmp, lb_wav, mic_wav, final_path, config)
    finally:
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
# Segment capture  (inner)
# ---------------------------------------------------------------------------
def _capture_segment(config: dict, segment_num: int,
                     split_limit: float | None,
                     sct: mss.base.MSSBase
                     ) -> tuple | None:
    """
    Capture one segment of frames and encode them in real-time via an ffmpeg
    stdin pipe.

    Pipeline:
        mss grab -> BGRA->BGR (cv2) -> frame queue ->
        [pipe-writer thread] -> ffmpeg stdin ->
        libx264 real-time encoder -> temp MKV (video only, no audio)

    The pipe-writer thread decouples the grab loop from stdin I/O latency.
    If the encoder is slower than the capture rate (queue fills), frames are
    dropped with a warning rather than blocking the timer or growing RAM.

    Returns:
        (outcome, vid_tmp, lb_wav_or_None, mic_wav_or_None, final_path)
        outcome: "split" – time limit reached; "done" – user stopped
    Returns None on a fatal ffmpeg startup error.
    """
    import imageio_ffmpeg

    global current_temp_video, _segment_start_time, current_segment_num

    current_segment_num = segment_num

    w       = config["resolution"]["width"]
    h       = config["resolution"]["height"]
    fps     = config["fps"]
    out_dir = config["output_path"]
    os.makedirs(out_dir, exist_ok=True)

    stamp   = int(time.time())
    tmp_dir = tempfile.gettempdir()

    # Temp video is now pre-encoded H.264 MKV: 1-5 GB/hour vs 10-20 GB/hour
    # for the old MJPG AVI intermediate.
    vid_tmp = os.path.join(tmp_dir, f"d264_video_{stamp}_s{segment_num:03d}.mkv")
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

    # ---- Launch ffmpeg for real-time H.264 encoding via stdin pipe ----
    #
    # Input  : raw BGR24 frames at the configured resolution and FPS.
    # Output : H.264 video in MKV container, no audio track.
    #
    # -thread_queue_size 512  : ffmpeg input demuxer read-ahead buffer.
    #                           Decouples I/O from the encoder thread pool
    #                           and absorbs brief grab-loop hiccups.
    # -an                     : suppress audio; audio is added at mux time.
    # video_params (preset/crf/tune/pix_fmt) : from active compression profile.
    ffmpeg_exe   = imageio_ffmpeg.get_ffmpeg_exe()
    video_params = configure.get_video_params(config)

    ffmpeg_cmd = [
        ffmpeg_exe, "-y",
        "-f",                "rawvideo",
        "-vcodec",           "rawvideo",
        "-s",                f"{w}x{h}",
        "-pix_fmt",          "bgr24",
        "-r",                str(fps),
        "-thread_queue_size","512",
        "-i",                "pipe:0",
        "-c:v",              "libx264",
        "-threads",          str(_thread_cap),
    ] + video_params + [
        "-an",
        "-f", "matroska",
        vid_tmp,
    ]

    try:
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin  = subprocess.PIPE,
            stdout = subprocess.DEVNULL,
            stderr = subprocess.PIPE,
        )
    except OSError as e:
        print(f"ERROR: could not launch ffmpeg for segment {segment_num}: {e}")
        stop_audio.set()
        for t in audio_threads:
            t.join(timeout=5)
        current_temp_video = None
        return None

    # ---- Pipe-writer thread ----
    # Writes raw BGR bytes to ffmpeg stdin from a bounded queue.
    # Runs as a daemon thread so it is cleaned up if the main process exits.
    frame_q = _queue.Queue(maxsize=_PIPE_QUEUE_DEPTH)

    def _pipe_writer():
        while True:
            item = frame_q.get()
            if item is None:
                break
            try:
                ffmpeg_proc.stdin.write(item)
            except (BrokenPipeError, OSError):
                # ffmpeg process died; drain queue to unblock any put() calls.
                while True:
                    try:
                        frame_q.get_nowait()
                    except _queue.Empty:
                        break
                break

    pipe_thread = threading.Thread(target=_pipe_writer, daemon=True,
                                   name=f"pipe-s{segment_num}")
    pipe_thread.start()

    seg_label = f"S{segment_num:03d}" if split_limit else "recording"
    print(f"Capturing {seg_label} -> {final}")

    frame_dur            = 1.0 / fps
    next_tick            = time.perf_counter()
    _segment_start_time  = time.time()
    result               = "done"
    frames_dropped       = 0

    # Re-query monitor each segment in case display setup changed.
    monitor = sct.monitors[1]

    # ---- Frame grab loop ----
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

        # tobytes() produces a new bytes object (safe copy; the mss internal
        # buffer is reused on the next sct.grab() call).
        # Non-blocking put: if the queue is full the frame is dropped rather
        # than the grab loop stalling (which would cascade into audio desync).
        try:
            frame_q.put_nowait(bgr.tobytes())
        except _queue.Full:
            frames_dropped += 1

        next_tick += frame_dur

    # ---- Flush and close ----
    frame_q.put(None)           # sentinel: tells pipe_writer to exit
    pipe_thread.join(timeout=60)

    try:
        ffmpeg_proc.stdin.close()
    except OSError:
        pass

    # Wait for ffmpeg to flush encoder buffers and finalise the MKV.
    # With -tune zerolatency the flush is near-instant; 120 s is a generous
    # safety margin for any edge case.
    try:
        ret = ffmpeg_proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        ffmpeg_proc.kill()
        ret = ffmpeg_proc.wait()
        print(f"  WARNING: ffmpeg timed out flushing segment {segment_num}; process killed.")

    if frames_dropped:
        print(f"  Warning: {frames_dropped} frame(s) dropped (pipe queue full — "
              f"encoder may need a faster preset or lower thread cap)")
    if ret != 0:
        stderr_text = ffmpeg_proc.stderr.read().decode(errors="replace")
        print(f"  WARNING: ffmpeg exited with code {ret} for segment {segment_num}.")
        print(stderr_text[-2000:])

    # ---- Stop audio threads ----
    stop_audio.set()
    for t in audio_threads:
        t.join(timeout=10)

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

    After each segment's frame capture ends, the mux is submitted to a
    background ThreadPoolExecutor and the next segment begins immediately.

    Because mux is now a stream copy + audio encode (seconds, not minutes),
    the previous segment's temp file is deleted almost immediately.  The
    two temp files therefore never coexist for more than a few seconds,
    keeping temp disk usage bounded at ~2-6 GB regardless of session length.
    """
    global is_capturing, last_segment_count, current_segment_num
    global pending_mux_count, _mux_executor, _mux_futures

    splits_enabled = config.get("video_splits", False)
    split_limit    = SPLIT_DURATION if splits_enabled else None

    executor       = concurrent.futures.ThreadPoolExecutor(max_workers=1,
                                                           thread_name_prefix="mux")
    _mux_executor  = executor
    futures: list[concurrent.futures.Future] = []
    _mux_futures   = futures

    segment_num        = 1
    last_segment_count = 0

    # Reuse a single mss context to avoid DXGI re-init overhead between segments.
    with mss.mss() as sct:
        while is_capturing:
            result = _capture_segment(config, segment_num, split_limit, sct)

            if result is None:
                break

            outcome, vid_tmp, lb_wav, mic_wav, final_path = result
            last_segment_count += 1

            with _pending_mux_lock:
                pending_mux_count += 1

            future = executor.submit(
                _mux_and_cleanup, vid_tmp, lb_wav, mic_wav, final_path, config
            )
            futures.append(future)

            if outcome == "split" and is_capturing:
                segment_num += 1
            else:
                break

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

    global _thread_cap
    budget_pct  = config.get("thread_budget", _THREAD_BUDGET_DEFAULT)
    logical     = os.cpu_count() or 2
    _thread_cap = max(1, int(logical * budget_pct / 100))
    cv2.setNumThreads(_thread_cap)
    reserved    = logical - _thread_cap
    print(f"  Thread budget : {budget_pct}%  ->  {_thread_cap} / {logical} core(s) "
          f"({reserved} reserved for OS / game)")

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
    Signal the capture loop to stop, then wait for background mux jobs.
    Mux jobs now complete in seconds (stream copy + AAC), so the wait is brief.
    """
    global is_capturing, capture_thread, _mux_executor

    if not is_capturing:
        print("Not currently capturing.")
        return

    is_capturing = False

    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=15)

    capture_thread = None

    futures_to_wait = list(_mux_futures)
    if futures_to_wait:
        remaining = sum(1 for f in futures_to_wait if not f.done())
        if remaining:
            print(f"  Waiting for {remaining} segment mux job(s) to complete ...")
        for future in futures_to_wait:
            try:
                future.result()
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