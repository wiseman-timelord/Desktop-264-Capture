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
    """Stop the current recording session and wait for mux to finish."""
    if not configure.is_recording:
        return
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

def _run_gradio_server(app, debug_mode=False):
    """Launch the Gradio server (blocking) in a daemon thread."""
    app.launch(
        inbrowser=False,           # we open our own native window instead
        server_name=_GRADIO_HOST,
        server_port=_GRADIO_PORT,
        show_error=True,
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
        user32 = ctypes.windll.user32
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)  # SW_HIDE = 0
    except Exception:
        pass  # Ignore if not on Windows or fails

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

        # webview.start() blocks until the window is closed
        webview.start()

    except ImportError:
        # pywebview not available - fall back to opening in the default browser
        print(
             "WARNING: pywebview not installed.  "
             "Opening in default browser instead. "
        )
        import webbrowser
        webbrowser.open(url)
        # Keep the main thread alive so the server keeps running
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass
    
    # If webview exits without triggering _do_exit (rare), ensure cleanup
    if configure.is_recording:
        _do_exit()

if __name__ == "__main__":
    main()