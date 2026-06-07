# -*- coding: utf-8 -*-
import numpy as np
import matplotlib.gridspec as gridspec


class ChartSpec:
    def __init__(self, x_ch, y_ch, label=None, color="steelblue",
                 deg=False, show_arrow=False, equal_scale=False):
        self.x_ch        = x_ch
        self.y_ch        = y_ch
        self.label       = label or f"{y_ch} / {x_ch}"
        self.color       = color
        self.deg         = deg
        self.show_arrow  = show_arrow   # зарезервировано
        self.equal_scale = equal_scale  # True → одинаковый масштаб осей X и Y (для траектории)
        self.ax          = None
        self._dyn_line  = None
        self._dyn_dot   = None
        self._xdata     = None
        self._ydata     = None

    @classmethod
    def from_preset(cls, p: dict) -> "ChartSpec":
        return cls(p["x"], p["y"], p["label"], p["color"],
                   p.get("deg", False), p.get("show_arrow", False),
                   p.get("equal_scale", False))

    def update_to(self, i: int):
        """Сдвинуть динамическую линию и точку до кадра i."""
        xd, yd = self._xdata, self._ydata
        self._dyn_line.set_data(xd[:i + 1], yd[:i + 1])
        self._dyn_dot.set_data([xd[i]], [yd[i]])


# ---------------------------------------------------------------------------
# Функции отрисовки (не зависят от FlightViewerApp)
# ---------------------------------------------------------------------------

def draw_chart(spec: ChartSpec, ax, data: dict, focus_spec,
               channels: dict, i_cur: int):
    """Нарисовать один график на заданной оси matplotlib."""
    spec.ax = ax
    ax.set_picker(True)

    xdata = data.get(spec.x_ch)
    ydata = data.get(spec.y_ch)
    if xdata is None or ydata is None:
        ax.set_title(f"Нет канала: {spec.x_ch} / {spec.y_ch}", fontsize=9)
        spec._dyn_line = spec._dyn_dot = None
        return

    yd     = np.degrees(ydata) if spec.deg else ydata
    y_unit = "°" if spec.deg else channels.get(spec.y_ch, ("", ""))[1]
    x_name, x_unit = channels.get(spec.x_ch, (spec.x_ch, ""))
    y_name, _      = channels.get(spec.y_ch, (spec.y_ch, ""))

    spec._xdata = xdata
    spec._ydata = yd
    lw = getattr(spec, "lw", 1.5)

    ax.plot(xdata, yd, color=spec.color, lw=lw, alpha=0.15)
    dyn_line, = ax.plot(xdata[:i_cur + 1], yd[:i_cur + 1], color=spec.color, lw=lw + 0.3)
    dyn_dot,  = ax.plot([xdata[i_cur]], [yd[i_cur]], "o", color=spec.color,
                        ms=5, zorder=5, markeredgecolor="white", markeredgewidth=0.8)
    spec._dyn_line = dyn_line
    spec._dyn_dot  = dyn_dot

    title = spec.label
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

    if spec.equal_scale:
        # 1 м по X = 1 м по Y; datalim растягивает ту ось, которая короче,
        # не меняя размер прямоугольника графика в сетке
        ax.set_aspect("equal", adjustable="datalim")


def redraw_grid(fig, charts: list, data: dict, focus_spec,
                channels: dict, i_cur: int):
    """Равномерная сетка 2 колонки."""
    n_ch = len(charts)
    cols = min(2, n_ch)
    rows = (n_ch + cols - 1) // cols
    gs = gridspec.GridSpec(rows, cols, figure=fig,
                           hspace=0.50, wspace=0.36,
                           left=0.08, right=0.97, top=0.95, bottom=0.07)
    for i, spec in enumerate(charts):
        r, c = divmod(i, cols)
        draw_chart(spec, fig.add_subplot(gs[r, c]), data, focus_spec, channels, i_cur)


def redraw_focused(fig, charts: list, data: dict, focus_spec,
                   channels: dict, i_cur: int):
    """Большой график слева + остальные в столбик справа."""
    other   = [c for c in charts if c is not focus_spec]
    n_other = max(1, len(other))
    gs = gridspec.GridSpec(n_other, 2, figure=fig,
                           width_ratios=[1.45, 1],
                           hspace=0.55, wspace=0.38,
                           left=0.07, right=0.97, top=0.95, bottom=0.07)
    draw_chart(focus_spec, fig.add_subplot(gs[:, 0]), data, focus_spec, channels, i_cur)
    for i, spec in enumerate(other):
        draw_chart(spec, fig.add_subplot(gs[i, 1]), data, focus_spec, channels, i_cur)
