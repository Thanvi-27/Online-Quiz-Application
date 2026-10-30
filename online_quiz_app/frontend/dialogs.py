"""
FRONTEND LAYER  -  frontend/dialogs.py

FormDialog: one reusable pop-up form used for every input dialog (add user, create quiz,
add question, profile ...). Fields are described as data, so no form code is repeated.
"""
import tkinter as tk
from tkinter import ttk


class FormDialog(tk.Toplevel):
    """Generic modal form. fields = [(label, key, kind, options)] with kind in
    entry | password | combo | text. After closing, .result is a dict or None."""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.fields = fields
        self.widgets = {}
        self.transient(parent)
        self.resizable(False, False)
        for row, (label, key, kind, options) in enumerate(fields):
            ttk.Label(self, text=label, wraplength=200, justify="right").grid(
                row=row, column=0, sticky="ne", padx=(12, 6), pady=4)
            if kind == "password":
                widget = ttk.Entry(self, show="*", width=38)
            elif kind == "combo":
                widget = ttk.Combobox(self, values=options, state="readonly", width=35)
                widget.current(0)
            elif kind == "text":
                widget = tk.Text(self, width=38, height=4)
            else:
                widget = ttk.Entry(self, width=38)
            widget.grid(row=row, column=1, padx=(0, 12), pady=4)
            self.widgets[key] = widget
        buttons = ttk.Frame(self)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="left", padx=6)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self._ok() if not isinstance(e.widget, tk.Text) else None)
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window(self)

    def _ok(self):
        data = {}
        for _, key, kind, _ in self.fields:
            w = self.widgets[key]
            data[key] = w.get("1.0", "end").strip() if kind == "text" else w.get().strip()
        self.result = data
        self.destroy()
