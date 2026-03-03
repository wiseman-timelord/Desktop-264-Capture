# scripts/recorder.py
# Video : mss (DXGI Desktop Duplication) -> ffmpeg libx264 (H.264) via stdin pipe
# Audio : pyaudiowpatch WASAPI loopback (system out) + mic (system in)
#         both captured in parallel threads -> WAV written incrementally (streaming)
# Final : ffmpeg stream-copies the in-RAM H.264 + AAC audio -> .mkv / .mp4
#
# ============================================================================
# PIPELINE OVERVIEW
# ============================================================================
#
#  CAPTURE THREAD                        MUX THREAD  (ThreadPoolExecutor)
#  ─────────────────────────────────     ──────────────────────────────────────
#  mss grab → BGR24 bytes                (previous segment RAM buffer / spill)
#      │                                     │
#  [frame queue - bounded, 30 frames]        │  ffmpeg mux:
#      │                                     │   -f h264 -i pipe:0   ← RAM chunks
#  pipe_writer thread → ffmpeg stdin         │   -i loopback.wav      streamed in
#      │                                     │   -i mic.wav           a thread
#  ffmpeg libx264 (real-time)                │   -c:v copy  -c:a aac
#      │                                     │   → Output\file.mkv
#  stdout_reader thread → _VideoBuffer       │
#      ├── in RAM (50% free RAM cap)      RAM buffer freed after mux reads it
#      └── spill to .h264 temp file       (spill file deleted if it existed)
#
# ============================================================================
# WHY NO DISK INTERMEDIATE FOR VIDEO
# ============================================================================
#
# Previous approach (MJPG AVI → background libx264 re-encode):
#   - Temp AVI: 10-20 GB / hour  (uncompressed MJPG at capture quality)
#   - Mux re-encode: 30-60+ minutes on a mid-range CPU
#   - During that 45-min window, the next segment's AVI was ALSO growing on
#     the same temp drive.  When C:\Temp filled, cv2.VideoWriter.write()
#     silently dropped every frame while audio continued.  Result: correct
#     video for ~45 min, last ~15 min frozen per segment, every segment.
#
# This approach:
#   - Video encoded to H.264 in real time via ffmpeg pipe; output buffered in RAM
#   - Typical H.264 size at CRF 22 veryfast: 0.5-4 GB / hour
#   - Mux is stream copy (-c:v copy) + AAC encode: completes in 5-60 seconds
#   - Previous segment's RAM buffer is freed as soon as the mux reads it
#   - No two large temp artifacts ever coexist; disk I/O for video is zero
#     in the normal case
#
# ============================================================================
# MEMORY BUDGET
# ============================================================================
#
# At segment start, free RAM is sampled and the buffer limit is set to:
#   min(free_RAM × 0.50,  _RAM_BUFFER_HARD_CAP_GB)
#
# For 64 GB RAM with ~50 GB free: limit ≈ 25 GB  (a 1-hr segment at CRF 22
# veryfast on 1080p desktop content is typically 0.5-2 GB, well within budget)
#
# If the buffer would overflow (unexpectedly high bitrate, very long segment,
# or low-RAM system) it spills transparently to a .h264 temp file mid-segment
# with no interruption to recording.
#
# ============================================================================
# CPU THREADING
# ============================================================================
#
# _thread_cap (25/50/75 % of logical cores from config) is applied to:
#   - The real-time libx264 capture encoder
#   - The mux-step AAC audio encoder / filter graph
# The remaining percentage is reserved for the OS and the game being recorded.

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

# ===========================================================================
# Module-level state
# ===========================================================================
is_capturing        = False
capture_thread      = None
_pa                 = None       # PyAudio instance – kept alive for the session
last_output_file    = None       # path of most-recently completed segment
last_segment_count  = 0          # segments saved in the last session
capture_start_time  = None       # time.time() when current capture started
current_temp_video  = None       # "RAM" normally; spill path if buffer exceeded
current_segment_num = 1          # 1-based segment counter (live)
_segment_start_time = None       # time.time() when current segment started
_current_video_buf  = None       # Reference to current segment's video buffer (for RAM monitoring)

# ---------------------------------------------------------------------------
# Audio format
# ---------------------------------------------------------------------------
AUDIO_FORMAT = pyaudio.paInt16

# AUDIO_CHUNK is set during init based on available RAM.
AUDIO_CHUNK = 4096  # overridden by _detect_audio_chunk() at init

