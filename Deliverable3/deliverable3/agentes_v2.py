# -*- coding: utf-8 -*-
"""
agentes_v2.py - Agentes A3 y A4 de la etapa 2 (intento2). agentes.py queda intacto.

A3' Temporal v2    : tools_v2 + conciliación con A2 (la tool solo pisa a A2 con un valor no nulo y
                     que no sea un recordatorio). Deja en la traza qué componente produjo cada campo.
A4' Verificador v2 : validadores generales (fecha/hora/duración/am-pm/participantes). Lo determinista
                     se corrige sin modelo; los participantes dudosos se reparan con UNA llamada al
                     LLM (más un reintento si la respuesta no se puede usar), acotada a esos campos.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List, Tuple

from deliverable3.agentes import AgenteBase, _extraer_json
from deliverable3.tools import extraer_recurrencia, extraer_zona_horaria, normalizar_hora
from deliverable3.tools_v2 import (
    calcular_duracion_v2,
    expandir_participante,
    extraer_recordatorio,
    fecha_explicita_invalida,
    hora_ampm_explicita,
    participante_dudoso,
    resolver_fecha_v2,
    _norm,
)
from deliverable3.trazas import TrazaEjecucion

_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class AgenteTemporalV2(AgenteBase):
    """A3': resuelve fecha/hora/duración/recordatorio con tools_v2 y concilia con lo extraído por A2."""

    def __init__(self, motor: Any, prompt_file: str = "a3_temporal_v1.txt"):
        super().__init__("A3_Temporal_v2", prompt_file, motor)

    def resolver(
        self, frase: str, semantico: Dict[str, Any], fecha_ref: str, traza: TrazaEjecucion
    ) -> Dict[str, Any]:
        evento = dict(semantico)
        proc: Dict[str, str] = {}

        fecha = resolver_fecha_v2(frase, fecha_ref)
        traza.registrar_tool("resolver_fecha_v2", {"frase": frase, "fecha_ref": fecha_ref}, fecha)
        evento["fecha"], proc["fecha"] = fecha, "tool"

        hora = normalizar_hora(semantico.get("hora_inicio"), frase)
        traza.registrar_tool("normalizar_hora", {"hora_extraida": semantico.get("hora_inicio"), "frase": frase}, hora)
        evento["hora_inicio"], proc["hora_inicio"] = hora, "tool"

        dur = calcular_duracion_v2(frase)
        traza.registrar_tool("calcular_duracion_v2", {"frase": frase}, dur)
        if dur is not None:
            evento["duracion_minutos"], proc["duracion_minutos"] = dur, "tool"
        else:
            proc["duracion_minutos"] = "A2"

        rec = extraer_recordatorio(frase)
        traza.registrar_tool("extraer_recordatorio", {"frase": frase}, rec)
        if rec is not None:
            evento["recordatorio_minutos"], proc["recordatorio_minutos"] = rec, "tool"
        else:
            proc["recordatorio_minutos"] = "A2"

        tz = extraer_zona_horaria(frase)
        traza.registrar_tool("extraer_zona_horaria", {"frase": frase}, tz)
        evento["zona_horaria"], proc["zona_horaria"] = tz, "tool"

        rrule = extraer_recurrencia(frase)
        evento["recurrence"], proc["recurrence"] = rrule, "tool"

        participantes = []
        for p in semantico.get("participantes") or []:
            p2 = expandir_participante(frase, str(p))
            if p2 != p:
                traza.registrar_tool("expandir_participante", {"frase": frase, "nombre": p}, p2)
                proc["participantes"] = "tool"
            participantes.append(p2)
        evento["participantes"] = participantes
        proc.setdefault("participantes", "A2")

        traza.registrar_agente(
            self.nombre, f"Fecha: {fecha}, Hora: {hora}, Dur: {dur}, Rec: {rec}, TZ: {tz}", procedencia=proc
        )
        return evento


