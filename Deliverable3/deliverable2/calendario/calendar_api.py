# -*- coding: utf-8 -*-
"""
calendar_api.py -- API de calendario local con el mismo contrato que un
events.insert de Google Calendar.

Desviacion declarada en el documento: en lugar de Google Calendar OAuth,
el evento se persiste en JSON y se exporta como .ics. El contrato de
entrada (9 campos) es identico, de modo que cambiar a la API real es
sustituir esta clase por su cliente HTTP.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

from pipeline.normalizacion import CAMPOS_CONTRATO, objetivo_nulo

RUTA_POR_DEFECTO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resultados", "calendario.json",
)


class ErrorDeContrato(ValueError):
    pass


class LocalCalendarAPI:
    def __init__(self, ruta: str = RUTA_POR_DEFECTO):
        self.ruta = ruta
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        if not os.path.exists(ruta):
            self._guardar([])

    # -- persistencia -----------------------------------------------------

    def _leer(self) -> list:
        with open(self.ruta, encoding="utf-8") as f:
            return json.load(f)

    def _guardar(self, eventos: list) -> None:
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=1)

    # -- validacion del contrato ------------------------------------------

    @staticmethod
    def validar(evento: dict) -> dict:
        faltantes = [c for c in CAMPOS_CONTRATO if c not in evento]
        if faltantes:
            raise ErrorDeContrato("faltan campos del contrato: %s" % faltantes)

        e = dict(evento)
        if e.get("fecha") is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e["fecha"])):
            raise ErrorDeContrato("fecha invalida: %r" % e["fecha"])
        if e.get("hora_inicio") is not None and not re.fullmatch(r"\d{2}:\d{2}", str(e["hora_inicio"])):
            raise ErrorDeContrato("hora_inicio invalida: %r" % e["hora_inicio"])
        if e.get("participantes") is not None and not isinstance(e["participantes"], list):
            raise ErrorDeContrato("participantes debe ser lista")
        return e

    # -- operaciones ------------------------------------------------------

    def create_event(self, evento: dict) -> dict:
        """events.insert: recibe el contrato, valida y persiste."""
        e = self.validar(evento)
        eventos = self._leer()
        identificador = "evt-%04d" % (len(eventos) + 1)
        registro = {"id": identificador, "creado": datetime.now().isoformat(timespec="seconds"), "evento": e}
        eventos.append(registro)
        self._guardar(eventos)
        return registro

    def list_events(self) -> list:
        return self._leer()

    def delete_event(self, identificador: str) -> bool:
        eventos = self._leer()
        restantes = [x for x in eventos if x["id"] != identificador]
        if len(restantes) == len(eventos):
            return False
        self._guardar(restantes)
        return True

    # -- exportacion ------------------------------------------------------

    def exportar_ics(self, ruta: str | None = None) -> str:
        """Genera un .ics estandar (RFC 5545) con los eventos almacenados."""
        ruta = ruta or os.path.join(os.path.dirname(self.ruta), "calendario.ics")
        lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SML-GEN-AI//Calendar//ES"]
        for registro in self._leer():
            e = registro["evento"]
            if not e.get("fecha"):
                continue
            inicio = "%sT%s00" % (e["fecha"].replace("-", ""), (e.get("hora_inicio") or "00:00").replace(":", ""))
            dur = e.get("duracion_minutos") or 60
            fin = (datetime.strptime(inicio, "%Y%m%dT%H%M%S") + timedelta(minutes=dur)).strftime("%Y%m%dT%H%M%S")
            lineas += [
                "BEGIN:VEVENT",
                "UID:%s@sml-gen-ai" % registro["id"],
                "DTSTART:%s" % inicio,
                "DTEND:%s" % fin,
                "SUMMARY:%s" % (e.get("titulo") or "(sin titulo)"),
                "LOCATION:%s" % (e.get("ubicacion") or ""),
                "DESCRIPTION:participantes=%s | recordatorio=%s min | tz=%s" % (
                    ", ".join(e.get("participantes") or []),
                    e.get("recordatorio_minutos"),
                    e.get("zona_horaria"),
                ),
                "END:VEVENT",
            ]
        lineas.append("END:VCALENDAR")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\r\n".join(lineas) + "\r\n")
        return ruta