# ---------------------------------------------------------------------------
# Segment duration
# ---------------------------------------------------------------------------
SPLIT_DURATION = 3600.0  # seconds per segment (1 hour)

# ---------------------------------------------------------------------------
# Frame pipe queue depth
# ---------------------------------------------------------------------------
# Number of raw BGR frames buffered between the grab loop and the ffmpeg
# stdin writer thread.  Each 1080p BGR frame ≈ 6 MB; 30 frames ≈ 180 MB.
# Absorbs short encoder stalls.  If the encoder genuinely falls behind,
# frames are dropped (with a warning) rather than RAM growing unbounded.
_PIPE_QUEUE_DEPTH = 30  # frames

# ---------------------------------------------------------------------------
# RAM buffer limits
# ---------------------------------------------------------------------------
# The encoded H.264 output from the capture ffmpeg process is buffered here
# instead of written to disk.  The limit adapts to available RAM at the
# start of each segment; this is the ceiling regardless of system size.
_RAM_BUFFER_HARD_CAP_GB: float = 16.0   # never allocate more than this for video
_RAM_BUFFER_FRACTION:    float = 0.50   # default fraction of *free* RAM to use

# ---------------------------------------------------------------------------
# CPU thread budget
# ---------------------------------------------------------------------------
_THREAD_BUDGET_DEFAULT = 75
_thread_cap: int = max(1, int((os.cpu_count() or 2) * _THREAD_BUDGET_DEFAULT / 100))

# Mux pipeline ---------------------------------------------------------------
pending_mux_count  = 0
_pending_mux_lock  = threading.Lock()
_mux_executor: concurrent.futures.ThreadPoolExecutor | None = None
_mux_futures: list[concurrent.futures.Future] = []

# CPU info cache -------------------------------------------------------------
_cpu_info: dict | None = None


# ===========================================================================
# Adaptive in-RAM video buffer with transparent disk spill
# ===========================================================================
class _VideoBuffer:
    """
    Buffers encoded H.264 bytes from ffmpeg's stdout in a list of byte chunks.

    As long as total size stays under `max_bytes`, all data lives in RAM.
    If the budget would be exceeded the buffer spills transparently to
    `spill_path` on disk for the remainder of the segment.  Recording is
    never interrupted during a spill transition.

    After the mux step reads the buffer it should call `discard()` to free
    RAM (in-RAM path) or delete the spill file (disk path).
    """

    def __init__(self, max_bytes: int, spill_path: str):
        self._max         = max_bytes
        self._spill_path  = spill_path
        self._chunks: list[bytes] = []
        self._size        = 0
        self._spill_file  = None
        self._spilled     = False

    # ---- write (called from stdout_reader thread) -------------------------
    def write(self, data: bytes) -> None:
        if self._spilled:
            self._spill_file.write(data)
            return

        if self._size + len(data) > self._max:
            # Transition to disk spill.
            self._spill_file = open(self._spill_path, "wb")
            for chunk in self._chunks:
                self._spill_file.write(chunk)
            self._spill_file.write(data)
            self._chunks = []       # free RAM immediately
            self._size   = 0
            self._spilled = True
            print(f"  _VideoBuffer: RAM limit reached – spilling to disk "
                  f"({self._spill_path})")
        else:
            self._chunks.append(data)
            self._size += len(data)

    def close(self) -> None:
        """Flush and close the spill file if open (call after stdout closes)."""
        if self._spill_file is not None:
            try:
                self._spill_file.flush()
                self._spill_file.close()
            except OSError:
                pass
            self._spill_file = None

    # ---- properties -------------------------------------------------------
    @property
    def spilled(self) -> bool:
        return self._spilled

    @property
    def spill_path(self) -> str:
        return self._spill_path

    @property
    def ram_size_mb(self) -> float:
        return self._size / (1024 * 1024)

    # ---- iteration (in-RAM path only) ------------------------------------
    def iter_chunks(self):
        """Yield in-RAM bytes chunks.  Only valid when spilled is False."""
        yield from self._chunks

    # ---- cleanup ---------------------------------------------------------
    def discard(self) -> None:
        """Free RAM / delete spill file.  Safe to call multiple times."""
        self._chunks = []
        self._size   = 0
        if self._spill_file is not None:
            try:
                self._spill_file.close()
            except OSError:
                pass
            self._spill_file = None
        if self._spilled and os.path.exists(self._spill_path):
            try:
                os.remove(self._spill_path)
            except OSError:
                pass
        self._spilled = False


