# FlightLog Viewer — архитектура приложения

Файл: `viz/app_demo.py`  
Стек: Python 3, tkinter (stdlib), matplotlib (TkAgg backend), numpy, Pillow (опционально для GIF)

---

## Назначение

Standalone GUI-приложение для просмотра полётных логов `.flightlog`.  
Открывает файл, строит произвольный набор графиков по любым каналам лога,  
анимирует их синхронно по оси времени, экспортирует в GIF.

При переносе в отдельный реп достаточно:  
1. Убрать `_make_mock_data()` (или оставить для тестов)  
2. `load_log()` уже скопирована и работает standalone  

---

## Формат данных `.flightlog`

Файл — это `numpy .npz` (бинарный архив массивов) + JSON-метаданные.  
`load_log(path)` возвращает `dict`:

```python
data = {
    "t":          np.ndarray,   # время, с  (ось времени для всех каналов)
    "h":          np.ndarray,   # высота, м
    "x":          np.ndarray,   # горизонтальная дальность, м
    "u":          np.ndarray,   # продольная скорость (связ. СК), м/с
    "w":          np.ndarray,   # нормальная скорость (связ. СК), м/с
    "Va":         np.ndarray,   # воздушная скорость, м/с
    "theta":      np.ndarray,   # угол тангажа, рад
    "q":          np.ndarray,   # угловая скорость тангажа, рад/с
    "gamma":      np.ndarray,   # угол траектории (по воздуху), рад
    "alpha_true": np.ndarray,   # истинный угол атаки, рад
    "alpha_probe":np.ndarray,   # измерение зонда, рад (NaN если нет зонда)
    "alpha_est":  np.ndarray,   # косвенная оценка УА (ИНС+GPS), рад
    "delta_e":    np.ndarray,   # отклонение руля высоты, рад
    "throttle":   np.ndarray,   # тяга [0..1]
    "wind_x":     np.ndarray,   # горизонтальный ветер, м/с
    "wind_h":     np.ndarray,   # вертикальный ветер, м/с
    "E_kin":      np.ndarray,   # кинетическая энергия, Дж
    "E_pot":      np.ndarray,   # потенциальная энергия, Дж
    "E_mech":     np.ndarray,   # полная механическая энергия, Дж
    "P_thrust":   np.ndarray,   # нормированная мощность двигателя, о.е.·м/с
    "E_thrust":   np.ndarray,   # накопленная энергия двигателя, о.е.·м
    "alert":      np.ndarray,   # индикатор УА: 0=НОРМ 1=ПРЕД 2=КРИТ 3=СРЫВ
    "h_ref":      np.ndarray,   # уставка высоты, м (NaN если нет)
    "theta_ref":  np.ndarray,   # уставка тангажа, рад (NaN если нет)
    # Опционально при парном прогоне:
    "paired_h":         np.ndarray,
    "paired_Va":        np.ndarray,
    "paired_alpha_est": np.ndarray,
    "paired_delta_e":   np.ndarray,
    "paired_throttle":  np.ndarray,
    # Метаданные:
    "meta": {
        "scenario":    str,     # название сценария
        "description": str,
        "saved_at":    str,     # ISO timestamp
        "wind":        {"Vw_const": float, ...},
        "trim":        {"alpha_deg": float, "de_deg": float, "throttle": float},
        "events":      [{"t": float, "label": str, "color": str}, ...],
        "has_probe":   bool,
        "has_est":     bool,
        "has_h_ref":   bool,
        "has_paired":  bool,
        "channels":    {"key": "описание, единица", ...},  # справочник
    }
}
```

**Важно**: все каналы имеют одинаковую длину `len(data["t"])`.  
Индекс `i` в любом массиве соответствует моменту времени `data["t"][i]`.

---

## Структура кода

### Модульные объекты (вне классов)

| Имя | Тип | Назначение |
|-----|-----|------------|
| `load_log(path)` | функция | Загрузить `.flightlog` → `dict`. Standalone, не зависит от симулятора. |
| `_make_mock_data()` | функция | Генератор синтетических данных для демонстрации без файла. |
| `CHANNELS` | `dict[str, tuple]` | Справочник `ключ → (название, единица)`. Используется в диалогах выбора каналов и подписях осей. Добавить новый канал — добавить строку сюда. |
| `PRESETS` | `list[dict]` | Преднастроенные графики. Каждый: `x`, `y`, `label`, `color`, `deg` (перевод в градусы), `show_arrow` (зарезервировано). |

### Класс `ChartSpec`

Описание одного графика. Хранит как настройки (постоянные), так и ссылки на matplotlib-артисты (заполняются при `_redraw()`).

