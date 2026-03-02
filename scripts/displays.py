# scripts/displays.py
# Gradio-based GUI for Desktop-264-Capture.
# Two tabs: Recording (file table / live monitor) and Configure (grouped rows).
# Dark grey theme throughout.  Status bar + Exit button on every tab.

# Imports...
import os
import threading
import time
import gradio as gr
import scripts.configure as configure
from scripts import recorder
from scripts import utilities

# ===========================================================================
# Theme: dark greys
# ===========================================================================
THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.gray,
    secondary_hue=gr.themes.colors.gray,
    neutral_hue=gr.themes.colors.gray,
).set(
    body_background_fill="#1a1a1a",
    body_background_fill_dark="#1a1a1a",
    background_fill_primary="#242424",
    background_fill_primary_dark="#242424",
    background_fill_secondary="#2e2e2e",
    background_fill_secondary_dark="#2e2e2e",
    block_background_fill="#2a2a2a",
    block_background_fill_dark="#2a2a2a",
    block_border_color="#3a3a3a",
    block_border_color_dark="#3a3a3a",
    block_label_background_fill="#333333",
    block_label_background_fill_dark="#333333",
    block_title_text_color="#cccccc",
    block_title_text_color_dark="#cccccc",
    body_text_color="#d0d0d0",
    body_text_color_dark="#d0d0d0",
    body_text_color_subdued="#888888",
    body_text_color_subdued_dark="#888888",
    button_primary_background_fill="#4a4a4a",
    button_primary_background_fill_dark="#4a4a4a",
    button_primary_background_fill_hover="#5a5a5a",
    button_primary_background_fill_hover_dark="#5a5a5a",
    button_primary_text_color="#e0e0e0",
    button_primary_text_color_dark="#e0e0e0",
    button_secondary_background_fill="#383838",
    button_secondary_background_fill_dark="#383838",
    button_secondary_background_fill_hover="#484848",
    button_secondary_background_fill_hover_dark="#484848",
    button_secondary_text_color="#c0c0c0",
    button_secondary_text_color_dark="#c0c0c0",
    input_background_fill="#333333",
    input_background_fill_dark="#333333",
    input_border_color="#444444",
    input_border_color_dark="#444444",
    border_color_accent="#555555",
    border_color_accent_dark="#555555",
    color_accent_soft="#3a3a3a",
    color_accent_soft_dark="#3a3a3a",
)

