"""Tk UI: a floating status pill that never takes focus, and a dashboard window."""

from __future__ import annotations

import ctypes
import os
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from utter import APP_NAME

if TYPE_CHECKING:
    from utter.app import UtterApp

FONT = "Segoe UI"
STATES: dict[str, tuple[str, str]] = {
    "ready": ("#1f2937", "#d1d5db"),
    "listening": ("#dc2626", "#ffffff"),
    "transcribing": ("#2563eb", "#ffffff"),
    "done": ("#16a34a", "#ffffff"),
    "warn": ("#d97706", "#ffffff"),
    "error": ("#7f1d1d", "#ffffff"),
}

_GWL_EXSTYLE = -20
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080


class Pill:
    def __init__(self, root: tk.Tk, ready_text: str, on_click: Callable[[], None]) -> None:
        self.ready_text = ready_text
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.94)
        self.label = tk.Label(self.win, font=(FONT, 10, "bold"), padx=18, pady=8, cursor="hand2")
        self.label.pack()
        self.label.bind("<Button-1>", lambda _e: on_click())
        self._revert: str | None = None
        self.win.update_idletasks()
        self._make_non_activating()
        self.set("ready", ready_text)

    def _make_non_activating(self) -> None:
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.win.winfo_id())
        style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW)

    def _place(self) -> None:
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = self.win.winfo_screenheight() - h - 72
        self.win.geometry(f"+{x}+{y}")

    def set(self, state: str, text: str, revert_ms: int | None = None) -> None:
        if self._revert is not None:
            self.win.after_cancel(self._revert)
            self._revert = None
        bg, fg = STATES[state]
        self.label.config(text=text, bg=bg, fg=fg)
        self.win.config(bg=bg)
        self._place()
        if revert_ms:
            self._revert = self.win.after(revert_ms, lambda: self.set("ready", self.ready_text))