```python
spec.x_ch        # str  — ключ канала для оси X
spec.y_ch        # str  — ключ канала для оси Y
spec.label       # str  — заголовок графика
spec.color       # str  — цвет линии
spec.deg         # bool — конвертировать Y из рад в градусы
spec.show_arrow  # bool — зарезервировано (стрелка направления)
spec.lw          # float — толщина линии (опционально, через настройки)
spec.ymin/ymax   # float|None — явные пределы Y (опционально)
spec.ax          # matplotlib Axes, заполняется в _draw_chart()
spec._dyn_line   # Line2D — растущая линия (анимируется)
spec._dyn_dot    # Line2D — точка текущего положения (анимируется)
spec._xdata      # np.ndarray — данные X в единицах отображения
spec._ydata      # np.ndarray — данные Y в единицах отображения
```

### Класс `FlightViewerApp`

Главный класс приложения. Один экземпляр на всё приложение.

**Состояние:**
```python
self.data          # dict | None   — загруженный лог
self.charts        # list[ChartSpec] — текущий набор графиков
self._anim_obj     # FuncAnimation | None
self._anim_running # bool — True = воспроизводится (не на паузе)
self._anim_frame   # int  — текущий индекс в data["t"]
self._anim_speed   # float — множитель скорости (x0.25..x10)
self._focus_spec   # ChartSpec | None — "главный" большой график
self._picked_spec  # ChartSpec | None — последний выбранный ПКМ
self._slider_from_anim  # bool — guard: блокирует рекурсию slider↔anim
self._gif_active   # bool — True пока идёт GIF-экспорт
```

---

## Ключевые методы

### Загрузка данных

| Метод | Что делает |
|-------|-----------|
| `_load_mock()` | Загружает синтетику через `_make_mock_data()`, вызывает `_apply_data()` |
| `_open_file()` | Диалог выбора файла → `load_log(path)` → `_apply_data()` |
| `_apply_data(data, source)` | Центральный метод загрузки: сбрасывает анимацию, обновляет слайдер, ставит заголовок и статусбар из мета, создаёт PRESETS-графики (только если их каналы есть в файле), вызывает `_redraw()` |

### Управление графиками

| Метод | Что делает |
|-------|-----------|
| `_add_preset(p)` | Добавить преднастроенный график (если ещё нет) |
| `_add_custom_dialog()` | Открыть `_AddChartDialog` → `_on_add_custom()` → `ChartSpec` |
| `_delete_picked()` | Удалить `_picked_spec` из `self.charts`, сбросить фокус если нужно |
| `_focus_picked()` | Сделать `_picked_spec` главным (`_focus_spec`) |
| `_unfocus()` | Сбросить `_focus_spec = None` |
| `_clear_charts()` | Очистить `self.charts`, нарисовать пустой экран |

### Отрисовка

| Метод | Что делает |
|-------|-----------|
| `_redraw()` | Перестроить всю фигуру: проверяет `_focus_spec`, выбирает раскладку, вызывает `_redraw_grid()` или `_redraw_focused()` |
| `_redraw_grid(i_cur)` | Равномерная сетка 2 колонки. Вызывает `_draw_chart()` для каждого спека. |
| `_redraw_focused(i_cur)` | `GridSpec(n_other, 2, width_ratios=[1.45, 1])`: фокус-график занимает `gs[:, 0]`, остальные — `gs[i, 1]` |
| `_draw_chart(spec, ax, i_cur)` | Рисует один график на заданной оси: блёклый фон (alpha=0.15), `_dyn_line` (до `i_cur`), `_dyn_dot` (в `i_cur`), заголовок, подписи, пределы осей. Сохраняет артисты в `spec`. |
| `_draw_empty()` | Показать placeholder-текст когда нет данных |

### Анимация

Используется `FuncAnimation` с `blit=True` — перерисовываются только `_dyn_line` и `_dyn_dot`, фон кэшируется.

| Метод | Что делает |
|-------|-----------|
| `_toggle_anim()` | Пуск / Пауза / Продолжить. На паузе: `event_source.stop()`. На продолжить: `_stop_anim()` + `_start_anim()` от `self._anim_frame`. |
| `_start_anim()` | Создаёт новый `FuncAnimation`. `start_frame = self._anim_frame`, `stride = max(1, int(speed/fps/dt))`, `frames = (n - start_frame) // stride`. Вызывает `canvas.draw()` для установки blit-фона. |
| `_stop_anim()` | `event_source.stop()`, `_anim_obj = None`, сброс кнопки |
| `_on_anim_done()` | Callback по завершению: сброс в frame 0, кнопка → "Пуск" |
| `_update_spec_to(spec, i)` | Обновляет `_dyn_line` и `_dyn_dot` до кадра `i`. Используется в анимации, ползунке и GIF-рендере. |
| `_manual_draw()` | Обновить все спеки до `self._anim_frame` + `canvas.draw_idle()`. Вызывается при перетаскивании ползунка. |