# ===========================================================================
# Custom CSS
# ===========================================================================
CUSTOM_CSS = """
/* ---- Global ---- */
.gradio-container {
    max-width: 1200px !important;
    width: 95% !important;
    margin: auto;
    background: #1a1a1a !important;
    font-family: 'Segoe UI', Consolas, sans-serif;
}
/* ---- Tab styling ---- */
.tab-nav button {
    background: #2a2a2a !important;
    color: #999 !important;
    border: 1px solid #3a3a3a !important;
    font-weight: 600;
    font-size: 0.95rem;
    padding: 10px 28px !important;
}
.tab-nav button.selected {
    background: #3a3a3a !important;
    color: #ffffff !important;
    border-bottom: 2px solid #aaaaaa !important;
}
/* ---- Info boxes (read-only textboxes used as display panels) ---- */
.info-box input, .info-box textarea {
    background: #222 !important;
    color: #ccc !important;
    border: 1px solid #3a3a3a !important;
    font-family: Consolas, 'Courier New', monospace !important;
    font-size: 0.85rem !important;
    text-align: center !important;
}
.info-box label span {
    color: #888 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em;
}
/* ---- Totals row ---- */
.totals-box input {
    background: #262626 !important;
    color: #aaa !important;
    border: 1px solid #333 !important;
    font-family: Consolas, monospace !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    text-align: center !important;
}
/* ---- File table ---- */
.file-table {
    font-size: 0.82rem !important;
}
.file-table table {
    background: #222 !important;
}
.file-table th {
    background: #333 !important;
    color: #bbb !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em;
}
.file-table td {
    background: #252525 !important;
    color: #ccc !important;
    border-color: #333 !important;
    font-family: Consolas, monospace !important;
    font-size: 0.82rem !important;
    padding-top: 2px !important;
    padding-bottom: 2px !important;
    line-height: 1.15 !important;
}
/* Grow table naturally with content, min 5 rows */
.file-table .table-wrap {
    overflow-y: auto !important;
}
/* ---- Recording info boxes ---- */
.rec-info-box input {
    background: #1e1e1e !important;
    color: #e0e0e0 !important;
    border: 1px solid #444 !important;
    font-family: Consolas, monospace !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    text-align: center !important;
}
.rec-info-box label span {
    color: #888 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
}
/* ---- Encode log ---- */
.encode-log textarea {
    background: #1a1a1a !important;
    color: #8a8 !important;
    font-family: Consolas, monospace !important;
    font-size: 0.78rem !important;
    border: 1px solid #333 !important;
}
/* ---- Status bar ---- */
.status-bar input {
    background: #262626 !important;
    color: #999 !important;
    border: 1px solid #333 !important;
    font-size: 0.82rem !important;
}
/* ---- Buttons ---- */
.record-btn {
    background: #c0392b !important;
    color: white !important;
    font-weight: 700 !important;
    min-height: 42px;
}
.record-btn:hover { background: #e74c3c !important; }
.stop-btn {
    background: #555 !important;
    color: #eee !important;
    font-weight: 700 !important;
    min-height: 42px;
}
.stop-btn:hover { background: #777 !important; }
.purge-btn {
    background: #7f1d1d !important;
    color: #fca5a5 !important;
    font-weight: 600 !important;
}
.purge-btn:hover { background: #991b1b !important; }
/* Save Configuration — orange */
.save-btn {
    background: #c2560a !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    min-height: 0 !important;
    height: 38px !important;
    line-height: 1 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    padding: 0 8px !important;
}
.save-btn:hover { background: #ea6f0e !important; }
/* Exit button — force red regardless of theme */
.exit-btn {
    min-width: 110px;
    background: #b91c1c !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    min-height: 0 !important;
    height: 38px !important;
    line-height: 1 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    padding: 0 8px !important;
}
.exit-btn:hover { background: #dc2626 !important; }
/* ---- Config section labels ---- */
.cfg-section-label p {
    color: #888 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #333;
    padding-bottom: 4px;
    margin-bottom: 0 !important;
}
/* ---- Hide Gradio footer ---- */
footer { display: none !important; }
/* ---- About page header ---- */
.about-header p, .about-header h2, .about-header li, .about-header a {
    color: #cccccc !important;
}
.about-header a {
    color: #7ab4f5 !important;
    text-decoration: none;
}
.about-header a:hover { text-decoration: underline; }
.about-header h2 {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    margin-bottom: 2px !important;
}
"""

# ===========================================================================
# Shared state
# ===========================================================================
_shutdown_event = threading.Event()

# ===========================================================================
# Helper: build file table data
# ===========================================================================
_MIN_TABLE_ROWS = 5   # minimum rows shown; expands 1-per-file beyond this

def _build_file_table(config: dict):
    """Return (dataframe_rows, total_files_str, total_size_str, output_folder_str).
    Shows the most-recent files up to _MIN_TABLE_ROWS minimum rows.
    Starts at 5 rows (files + empty padding), then grows 1 row per extra file.
    """
    out_path = config.get("output_path", utilities.DEFAULT_OUTPUT)
    videos   = utilities.list_videos(out_path)
    folder_str = utilities.display_path(out_path)
    empty_row  = ["  ", "  ", "  "]

    if not videos:
        rows = [["  - empty -", "  ", "  "]] + [empty_row] * (_MIN_TABLE_ROWS - 1)
        return rows, "0", "0 B", folder_str

    data_rows  = [[v["name"], v["size_str"], v["date"]] for v in videos]
    pad_needed = max(0, _MIN_TABLE_ROWS - len(data_rows))
    rows       = data_rows + [empty_row] * pad_needed

    total_size = sum(v["size"] for v in videos)
    return (
        rows,
        str(len(videos)),
        utilities.fmt_bytes(total_size),
        folder_str,
    )

