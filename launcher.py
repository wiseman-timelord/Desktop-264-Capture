# launcher.py - Main entry point for Desktop-264-Capture.
# Initialisation, shutdown, and main loop.
# Starts the Gradio server in a background thread, then opens a native
# pywebview window so the app appears as a standalone desktop program.

import os
import sys
import time
import threading
import scripts.configure as configure
import scripts.displays as displays
from scripts.recorder import init_capture_system, start_capture, stop_capture, cleanup

# ---------------------------------------------------------------------------
# Recording control
# ---------------------------------------------------------------------------

def _do_start_recording(config):
    """Begin a recording session."""
    if configure.is_recording:
        return
    start_capture(config)
    configure.is_recording         = True
    configure.recording_start_time = time.time()

def _do_stop_recording():
    """Stop the current recording session and wait for mux to finish.

    configure.is_recording is intentionally NOT checked here.  displays.py
    flips that flag early (so the polling timer goes quiet) and then calls
    this function from a background thread.  stop_capture() guards itself
    against double-calls via its own recorder.is_capturing flag.
    """
    stop_capture()
    configure.is_recording         = False
    configure.recording_start_time = None

# ---------------------------------------------------------------------------
# Exit handler
# ---------------------------------------------------------------------------

_webview_window = None   # set once the webview window is created

def _do_exit():
    """Graceful shutdown: stop recording, cleanup, close GUI."""
    if configure.is_recording:
        _do_stop_recording()
    cleanup()
    time.sleep(0.5)
    print("Goodbye.")
    # Close the native window if it exists; this will unblock webview.start()
    if _webview_window is not None:
        try:
            _webview_window.destroy()
        except Exception:
            pass

    os._exit(0)

# ---------------------------------------------------------------------------
# Gradio server thread
# ---------------------------------------------------------------------------

_GRADIO_HOST = "127.0.0.1"
_GRADIO_PORT = 7860

# Portable icon path - relative to script location for consistency
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_ICON = os.path.join(_SCRIPT_DIR, "data", "desktop_264_capture_icon.ico")

def _run_gradio_server(app, debug_mode=False):
    """Launch the Gradio server (blocking) in a daemon thread."""
    app.launch(
        inbrowser=False,           # we open our own native window instead
        server_name=_GRADIO_HOST,
        server_port=_GRADIO_PORT,
        show_error=debug_mode,     # Only show Gradio errors in debug mode
        quiet=not debug_mode,      # Verbose logs only in debug mode
        prevent_thread_lock=False,
        theme=displays.THEME,
        css=displays.CUSTOM_CSS,
    )

# ---------------------------------------------------------------------------
# Console hide helper (Windows only)
# ---------------------------------------------------------------------------

