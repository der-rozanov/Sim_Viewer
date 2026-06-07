# -*- coding: utf-8 -*-
import os
import json
import numpy as np


def _make_mock_data():
    np.random.seed(42)
    t  = np.linspace(0, 40, 4000)
    dt = t[1] - t[0]
    h        = 100 + 12 * np.sin(0.18 * t) + 0.4 * t
    x        = 30 * t
    Va       = 30 + 2.5 * np.sin(0.38 * t) + 0.4 * np.random.randn(len(t))
    alpha    = np.radians(3 + 2.5 * np.sin(0.32 * t) + 0.3 * np.random.randn(len(t)))
    theta    = np.radians(5 + 3.2 * np.sin(0.18 * t))
    q        = np.gradient(theta, t)
    delta_e  = np.radians(-2 + 1.8 * np.sin(0.32 * t))
    throttle = np.clip(0.44 + 0.08 * np.sin(0.14 * t), 0, 1)
    E_thrust = np.cumsum(throttle * Va) * dt
    return {
        "t": t, "h": h, "x": x, "Va": Va,
        "alpha_true": alpha, "theta": theta, "q": q,
        "delta_e": delta_e, "throttle": throttle, "E_thrust": E_thrust,
        "meta": {
            "scenario":    "Демо: управление высотой",
            "description": "Тестовые данные — замените реальным .flightlog",
            "saved_at":    "2026-06-07T12:00:00",
        },
    }


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
