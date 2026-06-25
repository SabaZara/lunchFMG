"""LUNCH kiosk scan tester — standalone, no project / venv / pip needed.

A small window for testing the kiosk WITHOUT a USB card reader. Type or paste a
card ID, press Enter (or click "Scan"), and see a big green ALLOWED / red DENIED
result, exactly as the kiosk screen would. It POSTs to the local app's
/api/scan, the same endpoint a keyboard-mode reader triggers.

Uses ONLY the Python standard library (tkinter + urllib), so it runs on the
kiosk's python.org Python 3.11 with nothing installed. Run via run-tester.bat,
or just double-click this .pyw file.

NOTE: a successful scan records a real meal for today (by design), just like a
real tap. Re-scanning the same card the same day shows "already eaten".

If the kiosk app uses a non-default port, set it with the PORT box (default 8000).
"""
from __future__ import annotations

import json
import threading
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import font as tkfont

DEFAULT_PORT = "8000"

NEUTRAL_BG = "#1b2330"
NEUTRAL_FG = "#e8eef7"
ALLOWED_BG = "#11823b"
DENIED_BG = "#b3261e"
FG_ON_COLOR = "#ffffff"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("LUNCH — kiosk scan tester")
        root.geometry("620x420")
        root.configure(bg=NEUTRAL_BG)

        big = tkfont.Font(family="Helvetica", size=46, weight="bold")
        sub = tkfont.Font(family="Helvetica", size=16)
        small = tkfont.Font(family="Helvetica", size=12)

        # Top: controls
        top = tk.Frame(root, bg=NEUTRAL_BG)
        top.pack(fill="x", padx=16, pady=(16, 6))

        tk.Label(top, text="ბარათის ID:", bg=NEUTRAL_BG, fg=NEUTRAL_FG, font=small).pack(side="left")
        self.card_var = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.card_var, font=sub, width=22)
        self.entry.pack(side="left", padx=8)
        self.entry.bind("<Return>", lambda e: self.scan())
        self.entry.focus_set()

        tk.Label(top, text="PORT:", bg=NEUTRAL_BG, fg=NEUTRAL_FG, font=small).pack(side="left", padx=(10, 2))
        self.port_var = tk.StringVar(value=DEFAULT_PORT)
        tk.Entry(top, textvariable=self.port_var, font=small, width=6).pack(side="left")

        self.scan_btn = tk.Button(top, text="Scan", font=sub, command=self.scan,
                                  bg="#2d6cb5", fg="white", activebackground="#255aa0")
        self.scan_btn.pack(side="left", padx=10)

        # Middle: big result
        self.result = tk.Frame(root, bg=NEUTRAL_BG)
        self.result.pack(fill="both", expand=True, padx=16, pady=8)
        self.big_lbl = tk.Label(self.result, text="დაადეთ ბარათი", bg=NEUTRAL_BG,
                                fg=NEUTRAL_FG, font=big, wraplength=560)
        self.big_lbl.pack(expand=True)
        self.sub_lbl = tk.Label(self.result, text="", bg=NEUTRAL_BG, fg=NEUTRAL_FG, font=sub)
        self.sub_lbl.pack()

        # Bottom: status line
        self.status = tk.Label(root, text=f"target: http://127.0.0.1:{DEFAULT_PORT}/api/scan",
                               bg=NEUTRAL_BG, fg="#9fb0c6", font=small, anchor="w")
        self.status.pack(fill="x", side="bottom", padx=16, pady=(0, 10))

    def _set_state(self, bg: str, fg: str, big: str, sub: str) -> None:
        for w in (self.root, self.result, self.big_lbl, self.sub_lbl):
            w.configure(bg=bg)
        self.big_lbl.configure(fg=fg, text=big)
        self.sub_lbl.configure(bg=bg, fg=fg, text=sub)

    def scan(self) -> None:
        card = self.card_var.get().strip()
        if not card:
            return
        port = (self.port_var.get().strip() or DEFAULT_PORT)
        self.status.configure(text=f"scanning {card} -> http://127.0.0.1:{port}/api/scan ...")
        self.scan_btn.configure(state="disabled")
        # network off the UI thread
        threading.Thread(target=self._do_scan, args=(card, port), daemon=True).start()

    def _do_scan(self, card: str, port: str) -> None:
        url = f"http://127.0.0.1:{port}/api/scan"
        try:
            data = json.dumps({"card_id": card}).encode("utf-8")
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as exc:
            self.root.after(0, self._show_error, f"კავშირის შეცდომა: {exc}")
            return
        self.root.after(0, self._show_result, res)

    def _show_result(self, res: dict) -> None:
        self.scan_btn.configure(state="normal")
        if res.get("status") == "ALLOWED":
            self._set_state(ALLOWED_BG, FG_ON_COLOR, "ნებადართულია",
                            f"დრო: {res.get('scanned_at', '')}")
        else:
            self._set_state(DENIED_BG, FG_ON_COLOR, "უარყოფილია",
                            res.get("reason") or "")
        self.status.configure(text=f"last: {res.get('status')}  {res.get('reason') or ''}")
        self.card_var.set("")
        self.entry.focus_set()

    def _show_error(self, msg: str) -> None:
        self.scan_btn.configure(state="normal")
        self._set_state(DENIED_BG, FG_ON_COLOR, "შეცდომა", msg)
        self.status.configure(text=msg + "  (is start.bat running on the kiosk?)")
        self.entry.focus_set()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