def _hide_console():
    """Hide the console window on Windows (for normal/quiet mode)."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32   = ctypes.windll.user32
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)  # SW_HIDE = 0
    except Exception:
        pass  # Ignore if not on Windows or fails

# ---------------------------------------------------------------------------
# Windows icon helper (for titlebar and taskbar)
# ---------------------------------------------------------------------------

def _set_window_icon(hwnd, icon_path):
    """Set both the titlebar and taskbar icon using Windows API."""
    try:
        import ctypes
        from ctypes import wintypes
        
        # Constants for Windows API
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0  # Titlebar icon
        ICON_BIG = 1    # Taskbar icon
        
        # Load icon from file (Unicode path for Windows)
        user32 = ctypes.windll.user32
        
        # Ensure path is absolute and uses backslashes for Windows API
        abs_path = os.path.abspath(icon_path)
        
        hIcon = user32.LoadImageW(
            None,
            abs_path,
            IMAGE_ICON,
            0, 0,  # Use actual icon size
            LR_LOADFROMFILE
        )
        
        if hIcon:
            # Set both small (titlebar) and big (taskbar/Alt-Tab) icons
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIcon)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIcon)
            
            # Also set the class icon so new windows inherit it
            # GCL_HICON = -14, GCL_HICONSM = -34
            user32.SetClassLongW(hwnd, -14, hIcon)  # GCL_HICON
            user32.SetClassLongW(hwnd, -34, hIcon)  # GCL_HICONSM
            
            return True
    except Exception as e:
        if "--debug" in sys.argv:
            print(f"Icon setup warning: {e}")
    return False

def _force_icon_immediate(window, icon_path):
    """
    Force icon setting as early as possible.
    Tries multiple methods to get the window handle and set the icon.
    """
    if not icon_path or not os.path.isfile(icon_path):
        return False
        
    if sys.platform != 'win32':
        return False
    
    try:
        import ctypes
        
        # Method 1: Try to get handle from pywebview's native property
        try:
            # Different pywebview versions expose this differently
            if hasattr(window, 'native'):
                native = window.native
                if hasattr(native, 'Handle'):
                    hwnd = native.Handle.ToInt32()
                    if _set_window_icon(hwnd, icon_path):
                        return True
                elif isinstance(native, int):
                    if _set_window_icon(native, icon_path):
                        return True
        except Exception:
            pass
        
        # Method 2: Find window by title using EnumWindows
        def _find_window_by_title():
            target_title = "Desktop-264-Capture"
            found_hwnd = [None]
            
            def _enum_callback(hwnd, extra):
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                    if target_title in buffer.value:
                        found_hwnd[0] = hwnd
                        return False  # Stop enumeration
                return True
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            callback = EnumWindowsProc(_enum_callback)
            ctypes.windll.user32.EnumWindows(callback, None)
            return found_hwnd[0]
        
        hwnd = _find_window_by_title()
        if hwnd:
            if _set_window_icon(hwnd, icon_path):
                return True
                
    except Exception as e:
        if "--debug" in sys.argv:
            print(f"Immediate icon error: {e}")
    
    return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _webview_window

    # Check for debug flag
    debug_mode = "--debug" in sys.argv

    # Hide console window in normal mode (not debug)
    if not debug_mode:
        _hide_console()

    if debug_mode:
        print("Desktop-264-Capture: Initialising (Debug Mode) ... ")
    else:
        print("Desktop-264-Capture: Initialising ... ")

    # Set Windows AppUserModelID BEFORE creating the webview window so that
    # Windows groups the taskbar button under Desktop-264-Capture's own icon
    # rather than the generic Python interpreter icon.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Desktop264Capture.Recorder.1"
        )
    except (AttributeError, OSError):
        pass  # Not on Windows or older Windows version

    config = configure.load_configuration()

    if not init_capture_system(config):
        print(
             "\nERROR: Capture system could not initialise.\n "
             "Run option 3 (Install) in the batch menu, then try again. "
        )
        if debug_mode:
            input("Press ENTER to exit ... ")
        sys.exit(1)
    os.makedirs(config.get("output_path", "Output"), exist_ok=True)

    # Build the Gradio app
    app = displays.build_interface(
        config   = config,
        start_cb = lambda: _do_start_recording(config),
        stop_cb  = _do_stop_recording,
        exit_cb  = _do_exit,
    )

    # Start the Gradio server in a background daemon thread
    server_thread = threading.Thread(
        target=_run_gradio_server,
        args=(app, debug_mode),
        daemon=True,
        name="gradio-server",
    )
    server_thread.start()

    # Wait briefly for the server to be ready
    url = f"http://{_GRADIO_HOST}:{_GRADIO_PORT}"
    print(f"Gradio server starting at {url} ... ")
    time.sleep(2)

    # Open a native desktop window via pywebview
    try:
        import webview

        _webview_window = webview.create_window(
            title="Desktop-264-Capture",
            url=url,
            width=940,
            height=780,
            resizable=True,
            min_size=(800, 600),
        )

        # Attach a closing handler so the title-bar X does the same
        # graceful shutdown as the in-app "Exit Program" button.
        def _on_window_closed():
            _do_exit()

        _webview_window.events.closed += _on_window_closed

        # Set up icon path
        icon_path = _APP_ICON if os.path.isfile(_APP_ICON) else None
        
        # Set up EARLY icon application using the 'shown' event
        # This fires when the window is first shown, earlier than 'loaded'
        def _on_window_shown():
            """Apply icon immediately when window becomes visible."""
            if icon_path:
                _force_icon_immediate(_webview_window, icon_path)
        
        if hasattr(_webview_window.events, 'shown'):
            _webview_window.events.shown += _on_window_shown
        
        # Also set up a polling fallback that tries immediately after start()
        # This runs in a daemon thread to not block the main flow
        _icon_set = threading.Event()
        
        def _poll_for_icon():
            """Poll for window handle and set icon as soon as possible."""
            if not icon_path:
                return
            # Try multiple times in the first few seconds
            for _ in range(20):  # 20 attempts over 2 seconds
                if _icon_set.is_set():
                    return
                if _force_icon_immediate(_webview_window, icon_path):
                    _icon_set.set()
                    return
                time.sleep(0.1)
        
        # Start the polling thread - it will race to set the icon ASAP
        icon_thread = threading.Thread(
            target=_poll_for_icon,
            daemon=True,
            name="icon-setter"
        )
        icon_thread.start()
        
        # Start webview with the icon parameter (fallback)
        # The icon parameter sets the window class icon at creation time
        webview.start(
            icon=icon_path,
            debug=False  # Explicitly disable DevTools
        )

    except ImportError:
        # pywebview not available - fall back to opening in the default browser
        msg = "WARNING: pywebview not installed. Opening in default browser instead."
        print(msg)
        if debug_mode:
            import webbrowser
            webbrowser.open(url)
            try:
                server_thread.join()
            except KeyboardInterrupt:
                pass

    # If webview exits without triggering _do_exit (rare), ensure cleanup
    if configure.is_recording:
        _do_exit()

if __name__ == "__main__":
    main()