class AgenteVerificadorV2(AgenteBase):
    """A4': validadores generales + reparación acotada con LLM de los participantes dudosos."""

    def __init__(self, motor: Any, prompt_file: str = "a4_reparador_v2.txt", con_llm: bool = True):
        super().__init__("A4_Verificador_v2", prompt_file, motor)
        self.con_llm = con_llm

    # -- reparación con modelo -------------------------------------------------
    def _reparar_participantes(
        self, frase: str, participantes: List[str], dudosos: List[str]
    ) -> Tuple[List[str], int, bool]:
        """Devuelve (participantes_finales, llamadas, respuesta_usable)."""
        pedido = (
            f'Frase: "{frase}"\n'
            f"Participantes propuestos: {json.dumps(participantes, ensure_ascii=False)}\n"
            f"Dudosos: {json.dumps(dudosos, ensure_ascii=False)}"
        )
        validos = {_norm(p): p for p in participantes}
        llamadas = 0
        for _ in range(2):  # intento + 1 reintento
            llamadas += 1
            data = _extraer_json(self.invocar_modelo(pedido))
            lista = data.get("participantes")
            if not isinstance(lista, list):
                continue
            elegidos = {_norm(str(x)) for x in lista}
            if not elegidos.issubset(validos):  # el modelo no puede inventar participantes
                continue
            finales = [p for p in participantes if _norm(p) in elegidos or p not in dudosos]
            return finales, llamadas, True
        return participantes, llamadas, False

    # -- auditoría -------------------------------------------------------------
    def auditar(
        self, frase: str, evento: Dict[str, Any], traza: TrazaEjecucion, fecha_ref: str = "2026-09-01"
    ) -> Tuple[Dict[str, Any], str]:
        ev = dict(evento)
        correcciones: List[str] = []
        llamadas = 0

        # V1: fecha y hora bien formadas y coherentes con la frase
        f = ev.get("fecha")
        if f:
            try:
                date.fromisoformat(str(f))
            except ValueError:
                ev["fecha"] = None
                correcciones.append(f"V1 fecha inválida {f!r} -> null")
        if ev.get("fecha") and fecha_explicita_invalida(frase, fecha_ref):
            correcciones.append(f"V1 la frase trae una fecha inexistente; {ev['fecha']} -> null")
            ev["fecha"] = None
        h = ev.get("hora_inicio")
        if h is not None and not _RE_HORA.match(str(h)):
            ev["hora_inicio"] = None
            correcciones.append(f"V1 hora fuera de rango {h!r} -> null")

        # V2: una cantidad que la frase presenta como recordatorio no puede ser la duración
        dur, rec = ev.get("duracion_minutos"), ev.get("recordatorio_minutos")
        if dur is not None and dur in (rec, extraer_recordatorio(frase)) and calcular_duracion_v2(frase) != dur:
            ev["duracion_minutos"] = None
            correcciones.append(f"V2 duración {dur} era el recordatorio -> null")

        # V3: marca am/pm explícita manda sobre la hora extraída
        esperada = hora_ampm_explicita(frase)
        if esperada and ev.get("hora_inicio") != esperada:
            correcciones.append(f"V3 hora {ev.get('hora_inicio')!r} -> {esperada} (marca am/pm)")
            ev["hora_inicio"] = esperada

        # V4: participantes que pueden ser complemento del título -> LLM, acotado a esos campos
        participantes = [str(p) for p in (ev.get("participantes") or [])]
        dudosos = [p for p in participantes if participante_dudoso(frase, p)]
        if dudosos and self.con_llm:
            finales, llamadas, usable = self._reparar_participantes(frase, participantes, dudosos)
            if finales != participantes:
                quitados = [p for p in participantes if p not in finales]
                correcciones.append(f"V4 participantes descartados por el verificador: {quitados}")
            elif not usable:
                correcciones.append(f"V4 sin respuesta usable del modelo; se conservan {dudosos}")
            ev["participantes"] = finales

        if correcciones:
            estado, justif = "CORREGIDO", " | ".join(correcciones)
        elif ev.get("fecha") and ev.get("hora_inicio"):
            estado, justif = "APROBADO", "Contrato de 9 campos verificado y consistente."
        else:
            estado, justif = "INCOMPLETO", "Falta fecha u hora de inicio obligatoria."
        if correcciones and not (ev.get("fecha") and ev.get("hora_inicio")):
            estado = "INCOMPLETO"

        traza.registrar_agente(
            self.nombre, f"[{estado}] {justif}", correcciones=correcciones, llamadas_llm=llamadas, dudosos=dudosos
        )
        return ev, estado