# ===========================================================================
# RAM detection
# ===========================================================================
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


def _calc_buffer_limit(config: dict | None = None) -> int:
    """
    Return the maximum bytes the in-RAM video buffer may use for this segment.
    Samples current free RAM each time so successive segments adapt if memory
    pressure changes (e.g. the game loads a large level between segments).
    Uses the max_ram_usage config setting if available.
    """
    if config is not None:
        fraction = config.get("max_ram_usage", 50) / 100.0
    else:
        fraction = _RAM_BUFFER_FRACTION
    free_gb   = _get_available_ram_gb()
    budget_gb = min(free_gb * fraction, _RAM_BUFFER_HARD_CAP_GB)
    # Floor: at least 512 MB so the buffer is useful even on low-RAM systems.
    budget_gb = max(budget_gb, 0.5)
    return int(budget_gb * (1024 ** 3))


# ===========================================================================
# CPU feature detection
# ===========================================================================
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
        "name":           "Unknown",
        "logical_cores":   os.cpu_count() or 1,
        "avx":            False,
        "avx2":           False,
        "avx512f":        False,
        "sse2":           False,
        "numpy_threads":   1,
        "thread_cap":     _thread_cap,
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


# ===========================================================================
# Initialisation
# ===========================================================================
def init_capture_system(config: dict | None = None) -> bool:
    """Verify all runtime deps, choose buffer sizes, open PyAudio. Returns True on success."""
    global _pa, AUDIO_CHUNK, _thread_cap

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

    # Apply thread budget from config so the correct value is used from the start
    # (start_capture() will re-apply it again when recording begins, which is fine).
    if config is not None:
        budget_pct  = config.get("thread_budget", _THREAD_BUDGET_DEFAULT)
        logical     = os.cpu_count() or 2
        _thread_cap = max(1, int(logical * budget_pct / 100))

    AUDIO_CHUNK = _detect_audio_chunk()
    cv2.setNumThreads(_thread_cap)

    ci     = get_cpu_info()
    _pa    = pyaudio.PyAudio()

    simd = []
    if ci["sse2"]:    simd.append("SSE2")
    if ci["avx"]:     simd.append("AVX")
    if ci["avx2"]:    simd.append("AVX2")
    if ci["avx512f"]: simd.append("AVX-512F")
    simd_str = ", ".join(simd) if simd else "none detected"

    ram_gb      = _get_available_ram_gb()
    buf_limit   = _calc_buffer_limit(config)
    ram_pct     = config.get("max_ram_usage", int(_RAM_BUFFER_FRACTION * 100)) \
                  if config is not None else int(_RAM_BUFFER_FRACTION * 100)
    print(f"Capture system initialised  (mss + ffmpeg libx264 pipe + RAM buffer).")
    print(f"  CPU          : {ci['name']}")
    print(f"  Logical CPUs : {ci['logical_cores']}   SIMD: {simd_str}")
    print(f"  Thread cap   : {_thread_cap} core(s)  ({config.get('thread_budget', _THREAD_BUDGET_DEFAULT)}% budget)")
    print(f"  Free RAM     : {ram_gb:.1f} GB   "
          f"Video buffer cap: {buf_limit / (1024**3):.1f} GB  "
          f"({ram_pct}% of free, max {_RAM_BUFFER_HARD_CAP_GB:.0f} GB)")
    print(f"  Audio chunk  : {AUDIO_CHUNK} frames")
    return True


# ===========================================================================
# Audio device helpers
# ===========================================================================
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


# ===========================================================================
# Audio capture thread  —  STREAMING WAV WRITE (O(1) RAM)
# ===========================================================================
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


