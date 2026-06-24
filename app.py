#!/usr/bin/env python3
"""Desk.app shell — native macOS window (WKWebView via pywebview) around the desk server."""

import os
import sys

import webview  # type: ignore

from server import DEFAULT_PORT, start_server_preferred


class _Api:
    """JS bridge for the native folder picker (native window only). The frontend calls
    `window.pywebview.api.pick_folder()`; web mode (no pywebview) falls back to text entry.
    Returns the chosen path or None and never raises into the GUI — a dialog failure just
    leaves the patron's text field as-is. The path still goes through the validated
    /api/projects/add, so the under-$HOME fence is enforced server-side, not here."""

    def pick_folder(self):
        try:
            win = webview.windows[0]
            res = win.create_file_dialog(
                webview.FOLDER_DIALOG, directory=os.path.expanduser("~"))
        except Exception:  # noqa: BLE001 — any dialog/threading hiccup → fall back to typing
            return None
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res


def build_menu(window):
    """Native View menu: Admin (opens the overlay) · Reload. Wrapped by the caller
    in try/except — a menu-API mismatch must never keep the window from opening."""
    from webview.menu import Menu, MenuAction  # pywebview 6.2: MenuAction(title, fn)

    return [
        Menu("View", [
            MenuAction("Admin", lambda: window.evaluate_js(
                "window.openAdmin && openAdmin()")),
            MenuAction("Reload", lambda: window.evaluate_js("location.reload()")),
        ]),
    ]


def main():
    # Bare launch defers to a healthy current instance (never kills the patron's live
    # window); pass --replace for an intentional takeover. Stale predecessors and a
    # free port are handled inside start_server_preferred.
    replace = "--replace" in sys.argv
    result = start_server_preferred(replace=replace)
    if result is None:
        url = f"http://127.0.0.1:{DEFAULT_PORT}/"
        print(f"setsweep already running on :{DEFAULT_PORT} — focus that window, "
              f"or relaunch with --replace to take over. ({url})")
        return  # defer: leave the live window untouched, open no second window
    _, port = result
    window = webview.create_window(
        "Setsweep",
        f"http://127.0.0.1:{port}/",
        width=1560,
        height=980,
        min_size=(1100, 700),
        text_select=True,
        js_api=_Api(),                 # exposes pick_folder() to the frontend's browse button
    )
    # the app launching is sacred: a menu-API mismatch falls back to ⌘⇧A, never blocks
    menu = []
    try:
        menu = build_menu(window)
    except Exception as e:  # noqa: BLE001
        print(f"warning: native menu unavailable ({e!r}); use ⌘⇧A for Admin")
    webview.start(menu=menu)  # blocks until the window closes; daemon server dies with us


if __name__ == "__main__":
    main()
