# -*- coding: utf-8 -*-

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import datetime
import matplotlib.gridspec as gridspec


# ---------------------------------------------------------------------------
# Мок-данные (замените на load_log() в реальной версии)
# ---------------------------------------------------------------------------

def _make_mock_data():
    np.random.seed(42)
    t = np.linspace(0, 40, 4000)
    dt = t[1] - t[0]
    h = 100 + 12 * np.sin(0.18 * t) + 0.4 * t
    x = 30 * t
    Va = 30 + 2.5 * np.sin(0.38 * t) + 0.4 * np.random.randn(len(t))
    alpha = np.radians(3 + 2.5 * np.sin(0.32 * t) + 0.3 * np.random.randn(len(t)))
    theta = np.radians(5 + 3.2 * np.sin(0.18 * t))
    q = np.gradient(theta, t)
    delta_e = np.radians(-2 + 1.8 * np.sin(0.32 * t))
    throttle = np.clip(0.44 + 0.08 * np.sin(0.14 * t), 0, 1)
    E_thrust = np.cumsum(throttle * Va) * dt
    return {
        "t": t, "h": h, "x": x, "Va": Va,
        "alpha_true": alpha, "theta": theta, "q": q,
        "delta_e": delta_e, "throttle": throttle, "E_thrust": E_thrust,
        "meta": {
            "scenario": "Демо: управление высотой",
            "description": "Тестовые данные — замените реальным .flightlog",
            "saved_at": "2026-06-07T12:00:00",
        },
    }


# ---------------------------------------------------------------------------
# Загрузка .flightlog (standalone — не зависит от flight_logger.py)
# ---------------------------------------------------------------------------

def load_log(path: str) -> dict:
    if not os.path.exists(path) and os.path.exists(path + ".npz"):
        path = path + ".npz"
    raw = np.load(path, allow_pickle=False)
    result = {}
    for key in raw.files:
        if key == "meta_json":
            result["meta"] = json.loads(str(raw["meta_json"][0]))
        else:
            result[key] = raw[key]
    return result


# ---------------------------------------------------------------------------
# Справочник каналов: ключ → (название, единица)
# ---------------------------------------------------------------------------

CHANNELS = {
    # Основные каналы состояния
    "t":           ("Время",                      "с"),
    "h":           ("Высота",                     "м"),
    "x":           ("Дальность",                  "м"),
    "u":           ("Прод. скорость (связ.)",     "м/с"),
    "w":           ("Норм. скорость (связ.)",     "м/с"),
    "Va":          ("Возд. скорость",             "м/с"),
    "theta":       ("Угол тангажа",               "рад"),
    "q":           ("Угл. скор. тангажа",         "рад/с"),
    "gamma":       ("Угол траектории",            "рад"),
    # Аэродинамика
    "alpha_true":  ("УА истинный",               "рад"),
    "alpha_probe": ("УА зонд",                   "рад"),
    "alpha_est":   ("УА оценка ИНС+GPS",         "рад"),
    # Управление
    "delta_e":     ("Руль высоты",               "рад"),
    "throttle":    ("Тяга",                      "о.е."),
    # Ветер
    "wind_x":      ("Ветер горизонт.",           "м/с"),
    "wind_h":      ("Ветер вертикаль.",          "м/с"),
    # Энергия
    "E_kin":       ("Кинет. энергия",            "Дж"),
    "E_pot":       ("Потенц. энергия",           "Дж"),
    "E_mech":      ("Полная мех. энергия",       "Дж"),
    "P_thrust":    ("Мощность двигателя",        "о.е.·м/с"),
    "E_thrust":    ("Накопл. энергия двиг.",     "о.е.·м"),
    # Уставки
    "h_ref":       ("Уставка высоты",            "м"),
    "theta_ref":   ("Уставка тангажа",           "рад"),
    # Парный прогон
    "paired_h":         ("Высота (пара)",        "м"),
    "paired_Va":        ("Возд. скор. (пара)",   "м/с"),
    "paired_alpha_est": ("УА оценка (пара)",     "рад"),
    "paired_delta_e":   ("Руль высоты (пара)",   "рад"),
    "paired_throttle":  ("Тяга (пара)",          "о.е."),
}