# ===========================================================================
# ffmpeg mux  —  stream-copy video, encode audio only
# ===========================================================================
def _mux(video_buf: "_VideoBuffer", loopback_wav, mic_wav,
         output_path: str, config: dict):
    """
    Mux pre-encoded H.264 (from _VideoBuffer) with up to two WAV audio sources.

    VIDEO IS STREAM-COPIED (-c:v copy).
      - In-RAM path : video bytes are streamed from the chunk list to ffmpeg
                      stdin via a dedicated feeder thread.
      - Spill path  : video is read from the spill .h264 file on disk.
    Either way, no libx264 re-encode happens here.

    Mux time: 5-60 seconds (AAC audio encode + container remux only).
    After ffmpeg finishes reading, video_buf.discard() frees RAM / deletes the
    spill file so the previous segment's storage is reclaimed immediately.
    """
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd    = [ffmpeg, "-y",
              "-threads", str(_thread_cap)]

    # ---- video input -------------------------------------------------------
    if video_buf.spilled:
        # Spill file on disk – feed as a normal path input.
        cmd += ["-f", "h264", "-i", video_buf.spill_path]
        feeder_thread = None
    else:
        # In-RAM chunks – pipe to ffmpeg stdin.
        cmd += ["-f", "h264", "-i", "pipe:0"]
        feeder_thread = None      # created after Popen below

    # ---- audio inputs ------------------------------------------------------
    audio_src_indices = []
    for wav in (loopback_wav, mic_wav):
        if wav and os.path.exists(wav) and os.path.getsize(wav) > 44:
            cmd += ["-i", wav]
            audio_src_indices.append(len(audio_src_indices) + 1)

    # ---- stream-copy video; encode audio -----------------------------------
    cmd += ["-c:v", "copy"]

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

    src_desc = (f"spill:{os.path.basename(video_buf.spill_path)}"
                if video_buf.spilled
                else f"RAM:{video_buf.ram_size_mb:.0f} MB")
    print(f"Muxing (BG)  -> {os.path.basename(output_path)}"
          f"  [stream copy + AAC, src={src_desc}, "
          f"threads={_thread_cap}/{os.cpu_count() or 2}]")

    stdin_pipe = subprocess.PIPE if not video_buf.spilled else None

    proc = subprocess.Popen(
        cmd,
        stdin  = stdin_pipe,
        stdout = subprocess.DEVNULL,
        stderr = subprocess.PIPE,
    )

    # ---- stderr drainer thread ---------------------------------------------
    # CRITICAL: ffmpeg writes progress stats to stderr continuously.
    # If stderr is piped but never read, the 64 KB OS pipe buffer fills and
    # ffmpeg blocks trying to write more output.  proc.wait() then waits for
    # ffmpeg to exit, ffmpeg never exits → deadlock.
    # This thread drains stderr into a list so it is always available for
    # error reporting without ever blocking ffmpeg.
    _stderr_buf: list[bytes] = []

    def _stderr_drainer():
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                _stderr_buf.append(chunk)
        except OSError:
            pass

    stderr_thread = threading.Thread(target=_stderr_drainer, daemon=True,
                                      name="mux-stderr")
    stderr_thread.start()

    # ---- RAM feeder thread -------------------------------------------------
    # Streams in-RAM chunks to ffmpeg's stdin without blocking the caller.
    # Runs as a daemon thread; closes stdin when done so ffmpeg knows EOF.
    def _feed_stdin():
        try:
            for chunk in video_buf.iter_chunks():
                proc.stdin.write(chunk)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            try:
                proc.stdin.close()
            except OSError:
                pass

    if not video_buf.spilled:
        feeder_thread = threading.Thread(target=_feed_stdin, daemon=True,
                                         name="mux-feeder")
        feeder_thread.start()

    ret = proc.wait()

    if feeder_thread is not None:
        feeder_thread.join(timeout=30)

    # stderr drainer should be done since ffmpeg has exited; short join.
    stderr_thread.join(timeout=10)

    # Free RAM / delete spill file now that ffmpeg has consumed the buffer.
    video_buf.discard()

    if ret != 0:
        stderr_text = b"".join(_stderr_buf).decode(errors="replace")
        print(f"WARNING: ffmpeg mux failed for {os.path.basename(output_path)}.")
        print(stderr_text[-2000:])


# ===========================================================================
# Background mux-and-cleanup task
# ===========================================================================
def _mux_and_cleanup(video_buf: "_VideoBuffer",
                     lb_wav: str | None, mic_wav: str | None,
                     final_path: str, config: dict):
    """
    Runs in a ThreadPoolExecutor worker.
    1. Mux H.264 buffer + audio WAVs -> final_path  (stream copy, seconds).
    2. _mux() calls video_buf.discard() on completion  -> RAM freed.
    3. Delete audio WAV temp files.
    4. Update shared globals.
    """
    global last_output_file, pending_mux_count

    try:
        _mux(video_buf, lb_wav, mic_wav, final_path, config)
    finally:
        for p in filter(None, (lb_wav, mic_wav)):
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

