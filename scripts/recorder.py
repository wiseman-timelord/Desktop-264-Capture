# scripts/recorder.py - Core recording functionality using ctypes to interface with NVIDIA's NvFBC API.

import ctypes
import os
import threading
import time
from ctypes import c_void_p, c_int, c_uint32, c_char_p, POINTER, Structure
import av

# Platform-specific DLL loading. This application is designed for Windows.
if os.name == 'nt':
    WinDLL = ctypes.WinDLL
    WINFUNCTYPE = ctypes.WINFUNCTYPE
else:
    WinDLL = None
    WINFUNCTYPE = ctypes.CFUNCTYPE  # Placeholder for non-Windows environments.

# --- NvFBC API Definitions based on NvFBC.h ---
# This section translates the C header file (NvFBC.h) into Python ctypes definitions.
# This allows Python to call functions in the native NvFBC64.dll.

# Constants
NVFBC_API_VERSION = 0x10001
NVFBC_CAPTURE_TO_SYS = 0x1  # Capture to system memory.
NVFBC_GRAB_FRAME_FLAGS_NO_WAIT = 0x1

# Enums (simplified for clarity)
NVFBC_SUCCESS = 0
NVFBC_ERR_INVALID_PARAM = -2
NVFBC_ERR_API_VERSION = -3
NVFBC_ERR_UNSUPPORTED = -5

# Structures - These Python classes mirror the C structures used by the NvFBC API.
class NVFBC_CREATE_HANDLE_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
        ("pDevice", c_void_p),
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
        ("eBufferFormat", c_int), # Note: The ideal buffer format may need to be determined experimentally.
        ("dwWidth", c_uint32),
        ("dwHeight", c_uint32),
        ("dwSamplingRate", c_uint32),
        ("bWithCursor", c_int),
    ]

class NVFBC_DESTROY_CAPTURE_SESSION_PARAMS(Structure):
    _fields_ = [
        ("dwVersion", c_uint32),
    ]

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

def find_nvfbc_dll():
    """
    Finds the NvFBC DLL in the standard NVIDIA installation directory.
    Returns the path to the DLL if found, otherwise returns None.
    """
    if os.name == 'nt':
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        dll_path = os.path.join(program_files, "NVIDIA Corporation", "NvFBC", "NvFBCPlugin.dll")
        if os.path.exists(dll_path):
            return dll_path
    return None

# Function Prototypes - This section defines the signatures of the NvFBC API functions.
if WinDLL:
    try:
        dll_path = find_nvfbc_dll()
        if dll_path:
            nvfbc = WinDLL(dll_path)
        else:
            # Fallback to searching the system's PATH
            nvfbc = WinDLL("NvFBCPlugin.dll")

        # NvFBCCreateInstance - Creates an NvFBC API instance.
        NvFBCCreateInstance_proto = WINFUNCTYPE(c_int, POINTER(c_void_p))
        NvFBCCreateInstance = NvFBCCreateInstance_proto(("NvFBCCreateInstance", nvfbc))

        # NvFBCDestroyInstance - Destroys an NvFBC API instance.
        NvFBCDestroyInstance_proto = WINFUNCTYPE(c_int, c_void_p)
        NvFBCDestroyInstance = NvFBCDestroyInstance_proto(("NvFBCDestroyInstance", nvfbc))

        # NvFBCGetStatus - Retrieves the status of the NvFBC API.
        _NvFBCGetStatus = nvfbc.NvFBCGetStatus
        _NvFBCGetStatus.argtypes = [c_void_p, POINTER(NVFBC_GET_STATUS_PARAMS)]
        _NvFBCGetStatus.restype = c_int

        # NvFBCCreateCaptureSession - Creates a capture session.
        _NvFBCCreateCaptureSession = nvfbc.NvFBCCreateCaptureSession
        _NvFBCCreateCaptureSession.argtypes = [c_void_p, POINTER(NVFBC_CREATE_CAPTURE_SESSION_PARAMS)]
        _NvFBCCreateCaptureSession.restype = c_int

        # NvFBCDestroyCaptureSession - Destroys a capture session.
        _NvFBCDestroyCaptureSession = nvfbc.NvFBCDestroyCaptureSession
        _NvFBCDestroyCaptureSession.argtypes = [c_void_p, POINTER(NVFBC_DESTROY_CAPTURE_SESSION_PARAMS)]
        _NvFBCDestroyCaptureSession.restype = c_int

        # NvFBCCaptureFrame - Captures a single frame.
        _NvFBCCaptureFrame = nvfbc.NvFBCCaptureFrame
        _NvFBCCaptureFrame.argtypes = [c_void_p, POINTER(NVFBC_GRAB_FRAME_PARAMS)]
        _NvFBCCaptureFrame.restype = c_int
    except OSError:
        # This will be triggered if the NvFBC64.dll is not found.
        WinDLL = None