# Преднастроенные графики
PRESETS = [
    {"label": "Траектория",  "x": "x",   "y": "h",          "deg": False, "color": "royalblue", "show_arrow": True},
    {"label": "Угол атаки",  "x": "t",   "y": "alpha_true", "deg": True,  "color": "tomato"},
    {"label": "Тангаж",      "x": "t",   "y": "theta",      "deg": True,  "color": "steelblue"},
    {"label": "Скорость",    "x": "t",   "y": "Va",         "deg": False, "color": "seagreen"},
]


# ---------------------------------------------------------------------------
# Спецификация одного графика
# ---------------------------------------------------------------------------

class ChartSpec:
    def __init__(self, x_ch, y_ch, label=None, color="steelblue", deg=False,
                 show_arrow=False):
        self.x_ch       = x_ch
        self.y_ch       = y_ch
        self.label      = label or f"{y_ch} / {x_ch}"
        self.color      = color
        self.deg        = deg
        self.show_arrow = show_arrow  # зарезервировано, не используется пока
        self.ax         = None
        self._dyn_line  = None
        self._dyn_dot   = None
        self._xdata     = None
        self._ydata     = None


# ---------------------------------------------------------------------------
# Диалог добавления произвольного графика
# ---------------------------------------------------------------------------

class _AddChartDialog(tk.Toplevel):
    def __init__(self, parent, channels, callback):
        super().__init__(parent)
        self.title("Добавить график")
        self.resizable(False, False)
        self.grab_set()
        self.callback = callback

        ch_keys = list(channels.keys())
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
        colors = ["steelblue", "tomato", "seagreen", "darkorange", "mediumpurple",
                  "saddlebrown", "royalblue", "crimson", "teal", "gray"]
        ttk.Combobox(self, textvariable=self.color_var, values=colors,
                     state="readonly", width=28).grid(row=2, column=1, padx=14, pady=4)

        self.deg_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Перевести Y в градусы",
                        variable=self.deg_var).grid(row=3, column=0, columnspan=2,
                                                    padx=14, pady=4, sticky=tk.W)

        btn = ttk.Frame(self)
        btn.grid(row=4, column=0, columnspan=2, pady=(12, 18))
        ttk.Button(btn, text="Добавить", command=lambda: self._ok(_label_to_key)).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="Отмена",   command=self.destroy).pack(side=tk.LEFT, padx=6)

        x_off = parent.winfo_rootx() + 180
        y_off = parent.winfo_rooty() + 160
        self.geometry(f"+{x_off}+{y_off}")

    def _ok(self, label_to_key):
        x = label_to_key(self.x_var.get())
        y = label_to_key(self.y_var.get())
        self.callback(x, y, self.color_var.get(), self.deg_var.get())
        self.destroy()


# ---------------------------------------------------------------------------
# Диалог настроек графика (заглушка с показом запланированных опций)
# ---------------------------------------------------------------------------