# ===========================================================================
# Segment capture  (inner)
# ===========================================================================
def _capture_segment(config: dict, segment_num: int,
                     split_limit: float | None,
                     sct: mss.base.MSSBase
                     ) -> tuple | None:
    """
    Capture one segment of frames and encode them in real-time via an ffmpeg
    stdin pipe.  Encoded H.264 output is buffered in RAM (_VideoBuffer) rather
    than written to disk.

    Pipeline:
        mss grab -> cv2 BGRA->BGR -> [frame queue, 30 frames]
        -> pipe_writer thread -> ffmpeg stdin (rawvideo)
        -> libx264 real-time encoder
        -> ffmpeg stdout -> stdout_reader thread -> _VideoBuffer (RAM / spill)

    The pipe_writer and stdout_reader threads run concurrently so neither the
    grab loop nor the encoder ever blocks waiting for the other.

    Returns:
        (outcome, video_buf, lb_wav_or_None, mic_wav_or_None, final_path)
        outcome: "split" | "done"
    Returns None on a fatal ffmpeg startup error.
    """
    import imageio_ffmpeg

    global current_temp_video, _segment_start_time, current_segment_num
    global _current_video_buf

    current_segment_num = segment_num

    w       = config["resolution"]["width"]
    h       = config["resolution"]["height"]
    fps     = config["fps"]
    out_dir = config["output_path"]
    os.makedirs(out_dir, exist_ok=True)

    # Audio WAV paths still go to temp dir (audio is tiny: ~100 MB / hr).
    stamp   = int(time.time())
    tmp_dir = tempfile.gettempdir()
    lb_wav  = os.path.join(tmp_dir, f"d264_loopback_{stamp}_s{segment_num:03d}.wav")
    mic_wav = os.path.join(tmp_dir, f"d264_mic_{stamp}_s{segment_num:03d}.wav")

    # Spill path is only used if the RAM buffer overflows.
    spill_path = os.path.join(tmp_dir, f"d264_spill_{stamp}_s{segment_num:03d}.h264")

    # Determine final output path.
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

    # Adaptive RAM buffer limit for this segment.
    buf_limit  = _calc_buffer_limit(config)
    video_buf  = _VideoBuffer(max_bytes=buf_limit, spill_path=spill_path)
    _current_video_buf = video_buf  # Make accessible for RAM monitoring in displays.py

    # current_temp_video shows "RAM" in the monitor display; if spilled the
    # display will still show "RAM" (the spill is an implementation detail).
    current_temp_video = "(RAM buffer)"

    # ---- Identify audio devices ----
    loopback_info = _get_loopback_device(_pa)
    mic_info      = _get_default_mic(_pa)

    if segment_num == 1:
        ram_frac_pct = config.get("max_ram_usage", 50)
        print(f"  Video buffer : {buf_limit / (1024**3):.1f} GB cap "
              f"({ram_frac_pct}% of {_get_available_ram_gb():.1f} GB free RAM, "
              f"max {_RAM_BUFFER_HARD_CAP_GB:.0f} GB)")
        if loopback_info:
            print(f"  System audio : {loopback_info['name']}")
        else:
            print("  System audio : unavailable")
        if mic_info:
            print(f"  Microphone   : {mic_info['name']}")
        else:
            print("  Microphone   : unavailable")

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

    # ---- Launch ffmpeg: rawvideo -> libx264 -> raw H.264 on stdout --------
    #
    # Output format is raw H.264 Annex B (-f h264) because:
    #   a) It does not require seeking to write a container header, so the
    #      stream can start immediately and be buffered linearly in RAM.
    #   b) ffmpeg's mux step reads it back with -f h264 -i pipe:0 (or file),
    #      which also doesn't require seeking.  -c:v copy then just rewraps
    #      the already-encoded stream into MKV/MP4.
    #
    # -thread_queue_size 512 : ffmpeg input demuxer read-ahead buffer;
    #                          decouples I/O from the encoder thread pool.
    # -an                    : no audio here; audio is added at mux time.
    ffmpeg_exe   = imageio_ffmpeg.get_ffmpeg_exe()
    video_params = configure.get_video_params(config)

    ffmpeg_cmd = [
        ffmpeg_exe, "-y",
        "-f",                "rawvideo",
        "-vcodec",           "rawvideo",
        "-s",                f"{w}x{h}",
        "-pix_fmt",          "bgr24",
        "-r",                str(fps),
        "-thread_queue_size", "512",
        "-i",                "pipe:0",
        "-c:v",              "libx264",
        "-threads",          str(_thread_cap),
    ] + video_params + [
        "-an",
        "-f", "h264",
        "pipe:1",           # encoded H.264 -> Python's stdout read loop
    ]

    try:
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin  = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )
    except OSError as e:
        print(f"ERROR: could not launch ffmpeg for segment {segment_num}: {e}")
        video_buf.discard()
        _current_video_buf = None  # Clear reference on error
        stop_audio.set()
        for t in audio_threads:
            t.join(timeout=5)
        current_temp_video = None
        return None

    # ---- stderr drainer thread --------------------------------------------
    # CRITICAL: ffmpeg writes progress stats to stderr continuously.
    # If stderr is piped but never read, the 64 KB OS pipe buffer fills and
    # ffmpeg blocks trying to write more output.  wait() then waits for ffmpeg
    # to exit, ffmpeg never exits → deadlock → 120 s timeout → killed process.
    # This thread drains stderr into a list so it is always available for
    # error reporting without ever blocking ffmpeg.
    _stderr_buf: list[bytes] = []

    def _stderr_drainer():
        try:
            while True:
                chunk = ffmpeg_proc.stderr.read(4096)
                if not chunk:
                    break
                _stderr_buf.append(chunk)
        except OSError:
            pass

    stderr_thread = threading.Thread(target=_stderr_drainer, daemon=True,
                                     name=f"stderr-s{segment_num}")
    stderr_thread.start()

    # ---- stdout reader thread ---------------------------------------------
    # Reads encoded H.264 bytes from ffmpeg's stdout into the video_buf.
    # Must run concurrently with the grab loop; if this thread stalls,
    # the stdout pipe fills and ffmpeg blocks, which would starve the encoder.
    _STDOUT_READ_SIZE = 256 * 1024   # 256 KB per read – balances latency/overhead

    def _stdout_reader():
        try:
            while True:
                chunk = ffmpeg_proc.stdout.read(_STDOUT_READ_SIZE)
                if not chunk:
                    break
                video_buf.write(chunk)
        except OSError:
            pass
        finally:
            video_buf.close()

    stdout_thread = threading.Thread(target=_stdout_reader, daemon=True,
                                     name=f"stdout-s{segment_num}")
    stdout_thread.start()

    # ---- pipe writer thread -----------------------------------------------
    # Writes raw BGR frames from the bounded queue to ffmpeg's stdin.
    frame_q = _queue.Queue(maxsize=_PIPE_QUEUE_DEPTH)

    def _pipe_writer():
        while True:
            item = frame_q.get()
            if item is None:
                break
            try:
                ffmpeg_proc.stdin.write(item)
            except (BrokenPipeError, OSError):
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
    monitor              = sct.monitors[1]   # re-queried each segment

    # ---- Frame grab loop --------------------------------------------------
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

        # tobytes() produces a safe copy (mss may reuse its internal buffer).
        # Non-blocking put: drop frame rather than stall the grab timer.
        try:
            frame_q.put_nowait(bgr.tobytes())
        except _queue.Full:
            frames_dropped += 1

        next_tick += frame_dur

    # ---- Flush and close stdin -------------------------------------------
    frame_q.put(None)           # sentinel: tells pipe_writer to exit
    pipe_thread.join(timeout=60)

    try:
        ffmpeg_proc.stdin.close()
    except OSError:
        pass

    # Wait for ffmpeg to flush encoder buffers.  With zerolatency tune the
    # flush is near-instant; 120 s is a generous safety margin.
    try:
        ret = ffmpeg_proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        ffmpeg_proc.kill()
        ret = ffmpeg_proc.wait()
        print(f"  WARNING: ffmpeg timed out flushing segment {segment_num}; process killed.")

    # stdout_reader exits when stdout closes (which happens after ffmpeg exits)
    stdout_thread.join(timeout=30)

    # stderr_drainer should already be done since ffmpeg has exited; short join.
    stderr_thread.join(timeout=10)

    if frames_dropped:
        print(f"  Warning: {frames_dropped} frame(s) dropped "
              f"(pipe queue full – encoder may need faster preset or lower thread cap)")
    if ret != 0:
        stderr_text = b"".join(_stderr_buf).decode(errors="replace")
        print(f"  WARNING: ffmpeg exited with code {ret} for segment {segment_num}.")
        print(stderr_text[-2000:])

    if video_buf.spilled:
        print(f"  Note: segment {segment_num} spilled to disk "
              f"({video_buf.spill_path}) – RAM cap was reached.")

    # ---- Stop audio -------------------------------------------------------
    stop_audio.set()
    for t in audio_threads:
        t.join(timeout=10)

    actual_lb_wav  = lb_wav  if (loopback_info and os.path.exists(lb_wav))  else None
    actual_mic_wav = mic_wav if (mic_info      and os.path.exists(mic_wav)) else None

    current_temp_video  = None
    _segment_start_time = None
    _current_video_buf  = None  # Clear reference when segment completes

    return result, video_buf, actual_lb_wav, actual_mic_wav, final

