# -*- coding: utf-8 -*-

import os
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation

from data    import load_log, CHANNELS, PRESETS
from charts  import ChartSpec, redraw_grid, redraw_focused
from dialogs import _AddChartDialog, _ChartSettingsDialog


class FlightViewerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FlightLog Viewer")
        self.root.geometry("1340x820")
        self.root.minsize(900, 600)

        self.data: dict | None        = None
        self.charts: list[ChartSpec]  = []

        self._anim_obj:        FuncAnimation | None = None
        self._anim_running:    bool  = False
        self._anim_frame:      int   = 0
        self._anim_speed:      float = 2.0
        self._slider_from_anim: bool = False
        self._focus_spec:  ChartSpec | None = None
        self._picked_spec: ChartSpec | None = None
        self._gif_active:      bool  = False

        self._build_ui()
        self._draw_empty()

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
        fm.add_command(label="Открыть...", command=self._open_file, accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label="Выход", command=self.root.quit)
        mb.add_cascade(label="Файл", menu=fm)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_command(label="Добавить график...", command=self._add_custom_dialog)
        vm.add_separator()
        vm.add_command(label="Очистить все", command=self._clear_charts)
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
        self.fig    = Figure(facecolor="#f5f5f5")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        w = self.canvas.get_tk_widget()
        w.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._ctx = tk.Menu(self.root, tearoff=0)
        self._ctx.add_command(label="Добавить график...",   command=self._add_custom_dialog)
        self._ctx.add_command(label="Настройки графика...", command=self._open_settings_for_picked)
        self._ctx.add_command(label="✕ Удалить график",    command=self._delete_picked)   # idx 2
        self._ctx.add_separator()
        self._ctx.add_command(label="★ Сделать главным",   command=self._focus_picked)    # idx 4
        self._ctx.add_command(label="☆ Убрать из фокуса", command=self._unfocus)          # idx 5
        self._ctx.add_separator()
        self._ctx.add_command(label="Очистить все",         command=self._clear_charts)

        w.bind("<Button-3>", self._on_right_click)
        self.canvas.mpl_connect("pick_event", self._on_pick)

    def _build_anim_controls(self):
        ctrl = ttk.Frame(self.root, padding=(8, 4))
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_play = ttk.Button(ctrl, text="▶  Пуск", width=10, command=self._toggle_anim)
        self.btn_play.pack(side=tk.LEFT)
        ttk.Button(ctrl, text="↺", width=3, command=self._reset_anim).pack(side=tk.LEFT, padx=2)

        self.time_var = tk.DoubleVar(value=0)
        self.slider   = ttk.Scale(ctrl, orient=tk.HORIZONTAL, variable=self.time_var,
                                  from_=0, to=100, command=self._on_slider)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        self.time_lbl = ttk.Label(ctrl, text="  0.0 с", width=8)
        self.time_lbl.pack(side=tk.LEFT)

        ttk.Separator(ctrl, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(ctrl, text="Скорость:").pack(side=tk.LEFT)

        self.speed_var = tk.StringVar(value="x2.0")
        spd = ttk.Combobox(ctrl, textvariable=self.speed_var,
                           values=["x0.25", "x0.5", "x1.0", "x2.0", "x5.0", "x10.0"],
                           width=6, state="readonly")
        spd.pack(side=tk.LEFT, padx=4)
        spd.bind("<<ComboboxSelected>>", self._on_speed_change)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Нет данных")
        ttk.Label(self.root, textvariable=self.status_var,
                  relief=tk.SUNKEN, anchor=tk.W,
                  padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

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

        self.charts = [
            ChartSpec.from_preset(p) for p in PRESETS
            if data.get(p["x"]) is not None and data.get(p["y"]) is not None
        ]
        # Траектория главная по умолчанию, если присутствует в данных
        self._focus_spec  = next((c for c in self.charts if c.x_ch == "x" and c.y_ch == "h"), None)
        self._picked_spec = None
        self._redraw()

    # ------------------------------------------------------------------
    # Управление графиками
    # ------------------------------------------------------------------

    def _add_preset(self, p: dict):
        if self.data is None:
            return
        if any(c.x_ch == p["x"] and c.y_ch == p["y"] for c in self.charts):
            return
        self.charts.append(ChartSpec.from_preset(p))
        self._redraw()

    def _add_custom_dialog(self):
        if self.data is None:
            messagebox.showinfo("", "Сначала откройте лог-файл (Файл → Открыть...)")
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

    def _open_settings_for_picked(self):
        if self._picked_spec is None:
            messagebox.showinfo("", "Кликните на график сначала (ЛКМ), затем ПКМ → Настройки")
            return
        _ChartSettingsDialog(self.root, self._picked_spec, self._redraw)

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def _draw_empty(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_axis_off()
        ax.text(0.5, 0.54, "Откройте лог-файл для начала работы",
                ha="center", va="center", fontsize=13, color="#999",
                transform=ax.transAxes)
        ax.text(0.5, 0.44, "Файл → Открыть...   (Ctrl+O)",
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

        if self._focus_spec not in self.charts:
            self._focus_spec = None

        i_cur = min(self._anim_frame, len(self.data["t"]) - 1)

        if self._focus_spec is not None and len(self.charts) > 1:
            redraw_focused(self.fig, self.charts, self.data, self._focus_spec, CHANNELS, i_cur)
        else:
            redraw_grid(self.fig, self.charts, self.data, self._focus_spec, CHANNELS, i_cur)

        self.canvas.draw()
        if was_running:
            self._start_anim()

    # ------------------------------------------------------------------
    # Анимация — FuncAnimation с blit=True
    # ------------------------------------------------------------------

    def _toggle_anim(self):
        if self._anim_obj is None:
            self._start_anim()
        elif self._anim_running:
            self._anim_obj.event_source.stop()
            self._anim_running = False
            self.btn_play.config(text="▶  Продолжить")
        else:
            self._stop_anim()
            self._start_anim()

    def _start_anim(self):
        if self.data is None or not self.charts:
            return

        t      = self.data["t"]
        n      = len(t)
        dt     = t[1] - t[0]
        fps    = 50
        stride = max(1, int(self._anim_speed / fps / dt))

        blit_artists = [
            artist
            for spec in self.charts if spec._dyn_line is not None
            for artist in (spec._dyn_line, spec._dyn_dot)
        ]
        if not blit_artists:
            return

        start_frame = self._anim_frame
        total       = max(1, (n - start_frame + stride - 1) // stride)

        def _update(fn):
            i = min(start_frame + fn * stride, n - 1)
            self._anim_frame = i
            self._slider_from_anim = True
            self.time_var.set(i)
            self._slider_from_anim = False
            self.time_lbl.config(text=f"{t[i]:5.1f} с")
            for spec in self.charts:
                if spec._dyn_line is not None and spec._xdata is not None:
                    spec.update_to(i)
            if fn >= total - 1:
                self.root.after(50, self._on_anim_done)
            return blit_artists

        self._anim_obj = FuncAnimation(
            self.fig, _update,
            frames=total, interval=1000 // fps,
            blit=True, repeat=False,
        )
        self._anim_running = True
        self.btn_play.config(text="⏸  Пауза")
        self.canvas.draw()

    def _stop_anim(self):
        if self._anim_obj is not None:
            self._anim_obj.event_source.stop()
            self._anim_obj = None
        self._anim_running = False
        self.btn_play.config(text="▶  Пуск")

    def _on_anim_done(self):
        self._anim_obj     = None
        self._anim_running = False
        self._anim_frame   = 0
        self.btn_play.config(text="▶  Пуск")

    def _reset_anim(self):
        self._stop_anim()
        self._anim_frame = 0
        self.time_var.set(0)
        self.time_lbl.config(text="  0.0 с")
        self._manual_draw()

    def _on_slider(self, val):
        if self._slider_from_anim:
            return
        self._anim_frame = int(float(val))
        if self.data is not None:
            i = min(self._anim_frame, len(self.data["t"]) - 1)
            self.time_lbl.config(text=f"{self.data['t'][i]:5.1f} с")
        self._manual_draw()

    def _manual_draw(self):
        if self.data is None:
            return
        i = min(self._anim_frame, len(self.data["t"]) - 1)
        for spec in self.charts:
            if spec._dyn_line is not None and spec._xdata is not None:
                spec.update_to(i)
        self.canvas.draw_idle()

    def _on_speed_change(self, _=None):
        try:
            self._anim_speed = float(self.speed_var.get().replace("x", ""))
        except ValueError:
            pass
        if self._anim_running or self._anim_obj is not None:
            saved = self._anim_frame
            self._stop_anim()
            self._anim_frame = saved
            self._start_anim()

    # ------------------------------------------------------------------
    # GIF-экспорт
    # ------------------------------------------------------------------

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

        was_running = self._anim_running
        saved_frame = self._anim_frame
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

        self.fig.canvas.draw()
        gif_bg  = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        img_w, img_h = self.fig.canvas.get_width_height()

        def _render_frame(fn: int):
            if not self._gif_active:
                self.status_var.set("Экспорт GIF отменён")
                return
            if fn >= total:
                self.status_var.set(f"Запись файла… ({len(frames_pil)} кадров)")
                self._gif_write_thread(frames_pil, path, fps_gif, was_running, saved_frame)
                return

            i = min(fn * stride, n - 1)
            self.fig.canvas.restore_region(gif_bg)
            for spec in self.charts:
                if spec._dyn_line is None or spec._xdata is None:
                    continue
                spec.update_to(i)
                spec.ax.draw_artist(spec._dyn_line)
                spec.ax.draw_artist(spec._dyn_dot)
            self.fig.canvas.blit(self.fig.bbox)

            buf = self.fig.canvas.buffer_rgba()
            img = Image.frombuffer("RGBA", (img_w, img_h), buf, "raw", "RGBA", 0, 1)
            frames_pil.append(img.convert("RGB"))

            pct = int((fn + 1) / total * 100)
            self.status_var.set(f"Рендер кадров: {fn+1}/{total}  ({pct}%)")
            self.root.after(1, lambda: _render_frame(fn + 1))

        _render_frame(0)

    def _gif_write_thread(self, frames: list, path: str, fps: int,
                          was_running: bool, saved_frame: int):
        def _worker():
            try:
                frames[0].save(
                    path, save_all=True, append_images=frames[1:],
                    duration=1000 // fps, loop=0, optimize=False,
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
            self.status_var.set(f"✓ GIF сохранён: {os.path.basename(path)}")
            messagebox.showinfo("Готово", f"GIF сохранён:\n{path}")
        self._anim_frame = saved_frame
        self._redraw()
        if was_running:
            self._start_anim()

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------

    def _spec_at(self, x_fig: float, y_fig: float) -> "ChartSpec | None":
        """Вернуть ChartSpec под курсором (в нормированных координатах фигуры)."""
        for spec in self.charts:
            if spec.ax is not None:
                bbox = spec.ax.get_position()
                if bbox.x0 <= x_fig <= bbox.x1 and bbox.y0 <= y_fig <= bbox.y1:
                    return spec
        return None

    def _on_right_click(self, event):
        if self.data is not None and self.charts:
            x_fig = event.x / self.canvas.get_tk_widget().winfo_width()
            y_fig = 1 - event.y / self.canvas.get_tk_widget().winfo_height()
            self._picked_spec = self._spec_at(x_fig, y_fig)

        has_pick  = self._picked_spec is not None
        can_focus = has_pick and self._picked_spec is not self._focus_spec and len(self.charts) > 1
        self._ctx.entryconfig(2, state="normal" if has_pick  else "disabled")
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
    app  = FlightViewerApp(root)
    root.mainloop()
