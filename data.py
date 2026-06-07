# -*- coding: utf-8 -*-
import os
import json
import numpy as np


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


CHANNELS = {
    # Основные каналы состояния
    "t":                ("Время",                  "с"),
    "h":                ("Высота",                 "м"),
    "x":                ("Дальность",              "м"),
    "u":                ("Прод. скорость (связ.)", "м/с"),
    "w":                ("Норм. скорость (связ.)", "м/с"),
    "Va":               ("Возд. скорость",         "м/с"),
    "theta":            ("Угол тангажа",           "рад"),
    "q":                ("Угл. скор. тангажа",     "рад/с"),
    "gamma":            ("Угол траектории",        "рад"),
    # Аэродинамика
    "alpha_true":       ("УА истинный",            "рад"),
    "alpha_probe":      ("УА зонд",                "рад"),
    "alpha_est":        ("УА оценка ИНС+GPS",      "рад"),
    # Управление
    "delta_e":          ("Руль высоты",            "рад"),
    "throttle":         ("Тяга",                   "о.е."),
    # Ветер
    "wind_x":           ("Ветер горизонт.",        "м/с"),
    "wind_h":           ("Ветер вертикаль.",       "м/с"),
    # Энергия
    "E_kin":            ("Кинет. энергия",         "Дж"),
    "E_pot":            ("Потенц. энергия",        "Дж"),
    "E_mech":           ("Полная мех. энергия",    "Дж"),
    "P_thrust":         ("Мощность двигателя",     "о.е.·м/с"),
    "E_thrust":         ("Накопл. энергия двиг.",  "о.е.·м"),
    # Уставки
    "h_ref":            ("Уставка высоты",         "м"),
    "theta_ref":        ("Уставка тангажа",        "рад"),
    # Парный прогон
    "paired_h":         ("Высота (пара)",          "м"),
    "paired_Va":        ("Возд. скор. (пара)",     "м/с"),
    "paired_alpha_est": ("УА оценка (пара)",       "рад"),
    "paired_delta_e":   ("Руль высоты (пара)",     "рад"),
    "paired_throttle":  ("Тяга (пара)",            "о.е."),
}

PRESETS = [
    {"label": "Траектория", "x": "x", "y": "h",          "deg": False, "color": "royalblue", "show_arrow": True, "equal_scale": True},
    {"label": "Угол атаки", "x": "t", "y": "alpha_true", "deg": True,  "color": "tomato"},
    {"label": "Тангаж",     "x": "t", "y": "theta",      "deg": True,  "color": "steelblue"},
    {"label": "Скорость",   "x": "t", "y": "Va",         "deg": False, "color": "seagreen"},
]
