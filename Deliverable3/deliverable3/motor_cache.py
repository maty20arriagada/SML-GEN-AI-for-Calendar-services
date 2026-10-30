# -*- coding: utf-8 -*-
"""
motor_cache.py - Memoiza las llamadas al modelo por (mensajes, parámetros).

A1 y A2 reciben exactamente el mismo prompt en todos los brazos, así que con el caché el modelo los
calcula una sola vez por frase y los demás brazos reutilizan esa salida: la corrida es mucho más corta
y las diferencias entre brazos vienen solo de A3/A4 (comparación pareada, sin ruido de muestreo).
Cuidado al leer `segundos`: en los brazos que reutilizan el caché no incluye el tiempo de A1/A2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class MotorConCache:
    def __init__(self, motor: Any, ruta: Optional[str | Path] = None):
        self.motor = motor
        self.ruta = Path(ruta) if ruta else None
        self.cache: Dict[str, str] = {}
        self.llamadas = 0   # llamadas reales al modelo
        self.aciertos = 0   # respuestas servidas desde el caché
        if self.ruta and self.ruta.exists():
            self.cache = json.loads(self.ruta.read_text(encoding="utf-8"))

    @staticmethod
    def _clave(mensajes, kwargs) -> str:
        return json.dumps([mensajes, kwargs], ensure_ascii=False, sort_keys=True)

    def generar(self, mensajes, **kwargs) -> str:
        clave = self._clave(mensajes, kwargs)
        if clave in self.cache:
            self.aciertos += 1
            return self.cache[clave]
        self.llamadas += 1
        salida = self.motor.generar(mensajes, **kwargs)
        self.cache[clave] = salida
        return salida

    def guardar(self) -> None:
        """Persiste el caché (si se dio `ruta`) para retomar tras una caída de la sesión."""
        if self.ruta:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")

    def __getattr__(self, nombre):
        if nombre == "motor":
            raise AttributeError(nombre)
        return getattr(self.motor, nombre)