# ===========================================================================
# Helper: build recording monitor values
# ===========================================================================
def _build_rec_values(config: dict) -> dict:
    """Return a dict of all recording display values for the GUI boxes."""
    d = {
        "status":         "IDLE",
        "resolution":     "--",
        "fps":            "--",
        "audio_prof":     "--",
        "segment":        "--",
        "seg_progress":  0.0,
        "seg_label":      "Segment: --",
        "output_dir":     config.get("output_path", "Output"),
        "encode_log":     "  ",
    }
    if not configure.is_recording or configure.recording_start_time is None:
        return d

    elapsed     = time.time() - configure.recording_start_time
    seg_elapsed = recorder.current_segment_elapsed()
    seg_num     = recorder.current_segment_num
    splits_on   = config.get("video_splits", False)
    split_dur   = recorder.SPLIT_DURATION if splits_on else 0

    res = config["resolution"]
    ab  = configure.effective_audio_bitrate(config)

    d["status"]     = "● RECORDING"
    d["resolution"] = f"{res['width']}x{res['height']}"
    d["fps"]        = str(config["fps"])
    # Audio Profile shows bitrate only
    d["audio_prof"] = f"{ab} kbps"
    d["output_dir"] = utilities.display_path(config.get("output_path", "Output"))

    # Segment progress
    if splits_on and split_dur > 0:
        seg_pct = min(seg_elapsed / split_dur, 1.0)
        d["segment"] = (
            f"S{seg_num:03d}     "
            f"[{utilities.fmt_time(seg_elapsed)} / {utilities.fmt_time(split_dur)}] "
        )
    else:
        seg_pct = min(seg_elapsed / 3600.0, 1.0)
        d["segment"] = f"S{seg_num:03d}   [{utilities.fmt_time(seg_elapsed)}] "
    d["seg_progress"] = seg_pct
    d["seg_label"]    = f"Segment {seg_num}:  {seg_pct * 100:.0f}%"

    # Encode log
    log = []
    mux_pending = recorder.pending_mux_count
    if mux_pending > 0:
        log.append(f"[MUX] {mux_pending} segment(s) encoding  (stream-copy + AAC)... ")
    last = recorder.last_output_file
    if last:
        log.append(f"[DONE] {os.path.basename(last)} ")
    d["encode_log"] = "\n".join(log)

    return d