# Globals
session_handle = c_void_p()
is_capturing = False
capture_thread = None

def init_nvidia_apis():
    """
    Initializes the NvFBC API by creating an NvFBC instance.
    This must be called before any other NvFBC functions.
    """
    global session_handle
    if not WinDLL:
        print("This application is designed to run on Windows and/or the NVIDIA libraries could not be loaded.")
        return False

    status = NvFBCCreateInstance(ctypes.byref(session_handle))
    if status != NVFBC_SUCCESS:
        print(f"Failed to create NvFBC instance. Status: {status}")
        return False

    print("NvFBC instance created successfully.")
    return True

def capture_loop(config):
    """
    The main capture loop. This function will be run in a separate thread.
    It continuously grabs frames from the screen and passes them to an encoder.
    """
    global is_capturing

    output_filename = os.path.join(config['output_path'], f"capture-{int(time.time())}.mp4")

    with av.open(output_filename, mode='w') as container:
        stream = container.add_stream(config['codec'], rate=config['fps'])
        stream.width = config['resolution']['width']
        stream.height = config['resolution']['height']
        stream.pix_fmt = 'yuv420p'

        while is_capturing:
            grab_params = NVFBC_GRAB_FRAME_PARAMS()
            grab_params.dwVersion = NVFBC_API_VERSION
            grab_params.dwFlags = NVFBC_GRAB_FRAME_FLAGS_NO_WAIT

            frame_info = NVFBC_FRAME_GRAB_INFO()
            frame_info.dwVersion = NVFBC_API_VERSION
            grab_params.pFrameGrabInfo = ctypes.byref(frame_info)

            status = _NvFBCCaptureFrame(session_handle, ctypes.byref(grab_params))
            if status == NVFBC_SUCCESS:
                frame_data = ctypes.string_at(frame_info.pFrameBuffer, frame_info.dwByteSize)
                frame = av.VideoFrame.from_buffer(frame_data, width=stream.width, height=stream.height, format='bgra')
                for packet in stream.encode(frame):
                    container.mux(packet)

            time.sleep(1.0 / config['fps'])

        # Flush the stream
        for packet in stream.encode():
            container.mux(packet)


def start_capture(config):
    """
    Starts a screen capture session with the specified configuration.
    """
    global is_capturing, capture_thread
    if not session_handle:
        print("NvFBC instance not created.")
        return

    params = NVFBC_CREATE_CAPTURE_SESSION_PARAMS()
    params.dwVersion = NVFBC_API_VERSION
    params.eCaptureType = NVFBC_CAPTURE_TO_SYS
    params.dwAdapterIdx = 0
    params.eBufferFormat = 0  # Note: 0 corresponds to NVFBC_BUFFER_FORMAT_ARGB. This may need to be adjusted.
    params.dwWidth = config['resolution']['width']
    params.dwHeight = config['resolution']['height']
    params.dwSamplingRate = config['fps']
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
    """
    Stops the currently active screen capture session.
    """
    global is_capturing, capture_thread
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
    """
    Cleans up the NvFBC API by destroying the NvFBC instance.
    This should be called when the application exits.
    """
    if session_handle:
        NvFBCDestroyInstance(session_handle)
        print("NvFBC instance destroyed.")