class Dashboard:
    def __init__(self, root: tk.Tk, app: UtterApp) -> None:
        self.app = app
        self.win = tk.Toplevel(root)
        self.win.title(f"{APP_NAME} dashboard")
        self.win.geometry("760x520")
        self.win.protocol("WM_DELETE_WINDOW", self.win.withdraw)
        self.win.withdraw()
        style = ttk.Style(self.win)
        style.configure("Big.TLabel", font=(FONT, 13))
        style.configure("Head.TLabel", font=(FONT, 16, "bold"))
        style.configure("Good.TLabel", font=(FONT, 13, "bold"), foreground="#15803d")
        style.configure("Bad.TLabel", font=(FONT, 13, "bold"), foreground="#b91c1c")

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self._build_proof(nb)
        self._build_history(nb)
        self._build_glossary(nb)
        bottom = ttk.Frame(self.win)
        bottom.pack(fill="x", padx=10, pady=8)
        ttk.Button(bottom, text="Open config folder",
                   command=lambda: os.startfile(app.config_dir)).pack(side="left")
        ttk.Button(bottom, text=f"Quit {APP_NAME}", command=app.quit).pack(side="right")

    # --- Proof & savings -------------------------------------------------------------------
    def _build_proof(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="Proof & savings")
        ttk.Label(tab, text="Everything runs on this PC", style="Head.TLabel").pack(anchor="w")
        self.proof_vars: dict[str, tk.StringVar] = {}
        self.net_label = ttk.Label(tab, style="Good.TLabel")
        self.net_label.pack(anchor="w", pady=(10, 2))
        self.polish_var = tk.BooleanVar(value=self.app.settings.polish_enabled)
        ttk.Checkbutton(tab, text="AI polish with a local LLM (grammar, self-corrections)",
                        variable=self.polish_var,
                        command=lambda: self.app.set_polish(self.polish_var.get())
                        ).pack(anchor="w", pady=(4, 2))
        for key in ("engine", "polish", "audio", "words", "cap", "price", "latency", "count"):
            var = tk.StringVar()
            self.proof_vars[key] = var
            ttk.Label(tab, textvariable=var, style="Big.TLabel").pack(anchor="w", pady=2)

    def refresh_proof(self) -> None:
        a, s, cfg = self.app, self.app.stats, self.app.settings
        blocked = a.guard.blocked_count
        self.net_label.config(
            text=f"Network requests: {blocked}" + ("  (all blocked)" if blocked else ""),
            style="Good.TLabel" if blocked == 0 else "Bad.TLabel",
        )
        median = s.median_latency()
        price = cfg.wispr_pro_monthly_usd
        self.proof_vars["engine"].set(f"Speech model: Whisper {a.model_name} on CPU (offline)")
        if not cfg.polish_enabled:
            polish = "off"
        elif a.polisher_ready:
            polish = f"{a.polisher.model} via Ollama on 127.0.0.1 (this PC)"
        else:
            polish = "starting… (needs Ollama running)"
        self.proof_vars["polish"].set(f"AI polish: {polish}")
        self.proof_vars["audio"].set("Audio saved to disk: never  ·  History: memory only")
        self.proof_vars["words"].set(f"Words dictated this week: {s.words_week:,}  "
                                     f"(total {s.words_total:,})")
        self.proof_vars["cap"].set(
            f"Over Wispr Flow's free cap ({cfg.wispr_free_weekly_words:,}/week): "
            f"{s.words_over_free_cap(cfg.wispr_free_weekly_words):,} words")
        self.proof_vars["price"].set(f"Wispr Flow Pro: ${price:.0f}/month (${price * 12:.0f}/year)"
                                     f"  →  {APP_NAME}: $0, no account, no cap")
        self.proof_vars["latency"].set(
            "Median release-to-text: " + (f"{median:.2f}s" if median is not None else "-"))
        self.proof_vars["count"].set(f"Dictations: {s.dictations_total:,}")

    # --- History ---------------------------------------------------------------------------
    def _build_history(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="History")
        self.hist_list = tk.Listbox(tab, width=34, font=(FONT, 9), exportselection=False)
        self.hist_list.pack(side="left", fill="y")
        self.hist_list.bind("<<ListboxSelect>>", lambda _e: self._show_item())
        right = ttk.Frame(tab, padding=(10, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Raw transcript (select a misheard word, then Learn correction)"
                  ).pack(anchor="w")
        self.raw_text = tk.Text(right, height=5, wrap="word", font=(FONT, 10))
        self.raw_text.pack(fill="x")
        ttk.Label(right, text="Inserted text").pack(anchor="w", pady=(8, 0))
        self.clean_text = tk.Text(right, height=5, wrap="word", font=(FONT, 10))
        self.clean_text.pack(fill="x")
        self.rules_var = tk.StringVar()
        ttk.Label(right, textvariable=self.rules_var, wraplength=420, justify="left"
                  ).pack(anchor="w", pady=6)
        buttons = ttk.Frame(right)
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="Copy raw", command=lambda: self._copy(self.raw_text)
                   ).pack(side="left")
        ttk.Button(buttons, text="Copy inserted", command=lambda: self._copy(self.clean_text)
                   ).pack(side="left", padx=6)
        ttk.Button(buttons, text="Learn correction…", command=self._learn).pack(side="left")

    def refresh_history(self) -> None:
        self.hist_list.delete(0, "end")
        for d in self.app.history.items():
            preview = d.clean.replace("\n", " ")[:28]
            self.hist_list.insert("end", f"{d.at:%H:%M:%S} {d.mode.value:<7} {preview}")

    def _selected(self) -> int | None:
        sel = self.hist_list.curselection()  # type: ignore[no-untyped-call]
        return int(sel[0]) if sel else None

    def _show_item(self) -> None:
        idx = self._selected()
        items = self.app.history.items()
        if idx is None or idx >= len(items):
            return
        d = items[idx]
        for widget, value in ((self.raw_text, d.raw), (self.clean_text, d.clean)):
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
        rules = "; ".join(d.rules) or "no changes"
        self.rules_var.set(f"App: {d.app or '?'} · mode {d.mode.value} · {d.action} · "
                           f"{d.latency_s:.2f}s\nChanges: {rules}")

    def _copy(self, widget: tk.Text) -> None:
        self.win.clipboard_clear()
        self.win.clipboard_append(widget.get("1.0", "end-1c"))

    def _learn(self) -> None:
        try:
            heard = self.raw_text.get("sel.first", "sel.last").strip()
        except tk.TclError:
            heard = ""
        heard = simpledialog.askstring(APP_NAME, "What did it hear? (as transcribed)",
                                       initialvalue=heard, parent=self.win) or ""
        if not heard.strip():
            return
        written = simpledialog.askstring(APP_NAME, f"What should '{heard}' be written as?",
                                         parent=self.win) or ""
        if not written.strip():
            return
        if messagebox.askyesno(APP_NAME, f"Always write '{written}' when I hear '{heard}'?",
                               parent=self.win):
            self.app.add_glossary(heard.strip(), written.strip())
            self.refresh_glossary()

    # --- Glossary & snippets ---------------------------------------------------------------
    def _build_glossary(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Glossary & snippets")
        ttk.Label(tab, text="Glossary (stored locally in config.json)").pack(anchor="w")
        self.gloss = ttk.Treeview(tab, columns=("heard", "written"), show="headings", height=8)
        self.gloss.heading("heard", text="When I hear")
        self.gloss.heading("written", text="Write")
        self.gloss.pack(fill="x")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=6)
        self.heard_var, self.written_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(row, textvariable=self.heard_var, width=24).pack(side="left")
        ttk.Label(row, text=" → ").pack(side="left")
        ttk.Entry(row, textvariable=self.written_var, width=24).pack(side="left")
        ttk.Button(row, text="Add", command=self._add_gloss).pack(side="left", padx=6)
        ttk.Button(row, text="Delete selected", command=self._delete_gloss).pack(side="left")
        ttk.Label(tab, text="Snippets (say the trigger; static text only, never executed)"
                  ).pack(anchor="w", pady=(8, 0))
        self.snips = ttk.Treeview(tab, columns=("trigger", "text"), show="headings", height=3)
        self.snips.heading("trigger", text="Say")
        self.snips.heading("text", text="Inserts")
        self.snips.pack(fill="x")
        mem = ttk.LabelFrame(tab, text="Personal memory (personal.json on this PC)", padding=6)
        mem.pack(fill="x", pady=(8, 0))
        self.learn_var = tk.BooleanVar(value=self.app.settings.learn_enabled)
        ttk.Checkbutton(mem, text="Learn from my dictations and corrections (Ctrl+Alt+L)",
                        variable=self.learn_var,
                        command=lambda: self.app.set_learning(self.learn_var.get())
                        ).pack(anchor="w")
        self.memory_var = tk.StringVar()
        ttk.Label(mem, textvariable=self.memory_var, wraplength=680, justify="left"
                  ).pack(anchor="w", pady=4)
        ttk.Button(mem, text="Forget everything", command=self._forget).pack(anchor="w")

    def refresh_glossary(self) -> None:
        self.gloss.delete(*self.gloss.get_children())
        for i, g in enumerate(self.app.settings.glossary):
            self.gloss.insert("", "end", iid=str(i), values=(g.heard, g.written))
        self.snips.delete(*self.snips.get_children())
        for s in self.app.settings.snippets:
            self.snips.insert("", "end", values=(s.trigger, s.text.replace("\n", " ⏎ ")))
        m = self.app.memory
        top = sorted(m.vocab.items(), key=lambda kv: -kv[1])[:12]
        terms = ", ".join(f"{t} ×{n}" for t, n in top) or "nothing yet"
        self.memory_var.set(f"Words it is learning: {terms}\nCorrections learned: "
                            f"{m.corrections_learned} · Style examples: {len(m.style_examples)}")

    def _forget(self) -> None:
        if messagebox.askyesno(APP_NAME, "Delete all learned words and style examples?",
                               parent=self.win):
            self.app.forget_memory()
            self.refresh_glossary()

    def _add_gloss(self) -> None:
        heard, written = self.heard_var.get().strip(), self.written_var.get().strip()
        if heard and written:
            self.app.add_glossary(heard, written)
            self.heard_var.set("")
            self.written_var.set("")
            self.refresh_glossary()

    def _delete_gloss(self) -> None:
        for iid in self.gloss.selection():
            self.app.remove_glossary(int(iid))
        self.refresh_glossary()

    # --- Visibility ------------------------------------------------------------------------
    def toggle(self) -> None:
        if self.win.state() == "withdrawn":
            self.refresh_proof()
            self.refresh_history()
            self.refresh_glossary()
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        else:
            self.win.withdraw()

    def tick(self) -> None:
        if self.win.state() != "withdrawn":
            self.refresh_proof()