class _ChartSettingsDialog(tk.Toplevel):
    def __init__(self, parent, spec: ChartSpec, callback):
        super().__init__(parent)
        self.title(f"Настройки: {spec.label}")
        self.resizable(False, False)
        self.grab_set()
        self.spec = spec
        self.callback = callback

        ttk.Label(self, text="Заголовок:").grid(row=0, column=0, padx=14, pady=(18, 4), sticky=tk.W)
        self.lbl_var = tk.StringVar(value=spec.label)
        ttk.Entry(self, textvariable=self.lbl_var, width=26).grid(row=0, column=1, padx=14, pady=(18, 4))

        ttk.Label(self, text="Цвет линии:").grid(row=1, column=0, padx=14, pady=4, sticky=tk.W)
        self.color_var = tk.StringVar(value=spec.color)
        colors = ["steelblue", "tomato", "seagreen", "darkorange", "mediumpurple",
                  "saddlebrown", "royalblue", "crimson", "teal", "gray"]
        ttk.Combobox(self, textvariable=self.color_var, values=colors,
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

        btn = ttk.Frame(self)
        btn.grid(row=6, column=0, columnspan=2, pady=(12, 18))
        ttk.Button(btn, text="Применить", command=self._ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="Отмена",    command=self.destroy).pack(side=tk.LEFT, padx=6)

        x_off = parent.winfo_rootx() + 200
        y_off = parent.winfo_rooty() + 180
        self.geometry(f"+{x_off}+{y_off}")

    def _ok(self):
        self.spec.label = self.lbl_var.get()
        self.spec.color = self.color_var.get()
        self.spec.deg   = self.deg_var.get()
        try:
            ymin = float(self.ymin_var.get())
            self.spec.ymin = ymin
        except ValueError:
            self.spec.ymin = None
        try:
            ymax = float(self.ymax_var.get())
            self.spec.ymax = ymax
        except ValueError:
            self.spec.ymax = None
        try:
            self.spec.lw = float(self.lw_var.get())
        except ValueError:
            self.spec.lw = 1.5
        self.callback()
        self.destroy()


# ---------------------------------------------------------------------------
# Главное приложение
# ---------------------------------------------------------------------------

class FlightViewerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FlightLog Viewer — демо")
        self.root.geometry("1340x820")
        self.root.minsize(900, 600)

        self.data: dict | None = None
        self.charts: list[ChartSpec] = []

        self._anim_obj:    FuncAnimation | None = None
        self._anim_running = False
        self._anim_frame   = 0
        self._anim_speed   = 2.0
        self._slider_from_anim = False
        self._focus_spec:  ChartSpec | None = None
        self._picked_spec: ChartSpec | None = None

        self._build_ui()
        self._load_mock()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()
        self._build_chart_area()
        self._build_anim_controls()
        self._build_statusbar()

    def _build_menu(self):
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="Открыть...",            command=self._open_file,  accelerator="Ctrl+O")
        fm.add_command(label="Загрузить демо-данные", command=self._load_mock)
        fm.add_separator()
        fm.add_command(label="Выход", command=self.root.quit)
        mb.add_cascade(label="Файл", menu=fm)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_command(label="Добавить график...", command=self._add_custom_dialog)
        vm.add_separator()
        vm.add_command(label="Очистить все",       command=self._clear_charts)
        mb.add_cascade(label="Вид", menu=vm)

        self.root.config(menu=mb)
        self.root.bind("<Control-o>", lambda _: self._open_file())

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="Готовые:").pack(side=tk.LEFT, padx=(0, 4))
        for p in PRESETS:
            ttk.Button(bar, text=p["label"],
                       command=lambda p=p: self._add_preset(p)).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(bar, text="＋ Добавить график",
                   command=self._add_custom_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Очистить",
                   command=self._clear_charts).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(bar, text="💾 Сохранить GIF",
                   command=self._save_gif).pack(side=tk.LEFT, padx=2)

    def _build_chart_area(self):
        self.fig = Figure(facecolor="#f5f5f5")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        w = self.canvas.get_tk_widget()
        w.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Контекстное меню (ПКМ)
        self._ctx = tk.Menu(self.root, tearoff=0)
        self._ctx.add_command(label="Добавить график...", command=self._add_custom_dialog)
        self._ctx.add_command(label="Настройки графика...", command=self._open_settings_for_picked)
        self._ctx.add_command(label="✕ Удалить график",    command=self._delete_picked)  # idx 2
        self._ctx.add_separator()
        self._ctx.add_command(label="★ Сделать главным",   command=self._focus_picked)   # idx 4
        self._ctx.add_command(label="☆ Убрать из фокуса", command=self._unfocus)         # idx 5
        self._ctx.add_separator()
        self._ctx.add_command(label="Очистить все", command=self._clear_charts)

        w.bind("<Button-3>", self._on_right_click)
        self.canvas.mpl_connect("pick_event", self._on_pick)

    def _build_anim_controls(self):
        ctrl = ttk.Frame(self.root, padding=(8, 4))
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_play = ttk.Button(ctrl, text="▶  Пуск", width=10, command=self._toggle_anim)
        self.btn_play.pack(side=tk.LEFT)

        ttk.Button(ctrl, text="↺", width=3, command=self._reset_anim).pack(side=tk.LEFT, padx=2)

        self.time_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(ctrl, orient=tk.HORIZONTAL, variable=self.time_var,
                                from_=0, to=100, command=self._on_slider)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        self.time_lbl = ttk.Label(ctrl, text="  0.0 с", width=8)
        self.time_lbl.pack(side=tk.LEFT)

        ttk.Separator(ctrl, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(ctrl, text="Скорость:").pack(side=tk.LEFT)

        self.speed_var = tk.StringVar(value="x2.0")
        speeds = ["x0.25", "x0.5", "x1.0", "x2.0", "x5.0", "x10.0"]
        spd = ttk.Combobox(ctrl, textvariable=self.speed_var, values=speeds,
                           width=6, state="readonly")
        spd.pack(side=tk.LEFT, padx=4)
        spd.bind("<<ComboboxSelected>>", self._on_speed_change)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Демо-режим")
        ttk.Label(self.root, textvariable=self.status_var,
                  relief=tk.SUNKEN, anchor=tk.W,
                  padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def _load_mock(self):
        self._apply_data(_make_mock_data(), source="Демо-данные")

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Открыть полётный лог",
            filetypes=[("Flight log", "*.flightlog"), ("NPZ", "*.npz"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        try:
            data = load_log(path)
        except Exception as e:
            messagebox.showerror("Ошибка загрузки", f"Не удалось открыть файл:\n{e}")
            return
        self._apply_data(data, source=os.path.basename(path))

    def _apply_data(self, data: dict, source: str):
        """Загрузить данные, сбросить состояние, показать преднастроенные графики."""
        self._stop_anim()
        self.data        = data
        self._anim_frame = 0
        self.slider.config(to=len(data["t"]) - 1)

        m        = data.get("meta", {})
        scenario = m.get("scenario", source)
        self.root.title(f"FlightLog Viewer — {scenario}")

        wind   = m.get("wind", {})
        saved  = m.get("saved_at", "")
        flags  = [k for k in ("has_probe", "has_est", "has_h_ref", "has_paired") if m.get(k)]
        extras = f"  |  {', '.join(flags)}" if flags else ""
        self.status_var.set(
            f"{source}  |  {scenario}"
            + (f"  |  Vw={wind.get('Vw_const', 0):+.1f} м/с" if wind else "")
            + (f"  |  {saved}" if saved else "")
            + extras
        )

        # Добавляем только те преднастроенные графики, чьи каналы есть в файле
        self.charts = []
        for p in PRESETS:
            if data.get(p["x"]) is not None and data.get(p["y"]) is not None:
                self.charts.append(
                    ChartSpec(p["x"], p["y"], p["label"], p["color"],
                              p.get("deg", False), p.get("show_arrow", False))
                )
        self._focus_spec  = None
        self._picked_spec = None
        self._redraw()

    # ------------------------------------------------------------------
    # Управление графиками
    # ------------------------------------------------------------------

    def _add_preset(self, p):
        if self.data is None:
            return
        for c in self.charts:
            if c.x_ch == p["x"] and c.y_ch == p["y"]:
                return  # уже есть
        self.charts.append(ChartSpec(p["x"], p["y"], p["label"], p["color"],
                                     p.get("deg", False), p.get("show_arrow", False)))
        self._redraw()

    def _add_custom_dialog(self):
        if self.data is None:
            messagebox.showinfo("", "Сначала загрузите данные (Файл → Загрузить демо-данные)")
            return
        _AddChartDialog(self.root, CHANNELS, self._on_add_custom)

    def _on_add_custom(self, x_ch, y_ch, color, deg):
        self.charts.append(ChartSpec(x_ch, y_ch, color=color, deg=deg))
        self._redraw()

    def _clear_charts(self):
        self._stop_anim()
        self.charts = []
        self._draw_empty()

    def _delete_picked(self):
        if self._picked_spec is None:
            return
        if self._focus_spec is self._picked_spec:
            self._focus_spec = None
        self.charts.remove(self._picked_spec)
        self._picked_spec = None
        self._redraw()

    def _focus_picked(self):
        if self._picked_spec is not None:
            self._focus_spec = self._picked_spec
            self._redraw()

    def _unfocus(self):
        self._focus_spec = None
        self._redraw()

    def _save_gif(self):
        if self.data is None or not self.charts:
            messagebox.showinfo("", "Нет данных для экспорта")
            return
        try:
            from PIL import Image
        except ImportError:
            messagebox.showerror("Ошибка", "Нужна библиотека Pillow:\n  pip install pillow")
            return

        gif_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gif_exports")
        os.makedirs(gif_dir, exist_ok=True)
        fname = f"flight_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.gif"
        path  = os.path.join(gif_dir, fname)

        was_running  = self._anim_running
        saved_frame  = self._anim_frame
        self._stop_anim()
        self._anim_frame = 0
        self._redraw()

        t       = self.data["t"]
        n       = len(t)
        dt      = t[1] - t[0]
        fps_gif = 20
        stride  = max(1, int(self._anim_speed / fps_gif / dt))
        total   = max(1, (n + stride - 1) // stride)

        frames_pil: list = []
        self._gif_active = True

        # Один полный рендер → захватываем статичный фон (оси, подписи, блёклые линии)
        self.fig.canvas.draw()
        gif_bg = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        w, h   = self.fig.canvas.get_width_height()

        def _render_frame(fn: int):
            if not self._gif_active:
                self.status_var.set("Экспорт GIF отменён")
                return

            if fn >= total:
                self.status_var.set(f"Запись файла… ({len(frames_pil)} кадров)")
                self._gif_write_thread(frames_pil, path, fps_gif,
                                       was_running, saved_frame)
                return

            i = min(fn * stride, n - 1)

            # Восстанавливаем фон — без полного перерисовывания фигуры
            self.fig.canvas.restore_region(gif_bg)

            # Рисуем только динамические артисты
            for spec in self.charts:
                if spec._dyn_line is None or spec._xdata is None:
                    continue
                self._update_spec_to(spec, i)
                spec.ax.draw_artist(spec._dyn_line)
                spec.ax.draw_artist(spec._dyn_dot)

            self.fig.canvas.blit(self.fig.bbox)

            buf = self.fig.canvas.buffer_rgba()
            img = Image.frombuffer("RGBA", (w, h), buf, "raw", "RGBA", 0, 1)
            frames_pil.append(img.convert("RGB"))

            pct = int((fn + 1) / total * 100)
            self.status_var.set(f"Рендер кадров: {fn+1}/{total}  ({pct}%)")
            self.root.after(1, lambda: _render_frame(fn + 1))

        _render_frame(0)

    def _gif_write_thread(self, frames: list, path: str, fps: int,
                          was_running: bool, saved_frame: int):
        """Запись GIF в фоновом потоке (не блокирует UI)."""
        import threading

        def _worker():
            try:
                frames[0].save(
                    path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=1000 // fps,
                    loop=0,
                    optimize=False,   # оптимизация slow — отключаем
                )
                self.root.after(0, lambda: self._on_gif_done(path, was_running, saved_frame))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: messagebox.showerror("Ошибка GIF", err))
                self.root.after(0, lambda: self._on_gif_done(None, was_running, saved_frame))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_gif_done(self, path: str | None, was_running: bool, saved_frame: int):
        self._gif_active = False
        if path:
            fname = os.path.basename(path)
            self.status_var.set(f"✓ GIF сохранён: {fname}")
            messagebox.showinfo("Готово", f"GIF сохранён:\n{path}")
        self._anim_frame = saved_frame
        self._redraw()
        if was_running:
            self._start_anim()

    def _open_settings_for_picked(self):
        spec = self._picked_spec
        if spec is None:
            messagebox.showinfo("", "Кликните на график сначала (ЛКМ), затем ПКМ → Настройки")
            return
        _ChartSettingsDialog(self.root, spec, self._redraw)

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def _draw_empty(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_axis_off()
        ax.text(0.5, 0.56, "Откройте лог-файл или загрузите демо-данные",
                ha="center", va="center", fontsize=13, color="#999",
                transform=ax.transAxes)
        ax.text(0.5, 0.46, "Файл → Загрузить демо-данные    или    ПКМ → Добавить график",
                ha="center", va="center", fontsize=10, color="#bbb",
                transform=ax.transAxes)
        self.canvas.draw()

    def _redraw(self):
        was_running = self._anim_running
        self._stop_anim()
        self.fig.clear()

        if not self.charts or self.data is None:
            self._draw_empty()
            return

        # Если focus_spec удалён из списка — сбросить
        if self._focus_spec not in self.charts:
            self._focus_spec = None

        i_cur = min(self._anim_frame, len(self.data["t"]) - 1)

        if self._focus_spec is not None and len(self.charts) > 1:
            self._redraw_focused(i_cur)
        else:
            self._redraw_grid(i_cur)

        self.canvas.draw()
        if was_running:
            self._start_anim()

    def _redraw_grid(self, i_cur: int):
        """Равномерная сетка 2 колонки."""
        n_ch = len(self.charts)
        cols = min(2, n_ch)
        rows = (n_ch + cols - 1) // cols
        gs = gridspec.GridSpec(
            rows, cols, figure=self.fig,
            hspace=0.50, wspace=0.36,
            left=0.08, right=0.97, top=0.95, bottom=0.07,
        )
        for i, spec in enumerate(self.charts):
            r, c = divmod(i, cols)
            self._draw_chart(spec, self.fig.add_subplot(gs[r, c]), i_cur)

    def _redraw_focused(self, i_cur: int):
        """Большой график слева + остальные в столбик справа."""
        other = [c for c in self.charts if c is not self._focus_spec]
        n_other = max(1, len(other))
        gs = gridspec.GridSpec(
            n_other, 2, figure=self.fig,
            width_ratios=[1.45, 1],
            hspace=0.55, wspace=0.38,
            left=0.07, right=0.97, top=0.95, bottom=0.07,
        )
        # Главный — занимает всю левую колонку
        self._draw_chart(self._focus_spec, self.fig.add_subplot(gs[:, 0]), i_cur)
        # Остальные — правая колонка, по одному в ряд
        for i, spec in enumerate(other):
            self._draw_chart(spec, self.fig.add_subplot(gs[i, 1]), i_cur)

    def _draw_chart(self, spec: ChartSpec, ax, i_cur: int):
        """Нарисовать один график на заданной оси."""
        spec.ax = ax
        ax.set_picker(True)

        xdata = self.data.get(spec.x_ch)
        ydata = self.data.get(spec.y_ch)

        if xdata is None or ydata is None:
            ax.set_title(f"Нет канала: {spec.x_ch} / {spec.y_ch}", fontsize=9)
            spec._dyn_line = spec._dyn_dot = None
            return

        yd     = np.degrees(ydata) if spec.deg else ydata
        y_unit = "°" if spec.deg else CHANNELS.get(spec.y_ch, ("", ""))[1]
        x_name, x_unit = CHANNELS.get(spec.x_ch, (spec.x_ch, ""))
        y_name, _      = CHANNELS.get(spec.y_ch, (spec.y_ch, ""))

        spec._xdata = xdata
        spec._ydata = yd
        lw = getattr(spec, "lw", 1.5)

        ax.plot(xdata, yd, color=spec.color, lw=lw, alpha=0.15)   # блёклый фон
        dyn_line, = ax.plot(xdata[:i_cur+1], yd[:i_cur+1], color=spec.color, lw=lw + 0.3)
        dyn_dot,  = ax.plot([xdata[i_cur]], [yd[i_cur]], "o", color=spec.color,
                            ms=5, zorder=5, markeredgecolor="white", markeredgewidth=0.8)
        spec._dyn_line = dyn_line
        spec._dyn_dot  = dyn_dot

        # Пометить главный график звёздочкой в заголовке
        title = f"★ {spec.label}" if spec is self._focus_spec else spec.label
        ax.set_title(title, fontsize=9, pad=3)
        ax.set_xlabel(f"{x_name}, {x_unit}", fontsize=8)
        ax.set_ylabel(f"{y_name}, {y_unit}", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(True, ls="--", alpha=0.5)

        pad_x = max((xdata.max() - xdata.min()) * 0.04, 0.5)
        pad_y = max((yd.max() - yd.min()) * 0.10, 0.5)
        ax.set_xlim(xdata.min() - pad_x, xdata.max() + pad_x)
        ax.set_ylim(yd.min() - pad_y, yd.max() + pad_y)

        ymin = getattr(spec, "ymin", None)
        ymax = getattr(spec, "ymax", None)
        if ymin is not None or ymax is not None:
            cur = ax.get_ylim()
            ax.set_ylim(
                ymin if ymin is not None else cur[0],
                ymax if ymax is not None else cur[1],
            )


    # ------------------------------------------------------------------
    # Анимация — FuncAnimation с blit=True (перерисовываются только артисты)
    # ------------------------------------------------------------------

    def _toggle_anim(self):
        if self._anim_obj is None:
            self._start_anim()
        elif self._anim_running:
            # Пауза: останавливаем таймер (fn перестаёт расти)
            self._anim_obj.event_source.stop()
            self._anim_running = False
            self.btn_play.config(text="▶  Продолжить")
        else:
            # Продолжить: пересоздаём FuncAnimation от текущей позиции.
            # fn снова начинается с 0 → нет прыжка; canvas.draw() восстанавливает blit-фон.
            self._stop_anim()
            self._start_anim()

    def _start_anim(self):
        if self.data is None or not self.charts:
            return

        t = self.data["t"]
        n = len(t)
        dt = t[1] - t[0]
        fps = 50
        stride = max(1, int(self._anim_speed / fps / dt))

        blit_artists = []
        for spec in self.charts:
            if spec._dyn_line is not None:
                blit_artists.extend([spec._dyn_line, spec._dyn_dot])
        if not blit_artists:
            return

        start_frame = self._anim_frame
        total = max(1, (n - start_frame + stride - 1) // stride)

        def _update(fn):
            i = min(start_frame + fn * stride, n - 1)
            self._anim_frame = i
            self._slider_from_anim = True
            self.time_var.set(i)
            self._slider_from_anim = False
            self.time_lbl.config(text=f"{t[i]:5.1f} с")

            for spec in self.charts:
                if spec._dyn_line is None or spec._xdata is None:
                    continue
                self._update_spec_to(spec, i)

            if fn >= total - 1:
                self.root.after(50, self._on_anim_done)

            return blit_artists

        self._anim_obj = FuncAnimation(
            self.fig, _update,
            frames=total,
            interval=1000 // fps,
            blit=True,
            repeat=False,
        )
        self._anim_running = True
        self.btn_play.config(text="⏸  Пауза")
        self.canvas.draw()  # устанавливает blit-фон для новой анимации

    def _on_anim_done(self):
        self._anim_obj     = None
        self._anim_running = False
        self._anim_frame   = 0
        self.btn_play.config(text="▶  Пуск")

    def _stop_anim(self):
        """Полная остановка — при _redraw / _reset / смене скорости."""
        if self._anim_obj is not None:
            self._anim_obj.event_source.stop()
            self._anim_obj = None
        self._anim_running = False
        self.btn_play.config(text="▶  Пуск")

    def _reset_anim(self):
        self._stop_anim()
        self._anim_frame = 0
        self.time_var.set(0)
        self.time_lbl.config(text="  0.0 с")
        self._manual_draw()

    def _on_slider(self, val):
        if self._slider_from_anim:
            return  # вызван из анимации — игнорируем
        self._anim_frame = int(float(val))
        t = self.data["t"] if self.data else None
        if t is not None:
            i = min(self._anim_frame, len(t) - 1)
            self.time_lbl.config(text=f"{t[i]:5.1f} с")
        self._manual_draw()

    def _update_spec_to(self, spec: ChartSpec, i: int):
        """Обновить все динамические артисты спека до кадра i."""
        xd, yd = spec._xdata, spec._ydata
        spec._dyn_line.set_data(xd[:i + 1], yd[:i + 1])
        spec._dyn_dot.set_data([xd[i]], [yd[i]])

    def _manual_draw(self):
        """Перерисовать без анимации (при ручном перетаскивании ползунка)."""
        if self.data is None:
            return
        i = min(self._anim_frame, len(self.data["t"]) - 1)
        for spec in self.charts:
            if spec._dyn_line is None or spec._xdata is None:
                continue
            self._update_spec_to(spec, i)
        self.canvas.draw_idle()

    def _on_speed_change(self, _=None):
        try:
            self._anim_speed = float(self.speed_var.get().replace("x", ""))
        except ValueError:
            pass
        # Перезапустить с новой скоростью если воспроизводится
        if self._anim_running or self._anim_obj is not None:
            saved = self._anim_frame
            self._stop_anim()
            self._anim_frame = saved
            self._start_anim()

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------

    def _on_right_click(self, event):
        # Определяем, на каком графике кликнули
        if self.data is not None and self.charts:
            x_fig = event.x / self.canvas.get_tk_widget().winfo_width()
            y_fig = 1 - event.y / self.canvas.get_tk_widget().winfo_height()
            self._picked_spec = None
            for spec in self.charts:
                if spec.ax is not None:
                    bbox = spec.ax.get_position()
                    if (bbox.x0 <= x_fig <= bbox.x1 and bbox.y0 <= y_fig <= bbox.y1):
                        self._picked_spec = spec
                        break

        has_pick = self._picked_spec is not None
        can_focus = has_pick and self._picked_spec is not self._focus_spec and len(self.charts) > 1
        self._ctx.entryconfig(2, state="normal" if has_pick else "disabled")
        self._ctx.entryconfig(4, state="normal" if can_focus else "disabled")
        self._ctx.entryconfig(5, state="normal" if self._focus_spec is not None else "disabled")

        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    def _on_pick(self, event):
        for spec in self.charts:
            if spec.ax is event.artist.axes:
                self._picked_spec = spec
                break


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = FlightViewerApp(root)
    root.mainloop()
