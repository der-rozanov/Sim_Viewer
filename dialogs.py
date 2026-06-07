# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk


COLORS = [
    "steelblue", "tomato", "seagreen", "darkorange", "mediumpurple",
    "saddlebrown", "royalblue", "crimson", "teal", "gray",
]


class _AddChartDialog(tk.Toplevel):
    def __init__(self, parent, channels: dict, callback):
        super().__init__(parent)
        self.title("Добавить график")
        self.resizable(False, False)
        self.grab_set()
        self.callback = callback

        ch_display = [f"{k}  —  {v[0]}, {v[1]}" for k, v in channels.items()]

        def _label_to_key(lbl):
            return lbl.split("  —  ")[0].strip()

        ttk.Label(self, text="Ось X:").grid(row=0, column=0, padx=14, pady=(18, 4), sticky=tk.W)
        self.x_var = tk.StringVar(value=ch_display[0])
        ttk.Combobox(self, textvariable=self.x_var, values=ch_display,
                     state="readonly", width=28).grid(row=0, column=1, padx=14, pady=(18, 4))

        ttk.Label(self, text="Ось Y:").grid(row=1, column=0, padx=14, pady=4, sticky=tk.W)
        self.y_var = tk.StringVar(value=ch_display[1] if len(ch_display) > 1 else ch_display[0])
        ttk.Combobox(self, textvariable=self.y_var, values=ch_display,
                     state="readonly", width=28).grid(row=1, column=1, padx=14, pady=4)

        ttk.Label(self, text="Цвет:").grid(row=2, column=0, padx=14, pady=4, sticky=tk.W)
        self.color_var = tk.StringVar(value="steelblue")
        ttk.Combobox(self, textvariable=self.color_var, values=COLORS,
                     state="readonly", width=28).grid(row=2, column=1, padx=14, pady=4)

        self.deg_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Перевести Y в градусы",
                        variable=self.deg_var).grid(row=3, column=0, columnspan=2,
                                                    padx=14, pady=4, sticky=tk.W)

        btn = ttk.Frame(self)
        btn.grid(row=4, column=0, columnspan=2, pady=(12, 18))
        ttk.Button(btn, text="Добавить", command=lambda: self._ok(_label_to_key)).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="Отмена",   command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.geometry(f"+{parent.winfo_rootx() + 180}+{parent.winfo_rooty() + 160}")

    def _ok(self, label_to_key):
        self.callback(label_to_key(self.x_var.get()), label_to_key(self.y_var.get()),
                      self.color_var.get(), self.deg_var.get())
        self.destroy()


class _ChartSettingsDialog(tk.Toplevel):
    def __init__(self, parent, spec, callback):
        super().__init__(parent)
        self.title(f"Настройки: {spec.label}")
        self.resizable(False, False)
        self.grab_set()
        self.spec     = spec
        self.callback = callback

        ttk.Label(self, text="Заголовок:").grid(row=0, column=0, padx=14, pady=(18, 4), sticky=tk.W)
        self.lbl_var = tk.StringVar(value=spec.label)
        ttk.Entry(self, textvariable=self.lbl_var, width=26).grid(row=0, column=1, padx=14, pady=(18, 4))

        ttk.Label(self, text="Цвет линии:").grid(row=1, column=0, padx=14, pady=4, sticky=tk.W)
        self.color_var = tk.StringVar(value=spec.color)
        ttk.Combobox(self, textvariable=self.color_var, values=COLORS,
                     state="readonly", width=24).grid(row=1, column=1, padx=14, pady=4)

        ttk.Label(self, text="Y min:").grid(row=2, column=0, padx=14, pady=4, sticky=tk.W)
        self.ymin_var = tk.StringVar(value="авто")
        ttk.Entry(self, textvariable=self.ymin_var, width=12).grid(row=2, column=1, padx=14, pady=4, sticky=tk.W)

        ttk.Label(self, text="Y max:").grid(row=3, column=0, padx=14, pady=4, sticky=tk.W)
        self.ymax_var = tk.StringVar(value="авто")
        ttk.Entry(self, textvariable=self.ymax_var, width=12).grid(row=3, column=1, padx=14, pady=4, sticky=tk.W)

        ttk.Label(self, text="Толщина линии:").grid(row=4, column=0, padx=14, pady=4, sticky=tk.W)
        self.lw_var = tk.StringVar(value="1.5")
        ttk.Combobox(self, textvariable=self.lw_var, values=["0.8", "1.0", "1.5", "2.0", "2.5"],
                     state="readonly", width=10).grid(row=4, column=1, padx=14, pady=4, sticky=tk.W)

        self.deg_var = tk.BooleanVar(value=spec.deg)
        ttk.Checkbutton(self, text="Перевести Y в градусы",
                        variable=self.deg_var).grid(row=5, column=0, columnspan=2,
                                                    padx=14, pady=4, sticky=tk.W)

        self.equal_scale_var = tk.BooleanVar(value=getattr(spec, "equal_scale", False))
        ttk.Checkbutton(self, text="Одинаковый масштаб осей X и Y",
                        variable=self.equal_scale_var).grid(row=6, column=0, columnspan=2,
                                                            padx=14, pady=4, sticky=tk.W)

        btn = ttk.Frame(self)
        btn.grid(row=7, column=0, columnspan=2, pady=(12, 18))
        ttk.Button(btn, text="Применить", command=self._ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="Отмена",    command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.geometry(f"+{parent.winfo_rootx() + 200}+{parent.winfo_rooty() + 180}")

    def _ok(self):
        self.spec.label       = self.lbl_var.get()
        self.spec.color       = self.color_var.get()
        self.spec.deg         = self.deg_var.get()
        self.spec.equal_scale = self.equal_scale_var.get()
        try:
            self.spec.ymin = float(self.ymin_var.get())
        except ValueError:
            self.spec.ymin = None
        try:
            self.spec.ymax = float(self.ymax_var.get())
        except ValueError:
            self.spec.ymax = None
        try:
            self.spec.lw = float(self.lw_var.get())
        except ValueError:
            self.spec.lw = 1.5
        self.callback()
        self.destroy()