# ===========================================================================
# Main capture loop  (outer – manages segment pipeline)
# ===========================================================================
def _capture_loop(config: dict):
    """
    Outer loop managing multi-segment capture with a pipelined mux.

    Memory lifecycle per segment:
      1. _capture_segment() fills a _VideoBuffer in RAM (or spill file).
      2. _mux_and_cleanup() is submitted to the background executor;
         it reads the buffer (seconds), calls discard() immediately on
         completion, then encodes audio and finalises the container.
      3. By the time the next segment's buffer begins filling, the previous
         segment's RAM has already been freed.  At steady state, only one
         segment's worth of encoded video occupies RAM at any given moment.
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

    # Reuse a single mss context to avoid DXGI re-init overhead.
    with mss.mss() as sct:
        while is_capturing:
            result = _capture_segment(config, segment_num, split_limit, sct)

            if result is None:
                break

            outcome, video_buf, lb_wav, mic_wav, final_path = result
            last_segment_count += 1

            with _pending_mux_lock:
                pending_mux_count += 1

            future = executor.submit(
                _mux_and_cleanup, video_buf, lb_wav, mic_wav, final_path, config
            )
            futures.append(future)

            if outcome == "split" and is_capturing:
                segment_num += 1
                # The new segment's _VideoBuffer is allocated fresh in
                # _capture_segment before the old one has been freed.
                # Peak RAM: current segment buffer + previous segment buffer.
                # _calc_buffer_limit() samples free RAM at segment start,
                # so if the previous buffer is still being read by the mux
                # (unlikely given stream-copy speed but possible on slow
                # storage for the output file), the new limit is reduced
                # accordingly.
            else:
                break

    # _capture_loop owns the executor it created; shut it down here so that
    # stop_capture() cannot race executor.submit() by shutting the executor
    # down from a different thread while this loop might still be submitting.
    # shutdown(wait=False) means "stop accepting new futures but let any
    # already-submitted futures run to completion."
    executor.shutdown(wait=False)
    _mux_executor = None

    current_segment_num = 1


# ===========================================================================
# Public API  (called by launcher.py / displays.py)
# ===========================================================================
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
    Signal the capture loop to stop, then wait for all work to complete.

    Sequence:
      1. Set is_capturing = False  -> grab loop exits on next iteration.
      2. Join capture thread (up to 60 s).  With the stderr drainer fix the
         ffmpeg flush is near-instant; 60 s is a generous safety margin.
         The executor is shut down by _capture_loop itself when it exits,
         so there is no race between this join and executor.submit().
      3. Wait for any already-submitted mux futures.  These are fast
         (stream copy + AAC); they may already be done by the time we get here.
    """
    global is_capturing, capture_thread, _mux_executor

    if not is_capturing:
        print("Not currently capturing.")
        return

    is_capturing = False

    # Wait for the capture thread to finish.  It exits once the grab loop
    # stops, ffmpeg flushes (fast with stderr drainer), and _capture_loop
    # shuts down the executor.  60 s covers any edge-case encoder flush.
    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=60)

    capture_thread = None

    # Wait for any in-flight mux futures.  The executor is already shut down
    # (or being shut down) by _capture_loop; we just need the results.
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

    # Executor is owned and shut down by _capture_loop.  If for any reason
    # it was not cleaned up there (e.g. fatal exception in the loop), do it now.
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