**Известное ограничение**: при изменении размера окна во время анимации blit-фон инвалидируется → краткий артефакт. Лечится разворачиванием окна до запуска анимации.

**Логика паузы**: на паузе `event_source.stop()` останавливает таймер (fn не растёт). На продолжить — новый `FuncAnimation` с `start_frame = self._anim_frame`, поэтому прыжка нет.

### GIF-экспорт

Двухэтапный неблокирующий процесс:

1. **Рендер кадров** (`_save_gif()`) — через `root.after(1, ...)` по одному кадру, UI остаётся живым. Каждый кадр: `canvas.restore_region(gif_bg)` + `draw_artist()` только динамических артистов + `canvas.blit()` + `buffer_rgba()` → `PIL.Image`. Статичный фон (`gif_bg`) захватывается один раз через `copy_from_bbox()` — отсюда высокая скорость.

2. **Запись файла** (`_gif_write_thread()`) — `threading.Thread`, вызывает `PIL frames[0].save(..., save_all=True)`. По завершению через `root.after(0, callback)` восстанавливает состояние приложения.

Файлы сохраняются в `gif_exports/` рядом со скриптом, имя: `flight_YYYY-MM-DD_HH-MM-SS.gif`.  
Скорость GIF берётся из текущего `_anim_speed`.

---

## Раскладки графиков

### Режим сетки (по умолчанию)
```
┌───────────┬───────────┐
│  chart 0  │  chart 1  │
├───────────┼───────────┤
│  chart 2  │  chart 3  │
└───────────┴───────────┘
```
`GridSpec(rows, 2)`, `cols = min(2, n)`.

### Режим фокуса (ПКМ → "★ Сделать главным")
```
┌──────────────────┬──────────┐
│                  │ chart 1  │
│   focus chart    ├──────────┤
│   (gs[:, 0])     │ chart 2  │
│                  ├──────────┤
│                  │ chart 3  │
└──────────────────┴──────────┘
```
`GridSpec(n_other, 2, width_ratios=[1.45, 1])`.  
Главный (`_focus_spec`) занимает всю левую колонку `gs[:, 0]`, остальные — `gs[i, 1]`.

---

## Контекстное меню ПКМ

Индексы пунктов (используются в `_on_right_click` для `entryconfig`):

| Индекс | Пункт | Активен когда |
|--------|-------|---------------|
| 0 | Добавить график... | всегда |
| 1 | Настройки графика... | всегда |
| 2 | ✕ Удалить график | `_picked_spec` не None |
| 3 | separator | — |
| 4 | ★ Сделать главным | `_picked_spec` не None, не является текущим фокусом, графиков > 1 |
| 5 | ☆ Убрать из фокуса | `_focus_spec` не None |
| 6 | separator | — |
| 7 | Очистить все | всегда |

`_picked_spec` определяется по позиции курсора относительно bbox каждого `spec.ax` в момент нажатия ПКМ.

---

## Диалоги

### `_AddChartDialog`
Выбор X-канала, Y-канала (из `CHANNELS`), цвета, флага "в градусы".  
Callback: `_on_add_custom(x_ch, y_ch, color, deg)` → `ChartSpec(...)` → `_redraw()`.

### `_ChartSettingsDialog`
Редактирование существующего `ChartSpec`: заголовок, цвет, Y min/max, толщина линии, флаг градусов.  
Callback: `_redraw()`.  
`ymin`/`ymax`/`lw` — динамические атрибуты, добавляются к спеку при применении.

---

## Как добавить новый канал

1. Добавить строку в `CHANNELS`:
   ```python
   "my_channel": ("Моё название", "ед."),
   ```
2. Канал сразу появится в диалоге "Добавить график".  
   Если канал есть в загруженном `.flightlog` — он будет доступен для выбора.

## Как добавить преднастроенный график

Добавить элемент в `PRESETS`:
```python
{"label": "Моё название", "x": "t", "y": "my_channel", "deg": False, "color": "teal"},
```
Кнопка появится в тулбаре автоматически. График добавится при загрузке файла только если оба канала присутствуют в данных.

## Как подключить реальный файл вместо мок-данных

`load_log()` уже реализована и работает. При старте вместо `_load_mock()`:
```python
self._apply_data(load_log("path/to/file.flightlog"), source="имя файла")
```
Либо просто открыть через Файл → Открыть в самом приложении.
