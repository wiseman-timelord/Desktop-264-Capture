# scripts/recorder.py - Core recording functionality using ctypes to interface
# with NVIDIA's NvFBC API.  Updated for driver 399.07 (uses NvFBCCreateEx).
# FALL-BACK: if NvFBCPlugin.dll is missing we grab the desktop with d3dshot
# and feed the same BGRA frame into PyAV + NVENC.

import ctypes
import os
import threading
import time
import numpy as np  # <- needed for fast numpy-array wrapper
from ctypes import c_void_p, c_int, c_uint32, POINTER, Structure
import av

# ---------- Platform-specific DLL loading ----------
if os.name == 'nt':
    WinDLL = ctypes.WinDLL
    WINFUNCTYPE = ctypes.WINFUNCTYPE
else:
    WinDLL = None
    WINFUNCTYPE = ctypes.CFUNCTYPE  # placeholder

# ---------- Constants ----------
NVFBC_API_VERSION = 0x10001
NVFBC_CAPTURE_TO_SYS = 0x1
NVFBC_GRAB_FRAME_FLAGS_NO_WAIT = 0x1

NVFBC_SUCCESS = 0
NVFBC_ERR_INVALID_PARAM = -2
NVFBC_ERR_API_VERSION = -3
NVFBC_ERR_UNSUPPORTED = -5

# ---------- Structures ----------
class NVFBC_CREATE_HANDLE_EX_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("dwFlags", c_uint32),
        ("pDevice", c_void_p),
        ("pPrivateData", c_void_p),
    ]


class NVFBC_GET_STATUS_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("bIsCapturePossible", c_int),
        ("bCurrentlyCapturing", c_int),
        ("dwAdapterIdx", c_uint32),
    ]


class NVFBC_CREATE_CAPTURE_SESSION_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("eCaptureType", c_int),
        ("dwAdapterIdx", c_uint32),
        ("eBufferFormat", c_int),
        ("dwWidth", c_uint32),
        ("dwHeight", c_uint32),
        ("dwSamplingRate", c_uint32),
        ("bWithCursor", c_int),
    ]


class NVFBC_DESTROY_CAPTURE_SESSION_PARAMS(Structure):
    _fields_ = [("dwVersion", c_uint32)]


class NVFBC_FRAME_GRAB_INFO(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("dwWidth", c_uint32),
        ("dwHeight", c_uint32),
        ("dwByteSize", c_uint32),
        ("pFrameBuffer", c_void_p),
    ]


class NVFBC_GRAB_FRAME_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("dwFlags", c_uint32),
        ("pFrameGrabInfo", POINTER(NVFBC_FRAME_GRAB_INFO)),
    ]


# ---------- DLL loading ----------
def find_nvfbc_dll():
    if os.name == 'nt':
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        dll_path = os.path.join(pf, "NVIDIA Corporation", "NvFBC", "NvFBCPlugin.dll")
        return dll_path if os.path.exists(dll_path) else None
    return None


# ---------- Function prototypes ----------
nvfbc = None
if WinDLL:
    try:
        dll_path = find_nvfbc_dll()
        nvfbc = WinDLL(dll_path) if dll_path else WinDLL("NvFBCPlugin.dll")

        NvFBCCreateEx_proto = WINFUNCTYPE(
            c_int, POINTER(NVFBC_CREATE_HANDLE_EX_PARAMS), POINTER(c_void_p)
        )
        NvFBCCreateEx = NvFBCCreateEx_proto(("NvFBCCreateEx", nvfbc))

        NvFBCDestroyInstance_proto = WINFUNCTYPE(c_int, c_void_p)
        NvFBCDestroyInstance = NvFBCDestroyInstance_proto(
            ("NvFBCDestroyInstance", nvfbc)
        )

        _NvFBCGetStatus = nvfbc.NvFBCGetStatus
        _NvFBCGetStatus.argtypes = [c_void_p, POINTER(NVFBC_GET_STATUS_PARAMS)]
        _NvFBCGetStatus.restype = c_int

        _NvFBCCreateCaptureSession = nvfbc.NvFBCCreateCaptureSession
        _NvFBCCreateCaptureSession.argtypes = [
            c_void_p,
            POINTER(NVFBC_CREATE_CAPTURE_SESSION_PARAMS),
        ]
        _NvFBCCreateCaptureSession.restype = c_int

        _NvFBCDestroyCaptureSession = nvfbc.NvFBCDestroyCaptureSession
        _NvFBCDestroyCaptureSession.argtypes = [
            c_void_p,
            POINTER(NVFBC_DESTROY_CAPTURE_SESSION_PARAMS),
        ]
        _NvFBCDestroyCaptureSession.restype = c_int

        _NvFBCCaptureFrame = nvfbc.NvFBCCaptureFrame
        _NvFBCCaptureFrame.argtypes = [c_void_p, POINTER(NVFBC_GRAB_FRAME_PARAMS)]
        _NvFBCCaptureFrame.restype = c_int

    except OSError:
        nvfbc = None

# ---------- Globals ----------
session_handle = c_void_p()
is_capturing = False
capture_thread = None
NVFBC_AVAILABLE = bool(nvfbc)  # simple flag