# ===========================================================================
# Build the Gradio interface
# ===========================================================================
def build_interface(config: dict, start_cb, stop_cb, exit_cb):
    """
    Construct and return the Gradio Blocks app.
    Parameters
    ----------
    config     : current configuration dict (mutable reference)
    start_cb   : callable()  - begin recording
    stop_cb    : callable()  - stop recording
    exit_cb    : callable()  - shut down the application
    """
    with gr.Blocks(
        title="Desktop-264-Capture",
    ) as app:

        with gr.Tabs() as tabs:

            # =======================================================================
            # TAB 1 - RECORDING
            # =======================================================================
            with gr.Tab("Recording", id="tab_rec"):

                # --- Initial table data ---
                init_rows, init_count, init_size, init_folder = \
                    _build_file_table(config)

                # --- Files panel    (visible when NOT recording) -------------
                with gr.Column(visible=True) as files_panel:

                    # Output folder box
                    out_folder_box = gr.Textbox(
                        value=init_folder,
                        label="Output Folder",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                    )

                    # File table
                    file_table = gr.Dataframe(
                        value=init_rows,
                        headers=["Filename", "Size", "Date"],
                        datatype=["str", "str", "str"],
                        interactive=False,
                        row_count=(_MIN_TABLE_ROWS, "dynamic"),
                        column_count=(3, "fixed"),
                        elem_classes=["file-table"],
                    )

                    # Totals row  (Total Files | Total Size | Purge All)
                    with gr.Row():
                        total_files_box = gr.Textbox(
                            value=init_count,
                            label="Total Files",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["totals-box"],
                        )
                        total_size_box = gr.Textbox(
                            value=init_size,
                            label="Total Size",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["totals-box"],
                        )
                        rec_purge_btn = gr.Button(
                            "\U0001F5D1  Purge All Files",
                            variant="stop",
                            elem_classes=["purge-btn"],
                            scale=1,
                        )

                # --- Recording panel  (visible WHILE recording) ------------
                with gr.Column(visible=False) as rec_panel:

                    # Row 1: Status | Output Dir (Segment removed, Output Dir moved up)
                    with gr.Row():
                        rec_status_box = gr.Textbox(
                            value="IDLE",
                            label="Status",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["rec-info-box"],
                            scale=2,
                        )
                        rec_outdir_box = gr.Textbox(
                            value="--",
                            label="Output Dir",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["rec-info-box"],
                            scale=3,
                        )

                    # Row 2: Resolution | FPS | Audio Profile (Video Profile removed)
                    with gr.Row():
                        rec_res_box = gr.Textbox(
                            value="--",
                            label="Resolution",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["rec-info-box"],
                        )
                        rec_fps_box = gr.Textbox(
                            value="--",
                            label="FPS",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["rec-info-box"],
                        )
                        rec_aprof_box = gr.Textbox(
                            value="--",
                            label="Audio Profile",
                            interactive=False,
                            max_lines=1,
                            elem_classes=["rec-info-box"],
                        )

                    # Row 3: Segment progress bar
                    seg_progress = gr.Slider(
                        minimum=0,
                        maximum=1,
                        value=0,
                        label="Segment Progress",
                        interactive=False,
                    )

                    # Row 4: Encode log
                    encode_log = gr.Textbox(
                        value="  ",
                        label="Encode Log",
                        lines=2,
                        max_lines=3,
                        interactive=False,
                        elem_classes=["encode-log"],
                    )

                # --- Control buttons --------------------------------------
                # Visibility rules:
                #   idle     → Start only
                #   recording→ Pause + Stop
                #   paused   → Resume + Stop
                with gr.Row():
                    rec_start_btn = gr.Button(
                        "\u23FA  Start Recording",
                        variant="primary",
                        elem_classes=["record-btn"],
                        scale=3,
                        visible=True,
                    )
                    rec_pause_btn = gr.Button(
                        "\u23F8  Pause",
                        variant="secondary",
                        elem_classes=["stop-btn"],
                        scale=3,
                        visible=False,
                    )
                    rec_resume_btn = gr.Button(
                        "\u25B6  Resume",
                        variant="primary",
                        elem_classes=["record-btn"],
                        scale=3,
                        visible=False,
                    )
                    rec_stop_btn = gr.Button(
                        "\u23F9  Stop Recording",
                        variant="secondary",
                        elem_classes=["stop-btn"],
                        scale=3,
                        visible=False,
                    )

                # --- Polling timer ----------------------------------------
                rec_timer = gr.Timer(value=1.0, active=False)

                # --- Status bar -------------------------------------------
                with gr.Row():
                    rec_status = gr.Textbox(
                        value="Ready.",
                        label="Status",
                        interactive=False,
                        max_lines=1,
                        scale=20,
                        elem_classes=["status-bar"],
                    )
                    exit_rec = gr.Button(
                        "Exit Program",
                        variant="secondary",
                        scale=1,
                        elem_classes=["exit-btn"],
                    )

                # ----------------------------------------------------------
                # Recording tab callbacks
                # ----------------------------------------------------------

                # All recording-panel output components in canonical order:
                # (7 components total now)
                _rec_panel_outputs = [
                    rec_status_box, rec_outdir_box,
                    rec_res_box, rec_fps_box, rec_aprof_box,
                    seg_progress, encode_log,
                ]

                def _apply_rec_values(rv: dict) -> list:
                    """Map a rec-values dict to gr.update() list for the panel."""
                    return [
                        gr.update(value=rv["status"]),
                        gr.update(value=rv["output_dir"]),
                        gr.update(value=rv["resolution"]),
                        gr.update(value=rv["fps"]),
                        gr.update(value=rv["audio_prof"]),
                        gr.update(value=rv["seg_progress"], label=rv["seg_label"]),
                        gr.update(value=rv["encode_log"]),
                    ]

                # Button visibility helpers
                def _btn_idle():
                    """Start visible; Pause, Resume, Stop hidden."""
                    return (
                        gr.update(visible=True),   # start
                        gr.update(visible=False),  # pause
                        gr.update(visible=False),  # resume
                        gr.update(visible=False),  # stop
                    )

                def _btn_recording():
                    """Pause + Stop visible; Start, Resume hidden."""
                    return (
                        gr.update(visible=False),  # start
                        gr.update(visible=True),   # pause
                        gr.update(visible=False),  # resume
                        gr.update(visible=True),   # stop
                    )

                def _btn_paused():
                    """Resume + Stop visible; Start, Pause hidden."""
                    return (
                        gr.update(visible=False),  # start
                        gr.update(visible=False),  # pause
                        gr.update(visible=True),   # resume
                        gr.update(visible=True),   # stop
                    )

                def on_start_recording():
                    if configure.is_recording:
                        noop = [gr.update()] * 7
                        return (
                            [gr.update(), gr.update()]   # panels
                            + noop                       # rec boxes
                            + list(_btn_idle())          # 4 buttons
                            + [gr.update()]              # timer
                            + ["Already recording."]     # status
                        )

                    start_cb()
                    rv = _build_rec_values(config)
                    updates = _apply_rec_values(rv)

                    return (
                        [gr.update(visible=False), gr.update(visible=True)]
                        + updates
                        + list(_btn_recording())
                        + [gr.update(active=True)]
                        + ["Recording..."]
                    )

                rec_start_btn.click(
                    fn=on_start_recording,
                    outputs=(
                        [files_panel, rec_panel]
                        + _rec_panel_outputs
                        + [rec_start_btn, rec_pause_btn, rec_resume_btn, rec_stop_btn]
                        + [rec_timer]
                        + [rec_status]
                    ),
                )

                def on_stop_recording():
                    if not configure.is_recording:
                        return [gr.update()] * 13

                    stop_cb()

                    last = recorder.last_output_file
                    segs = recorder.last_segment_count
                    if last and os.path.exists(last):
                        sz = utilities.fmt_bytes(os.path.getsize(last))
                        if segs > 1:
                            msg = (
                                f"Done. {segs} segment(s).   "
                                f"Last: {os.path.basename(last)} ({sz}) "
                            )
                        else:
                            msg = f"Saved: {os.path.basename(last)} ({sz}) "
                    else:
                        msg = "Stopped. Check output folder."

                    refreshed = configure.load_configuration()
                    config.update(refreshed)
                    rows, cnt, sz_str, fld = _build_file_table(config)

                    return [
                        gr.update(visible=True),    # files_panel
                        gr.update(visible=False),   # rec_panel
                        gr.update(value=rows),        # file_table
                        gr.update(value=cnt),       # total_files
                        gr.update(value=sz_str),    # total_size
                        gr.update(value=fld),       # out_folder
                    ] + list(_btn_idle()) + [
                        gr.update(active=False),                       # timer
                        gr.update(value=0, label="Segment Progress"),  # seg_progress
                        gr.update(value="  "),                           # encode_log
                        msg,                                           # status
                    ]

                rec_stop_btn.click(
                    fn=on_stop_recording,
                    outputs=[
                        files_panel, rec_panel,
                        file_table, total_files_box, total_size_box, out_folder_box,
                        rec_start_btn, rec_pause_btn, rec_resume_btn, rec_stop_btn,
                        rec_timer,
                        seg_progress, encode_log,
                        rec_status,
                    ],
                )

                def on_pause_recording():
                    """Pause: best-effort call to recorder, switch to paused UI."""
                    if not configure.is_recording:
                        return [gr.update()] * 5
                    try:
                        recorder.pause_capture()
                    except AttributeError:
                        pass   # recorder may not implement pause yet
                    configure.is_paused = True
                    return list(_btn_paused()) + ["Paused."]

                rec_pause_btn.click(
                    fn=on_pause_recording,
                    outputs=[
                        rec_start_btn, rec_pause_btn, rec_resume_btn, rec_stop_btn,
                        rec_status,
                    ],
                )

                def on_resume_recording():
                    """Resume: best-effort call to recorder, switch to recording UI."""
                    try:
                        recorder.resume_capture()
                    except AttributeError:
                        pass
                    configure.is_paused = False
                    return list(_btn_recording()) + ["Recording..."]

                rec_resume_btn.click(
                    fn=on_resume_recording,
                    outputs=[
                        rec_start_btn, rec_pause_btn, rec_resume_btn, rec_stop_btn,
                        rec_status,
                    ],
                )

                def on_purge():
                    if configure.is_recording:
                        return [gr.update()] * 4 + ["Cannot purge while recording."]
                    out = config.get("output_path", utilities.DEFAULT_OUTPUT)
                    deleted, total, errs = utilities.purge_recordings(out)
                    if total == 0:
                        msg = "No recordings to purge."
                    else:
                        msg = f"Purged {deleted}/{total} recording(s)."
                        if errs:
                            msg += f"  Errors: {len(errs)} "
                    refreshed = configure.load_configuration()
                    config.update(refreshed)
                    rows, cnt, sz_str, fld = _build_file_table(config)
                    return [
                        gr.update(value=rows),
                        gr.update(value=cnt),
                        gr.update(value=sz_str),
                        gr.update(value=fld),
                        msg,
                    ]

                rec_purge_btn.click(
                    fn=on_purge,
                    outputs=[
                        file_table, total_files_box, total_size_box,
                        out_folder_box, rec_status,
                    ],
                )

                def on_timer_tick():
                    if not configure.is_recording:
                        return [gr.update()] * 7

                    rv = _build_rec_values(config)
                    elapsed = 0
                    if configure.recording_start_time:
                        elapsed = time.time() - configure.recording_start_time

                    return [
                        gr.update(value=rv["status"]),
                        gr.update(value=rv["output_dir"]),
                        gr.update(value=rv["resolution"]),
                        gr.update(value=rv["fps"]),
                        gr.update(value=rv["audio_prof"]),
                        gr.update(
                            value=rv["seg_progress"],
                            label=rv["seg_label"],
                        ),
                        gr.update(value=rv["encode_log"]),
                        f"Recording...  [{utilities.fmt_time(elapsed)}] ",
                    ]

                rec_timer.tick(
                    fn=on_timer_tick,
                    outputs=[
                        rec_status_box, rec_outdir_box,
                        rec_res_box, rec_fps_box, rec_aprof_box,
                        seg_progress, encode_log,
                        rec_status,
                    ],
                )

                exit_rec.click(fn=lambda: exit_cb())

            # =======================================================================
            # TAB 2 - CONFIGURE
            # =======================================================================
            with gr.Tab("Configure", id="tab_cfg"):

                # ---- Row 1: Video  (Resolution | FPS | Video Compression)
                gr.Markdown("Video", elem_classes=["cfg-section-label"])
                with gr.Row():
                    res = config["resolution"]
                    res_val = f"{res['width']}x{res['height']}"
                    res_choices = [
                        f"{r['width']}x{r['height']}"
                        for r in configure.resolutions
                    ]
                    cfg_resolution = gr.Dropdown(
                        choices=res_choices,
                        value=(
                            res_val if res_val in res_choices
                            else res_choices[0]
                        ),
                        label="Resolution",
                    )
                    cfg_fps = gr.Dropdown(
                        choices=[str(f) for f in configure.fps_options],
                        value=str(config.get("fps", 30)),
                        label="FPS",
                    )
                    cfg_video_comp = gr.Dropdown(
                        choices=configure.video_compression_options,
                        value=config.get(
                            "video_compression", "Optimal Performance"
                        ),
                        label="Video Compression",
                    )

                # ---- Row 2: Audio  (Audio Bitrate | Audio Compression)
                gr.Markdown("Audio", elem_classes=["cfg-section-label"])
                with gr.Row():
                    cfg_audio_br = gr.Dropdown(
                        choices=[
                            f"{b} kbps"
                            for b in configure.audio_bitrate_options
                        ],
                        value=f"{config.get('audio_bitrate', 192)} kbps",
                        label="Audio Bitrate",
                    )
                    cfg_audio_comp = gr.Dropdown(
                        choices=configure.audio_compression_options,
                        value=config.get(
                            "audio_compression", "Optimal Performance"
                        ),
                        label="Audio Compression",
                    )

                # ---- Row 3: Output  (Container | Output Dir)
                gr.Markdown("Output", elem_classes=["cfg-section-label"])
                with gr.Row():
                    cfg_container = gr.Dropdown(
                        choices=configure.container_format_options,
                        value=config.get("container_format", "MKV"),
                        label="Container Format",
                    )
                    cfg_output_dir = gr.Textbox(
                        value=config.get("output_path", "Output"),
                        label="Output Directory",
                        scale=2,
                    )

                    cfg_splits = gr.Dropdown(
                        choices=["Off", "On"],
                        value=(
                            "On" if config.get("video_splits", False)
                            else "Off"
                        ),
                        label="1-Hour Video Splits",
                    )

                # ---- Row 4: Resources
                #      (1Hr Splits | Max Threads | Max RAM)
                gr.Markdown(
                    "RESOURCES",
                    elem_classes=["cfg-section-label"],
                )
                with gr.Row():
                    cfg_threads = gr.Dropdown(
                        choices=[
                            f"{t}%" for t in configure.thread_budget_options
                        ],
                        value=f"{config.get('thread_budget', 75)}%",
                        label="Max Threads Used",
                    )
                    cfg_ram = gr.Dropdown(
                        choices=[
                            f"{r}%" for r in configure.max_ram_usage_options
                        ],
                        value=f"{config.get('max_ram_usage', 50)}%",
                        label="Max RAM Usage",
                    )

                # --- Status bar -------------------------------------------
                with gr.Row():
                    cfg_status = gr.Textbox(
                        value="Configuration tab loaded.",
                        label="Status",
                        interactive=False,
                        max_lines=1,
                        scale=20,
                        elem_classes=["status-bar"],
                    )
                    with gr.Column(scale=1, min_width=130):
                        cfg_save_btn = gr.Button(
                            "\U0001F4BE  Save Settings",
                            variant="secondary",
                            elem_classes=["save-btn"],
                        )
                        exit_cfg = gr.Button(
                            "Exit Program",
                            variant="secondary",
                            elem_classes=["exit-btn"],
                        )

                # --- Configure callbacks ----------------------------------

                def on_save_config(
                    res_str, fps_str, v_comp, a_br_str, a_comp,
                    container, out_dir, splits_str, threads_str, ram_str,
                ):
                    if configure.is_recording:
                        return "Cannot change settings while recording."

                    try:
                        w, h = res_str.split("x")
                        config["resolution"] = {
                            "width": int(w), "height": int(h)
                        }
                    except (ValueError, AttributeError):
                        pass

                    try:
                        config["fps"] = int(fps_str)
                    except (ValueError, TypeError):
                        pass

                    if v_comp in configure.video_compression_options:
                        config["video_compression"] = v_comp

                    try:
                        config["audio_bitrate"] = int(
                            a_br_str.replace("kbps", "").strip()
                        )
                    except (ValueError, AttributeError):
                        pass

                    if a_comp in configure.audio_compression_options:
                        config["audio_compression"] = a_comp

                    if container in configure.container_format_options:
                        config["container_format"] = container

                    if out_dir and out_dir.strip():
                        resolved = utilities.resolve_output_path(
                            out_dir.strip()
                        )
                        if resolved:
                            try:
                                os.makedirs(resolved, exist_ok=True)
                                config["output_path"] = resolved
                            except OSError as e:
                                return f"Error creating folder: {e}"

                    config["video_splits"] = (splits_str == "On")

                    try:
                        config["thread_budget"] = int(
                            threads_str.replace("%", "").strip()
                        )
                    except (ValueError, AttributeError):
                        pass

                    try:
                        config["max_ram_usage"] = int(
                            ram_str.replace("%", "").strip()
                        )
                    except (ValueError, AttributeError):
                        pass

                    configure.save_configuration(config)
                    return "Configuration saved."

                cfg_save_btn.click(
                    fn=on_save_config,
                    inputs=[
                        cfg_resolution, cfg_fps, cfg_video_comp,
                        cfg_audio_br, cfg_audio_comp,
                        cfg_container, cfg_output_dir,
                        cfg_splits, cfg_threads, cfg_ram,
                    ],
                    outputs=[cfg_status],
                )

                exit_cfg.click(fn=lambda: exit_cb())

            # =======================================================================
            # TAB 3 - ABOUT / DEBUG
            # =======================================================================
            with gr.Tab("About / Debug", id="tab_about"):

                gr.Markdown(
                    """
Desktop-264-Capture
A x264vfw screen recording tool for Windows ~8.1-10 by [WiseMan-TimeLord](https://wisetime.rf.gd)
Here is the project on [GitHub](https://github.com/wiseman-timelord/Desktop-264-Capture).
Here are the [1.61 videos](https://www.youtube.com/playlist?list=PL7GSoMbwogC9FhbdfFyjXJcFDNSPFdg_U) created during testing.
""",
                    elem_classes=["about-header"],
                )
                # --- System / Debug info boxes ----------------------------
                gr.Markdown("System Info", elem_classes=["cfg-section-label"])

                sinfo = utilities.get_system_info()

                with gr.Row():
                    gr.Textbox(
                        value=sinfo.get("python_version", "?"),
                        label="Python Version",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                    )
                    gr.Textbox(
                        value=sinfo.get("opencv", "not installed"),
                        label="OpenCV",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                    )
                    gr.Textbox(
                        value=sinfo.get("mss", "not installed"),
                        label="MSS (DXGI)",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                    )

                with gr.Row():
                    gr.Textbox(
                        value=sinfo.get("cpu_name", "?"),
                        label="CPU",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=3,
                    )
                    gr.Textbox(
                        value=f"{sinfo.get('thread_cap', '?')}/{sinfo.get('logical_cores', '?')}",
                        label="Cores Used / Total",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=1,
                    )
                    gr.Textbox(
                        value=sinfo.get("simd_flags", "none"),
                        label="SIMD Flags",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=2,
                    )

                gr.Markdown("Pipeline", elem_classes=["cfg-section-label"])
                with gr.Row():
                    gr.Textbox(
                        value=sinfo.get("encoding", "?"),
                        label="Encoding Pipeline",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=2,
                    )
                    gr.Textbox(
                        value=sinfo.get("segments", "?"),
                        label="Segment Strategy",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=2,
                    )
                    gr.Textbox(
                        value=sinfo.get("ffmpeg_status", "Missing"),
                        label="FFmpeg Status",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["info-box"],
                        scale=1,
                    )

                # --- About tab status / exit bar --------------------------
                with gr.Row():
                    about_status = gr.Textbox(
                        value="About / Debug tab loaded.",
                        label="Status",
                        interactive=False,
                        max_lines=1,
                        scale=20,
                        elem_classes=["status-bar"],
                    )
                    exit_about = gr.Button(
                        "Exit Program",
                        variant="secondary",
                        scale=1,
                        elem_classes=["exit-btn"],
                    )

                exit_about.click(fn=lambda: exit_cb())

    # =======================================================================
    # Window [X] close hook – fires exit_cb when the browser tab /webview
    # window is closed via the native title-bar button.
    # Uses a synchronous XHR so the shutdown runs before the page unloads.
    # =======================================================================
    _exit_js = """
    () => {
    window.addEventListener('beforeunload', function(e) {
    // Find and click the first visible Exit Program button
    var btns = document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
    if (btns[i].textContent.trim() === 'Exit Program') {
    btns[i].click();
    break;
    }
    }
    });
    }
    """
    app.load(js=_exit_js)
    return app