# ---------- API helpers ----------
def init_nvidia_apis():
    global session_handle
    if not NVFBC_AVAILABLE:
        print("NvFBC not available on this system.")
        return False

    params = NVFBC_CREATE_HANDLE_EX_PARAMS()
    params.dwVersion = NVFBC_API_VERSION
    params.dwFlags = 0
    params.pDevice = None
    params.pPrivateData = None

    status = NvFBCCreateEx(ctypes.byref(params), ctypes.byref(session_handle))
    if status != NVFBC_SUCCESS:
        print(f"Failed to create NvFBC instance. Status: {status}")
        return False

    print("NvFBC instance created successfully.")
    return True


# ---------- frame-grab helpers ----------
def grab_frame_nvfbc(width: int, height: int):
    """Return BGRA numpy array (H,W,4) or None if grab failed."""
    grab_params = NVFBC_GRAB_FRAME_PARAMS()
    grab_params.dwVersion = NVFBC_API_VERSION
    grab_params.dwFlags = NVFBC_GRAB_FRAME_FLAGS_NO_WAIT

    frame_info = NVFBC_FRAME_GRAB_INFO()
    frame_info.dwVersion = NVFBC_API_VERSION
    grab_params.pFrameGrabInfo = ctypes.byref(frame_info)

    status = _NvFBCCaptureFrame(session_handle, ctypes.byref(grab_params))
    if status != NVFBC_SUCCESS:
        return None

    data = ctypes.string_at(frame_info.pFrameBuffer, frame_info.dwByteSize)
    return np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))


def grab_frame_d3dshot(width: int, height: int):
    """BGRA numpy array via Desktop Duplication (d3dshot)."""
    import d3dshot

    if not hasattr(grab_frame_d3dshot, "d"):
        grab_frame_d3dshot.d = d3dshot.create(capture_output="numpy")
        grab_frame_d3dshot.d.capture(target_fps=60)

    frame = grab_frame_d3dshot.d.get_latest_frame()
    if frame is None:
        return None
    # ensure correct shape
    if frame.shape[2] == 4:
        return frame
    if frame.shape[2] == 3:
        return np.dstack([frame, np.full(frame.shape[:2], 255, dtype=np.uint8)])
    raise RuntimeError("Unexpected frame format")


# ---------- Capture loop ----------
def capture_loop(config):
    global is_capturing

    output_filename = os.path.join(
        config["output_path"], f"capture-{int(time.time())}.mp4"
    )

    # choose grabber once
    grab_frame = grab_frame_nvfbc if NVFBC_AVAILABLE else grab_frame_d3dshot
    w, h = config["resolution"]["width"], config["resolution"]["height"]

    with av.open(output_filename, mode="w") as container:
        stream = container.add_stream(config["codec"], rate=config["fps"])
        stream.width, stream.height = w, h
        stream.pix_fmt = "yuv420p"

        while is_capturing:
            frame_bgra = grab_frame(w, h)
            if frame_bgra is None:
                time.sleep(0.001)
                continue

            av_frame = av.VideoFrame.from_ndarray(frame_bgra, format="bgra")
            for packet in stream.encode(av_frame):
                container.mux(packet)

            time.sleep(1.0 / config["fps"])

        # flush encoder
        for packet in stream.encode():
            container.mux(packet)


# ---------- Session control ----------
def start_capture(config):
    global is_capturing, capture_thread
    if not session_handle and NVFBC_AVAILABLE:
        print("NvFBC instance not created.")
        return
    if not NVFBC_AVAILABLE:
        # d3dshot path needs no session
        is_capturing = True
        capture_thread = threading.Thread(target=capture_loop, args=(config,))
        capture_thread.start()
        print("Capture thread started (Desktop Duplication).")
        return

    params = NVFBC_CREATE_CAPTURE_SESSION_PARAMS()
    params.dwVersion = NVFBC_API_VERSION
    params.eCaptureType = NVFBC_CAPTURE_TO_SYS
    params.dwAdapterIdx = 0
    params.eBufferFormat = 0  # ARGB
    params.dwWidth = config["resolution"]["width"]
    params.dwHeight = config["resolution"]["height"]
    params.dwSamplingRate = config["fps"]
    params.bWithCursor = 1

    status = _NvFBCCreateCaptureSession(session_handle, ctypes.byref(params))
    if status != NVFBC_SUCCESS:
        print(f"Failed to create capture session. Status: {status}")
    else:
        print("Capture session created successfully.")
        is_capturing = True
        capture_thread = threading.Thread(target=capture_loop, args=(config,))
        capture_thread.start()


def stop_capture():
    global is_capturing, capture_thread
    if not NVFBC_AVAILABLE:
        if is_capturing:
            is_capturing = False
            capture_thread.join()
        print("Desktop-duplication capture stopped.")
        return
    if not session_handle:
        print("NvFBC instance not created.")
        return

    if is_capturing:
        is_capturing = False
        capture_thread.join()

    params = NVFBC_DESTROY_CAPTURE_SESSION_PARAMS()
    params.dwVersion = NVFBC_API_VERSION
    status = _NvFBCDestroyCaptureSession(session_handle, ctypes.byref(params))
    if status != NVFBC_SUCCESS:
        print(f"Failed to destroy capture session. Status: {status}")
    else:
        print("Capture session destroyed successfully.")


def cleanup():
    if NVFBC_AVAILABLE and session_handle:
        NvFBCDestroyInstance(session_handle)
        print("NvFBC instance destroyed.")
    if hasattr(grab_frame_d3dshot, "d"):
        grab_frame_d3dshot.d.stop()
        print("d3dshot stopped.")