# -*- coding: utf-8 -*-
"""
agentes_v3.py - Agentes de la etapa 3 (intento3). Cada agente es una llamada al modelo con rol y prompt
propios que DECIDE qué pasa después; agentes.py / agentes_v2.py quedan intactos.

A1 Triage      : continuar | rechazar. Ve la señal de la herramienta detectar_expresion_temporal.
A2 Extractor   : 6 campos semánticos (LoRA). Si la salida no es JSON, se revisa a sí mismo una vez.
A3 Temporal    : bucle observar-actuar: elige qué herramientas llamar, mira los resultados y termina.
A4 Verificador : aprobar | corregir | devolver_a_A3, a partir del reporte de validar_contrato.

Los traspasos se registran con TrazaEjecucion.registrar_mensaje(de, a, contenido).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from deliverable3.agentes import AgenteBase, _extraer_json
from deliverable3.tools import extraer_recurrencia, extraer_zona_horaria, normalizar_hora
from deliverable3.tools_v2 import (
    _norm,
    calcular_duracion_v2,
    detectar_expresion_temporal,
    expandir_participantes,
    extraer_recordatorio,
    resolver_fecha_v2,
    validar_contrato,
)
from deliverable3.trazas import TrazaEjecucion

DIA_REF = {"2026-09-01": "martes"}
ZONA_DEFECTO = "America/Santiago"
MAX_TOKENS_ACCION = 160   # las acciones de agente son JSON cortos


def _dump(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False)


class _AgenteV3(AgenteBase):
    def invocar(self, user_content: str, **kw) -> str:
        mensajes = [{"role": "system", "content": self.prompt}, {"role": "user", "content": user_content}]
        return self.motor.generar(mensajes, **kw) if hasattr(self.motor, "generar") else "{}"


# ---------------------------------------------------------------------------
# A1
# ---------------------------------------------------------------------------

class AgenteTriageV3(_AgenteV3):
    def __init__(self, motor: Any, prompt_file: str = "a1_triage_v2.txt"):
        super().__init__("A1_Triage", prompt_file, motor)

    def evaluar(self, frase: str, traza: TrazaEjecucion, fecha_ref: str) -> Dict[str, Any]:
        traza.registrar_mensaje("Entrada", "A1", frase)
        senal = detectar_expresion_temporal(frase, fecha_ref)
        traza.registrar_mensaje("A1", "tool:detectar_expresion_temporal", {"frase": frase})
        traza.registrar_mensaje("tool:detectar_expresion_temporal", "A1", senal)
        resp = self.invocar(f'Evalúa esta frase: "{frase}"\nSeñal de detectar_expresion_temporal: {_dump(senal)}',
                            max_new_tokens=MAX_TOKENS_ACCION)
        data = _extraer_json(resp)
        accion = data.get("accion")
        if accion not in ("continuar", "rechazar"):   # sin respuesta usable: no se borra el evento
            accion, data = "continuar", dict(data, razon=data.get("razon", "respuesta no usable: se continúa"))
        traza.registrar_agente(self.nombre, f"Decisión: {accion}. {data.get('razon', '')}", accion=accion)
        traza.registrar_mensaje("A1", "A2" if accion == "continuar" else "FIN", {"accion": accion})
        return {"continuar": accion == "continuar", "idioma": data.get("idioma"), "metadata": data}


# ---------------------------------------------------------------------------
# A2
# ---------------------------------------------------------------------------

class AgenteExtractorV3(_AgenteV3):
    def __init__(self, motor: Any, prompt_file: str = "a2_extractor_v1.txt"):
        super().__init__("A2_Extractor", prompt_file, motor)

    def extraer(self, frase: str, traza: TrazaEjecucion) -> Dict[str, Any]:
        user = f'Frase: "{frase}"'
        resp = self.invocar(user)   # mismo prompt y llamada que en el intento2 (el caché los reutiliza)
        data = _extraer_json(resp)
        reintento = False
        if not data:   # revisa su propia salida una vez
            reintento = True
            mensajes = [{"role": "system", "content": self.prompt}, {"role": "user", "content": user},
                        {"role": "assistant", "content": resp},
                        {"role": "user", "content": "Tu respuesta no es un JSON válido. Responde SOLO el objeto JSON de los seis campos."}]
            data = _extraer_json(self.motor.generar(mensajes))
        if not data:
            data = {"titulo": frase, "hora_inicio": None, "duracion_minutos": None, "participantes": [],
                    "ubicacion": None, "recordatorio_minutos": None}
        traza.registrar_agente(self.nombre, _dump(data), reintento=reintento)
        traza.registrar_mensaje("A2", "A3", data)
        return data


# ---------------------------------------------------------------------------
# A3
# ---------------------------------------------------------------------------

TOOLS_A3 = ["resolver_fecha", "normalizar_hora", "calcular_duracion", "extraer_recordatorio",
            "extraer_zona_horaria", "extraer_recurrencia", "expandir_participantes"]


def ejecutar_tool(nombre: str, frase: str, fecha_ref: str, borrador: Dict[str, Any]) -> Any:
    if nombre == "resolver_fecha":
        return resolver_fecha_v2(frase, fecha_ref)
    if nombre == "normalizar_hora":
        return normalizar_hora(borrador.get("hora_inicio"), frase)
    if nombre == "calcular_duracion":
        return calcular_duracion_v2(frase)
    if nombre == "extraer_recordatorio":
        return extraer_recordatorio(frase)
    if nombre == "extraer_zona_horaria":
        return extraer_zona_horaria(frase)
    if nombre == "extraer_recurrencia":
        return extraer_recurrencia(frase)
    if nombre == "expandir_participantes":
        return expandir_participantes(frase, borrador.get("participantes") or [])
    raise KeyError(nombre)


def _normalizar_tools(crudo: Any) -> List[str]:
    """Tolera variantes de formato del modelo: nombre suelto, mayúsculas, tildes, backticks o paréntesis."""
    if isinstance(crudo, str):
        crudo = [crudo]
    if not isinstance(crudo, list):
        return []
    out: List[str] = []
    for t in crudo:
        nombre = _norm(str(t)).strip().strip("`'\" ").split("(")[0].strip()
        if nombre in TOOLS_A3 and nombre not in out:
            out.append(nombre)
    return out


def _ensamblar(borrador: Dict[str, Any], obs: Dict[str, Any]) -> Dict[str, Any]:
    """Conciliación: una herramienta pisa a A2 solo si fue llamada y devolvió un valor no nulo
    (fecha, zona y recurrencia solo salen de herramientas)."""
    ev = dict(borrador)
    ev["fecha"] = obs.get("resolver_fecha")
    if "normalizar_hora" in obs:
        ev["hora_inicio"] = obs["normalizar_hora"]
    for tool, campo in (("calcular_duracion", "duracion_minutos"), ("extraer_recordatorio", "recordatorio_minutos")):
        if obs.get(tool) is not None:
            ev[campo] = obs[tool]
    ev["zona_horaria"] = obs.get("extraer_zona_horaria") or ZONA_DEFECTO
    ev["recurrence"] = obs.get("extraer_recurrencia")
    if "expandir_participantes" in obs:
        ev["participantes"] = obs["expandir_participantes"]
    return ev


class AgenteTemporalReAct(_AgenteV3):
    """A3 con herramientas (T1): elige herramientas, observa y termina. Máximo `max_pasos` pasos."""

    def __init__(self, motor: Any, prompt_file: str = "a3_agente_v1.txt", max_pasos: int = 3):
        super().__init__("A3_Temporal", prompt_file, motor)
        self.max_pasos = max_pasos

    def _mensaje(self, frase, borrador, fecha_ref, obs, objecion, nota=None):
        partes = [f'Frase: "{frase}"', f"Borrador de A2: {_dump(borrador)}",
                  f"Fecha de referencia: {fecha_ref} ({DIA_REF.get(fecha_ref, 'martes')})"]
        if objecion:
            partes.append(f"Objeción de A4: {objecion}")
        if nota:
            partes.append(f"Nota del sistema: {nota}")
        partes.append("Observaciones hasta ahora:" + ("" if obs else " (ninguna)"))
        partes += [f"- {t} -> {_dump(v)}" for t, v in obs.items()]
        partes.append("Siguiente acción (JSON):")
        return "\n".join(partes)

    def resolver(self, frase: str, borrador: Dict[str, Any], fecha_ref: str, traza: TrazaEjecucion,
                 objecion: Optional[str] = None) -> Dict[str, Any]:
        obs: Dict[str, Any] = {}
        respaldo = False
        motivo_fin = "terminar"
        invalidas = 0
        nota = None
        guardia = False
        for paso in range(1, self.max_pasos + 1):
            data = _extraer_json(self.invocar(self._mensaje(frase, borrador, fecha_ref, obs, objecion, nota),
                                              max_new_tokens=MAX_TOKENS_ACCION))
            accion = data.get("accion")
            tools = _normalizar_tools(data.get("tools", data.get("tool")))
            if accion == "terminar" or (accion is None and not tools and data.get("terminar")):
                if not obs and paso == 1 and not guardia:
                    # guardia declarada: terminar sin haber observado nada no es una decisión útil; se pide una vez más
                    guardia = True
                    nota = ("Todavía no llamaste ninguna herramienta. Llama las que la frase necesita "
                            "(por ejemplo resolver_fecha si hay una fecha) antes de terminar.")
                    traza.registrar_agente(self.nombre, f"paso {paso}: terminar sin observar; se pide reconsiderar",
                                           accion="terminar_vacio")
                    continue
                traza.registrar_agente(self.nombre, f"paso {paso}: terminar. {data.get('pensamiento', '')}", accion="terminar")
                break
            if accion not in ("llamar", None) and not tools:
                tools = []
            if not tools:
                invalidas += 1
                traza.registrar_agente(self.nombre, f"paso {paso}: respuesta no usable", accion="invalida")
                if invalidas >= 2:   # respaldo declarado: llama todas las herramientas
                    respaldo, motivo_fin = True, "respaldo"
                    tools = list(TOOLS_A3)
                else:
                    continue
            else:
                traza.registrar_agente(self.nombre, f"paso {paso}: llamar {tools}. {data.get('pensamiento', '')}", accion="llamar")
            for t in tools:
                traza.registrar_mensaje("A3", f"tool:{t}", {"frase": frase})
                obs[t] = ejecutar_tool(t, frase, fecha_ref, borrador)
                traza.registrar_mensaje(f"tool:{t}", "A3", obs[t])
            if respaldo:
                break
        else:
            motivo_fin = "tope_de_pasos"
        evento = _ensamblar(borrador, obs)
        traza.registrar_agente(self.nombre, f"fin ({motivo_fin}): herramientas {list(obs)}", respaldo=respaldo,
                               herramientas=list(obs), guardia_terminar_vacio=guardia)
        traza.registrar_mensaje("A3", "A4", evento)
        return evento


class AgenteTemporalSinTools(_AgenteV3):
    """Ablación T1: el modelo calcula todo él mismo, sin herramientas."""

    def __init__(self, motor: Any, prompt_file: str = "a3_sin_tools_v1.txt"):
        super().__init__("A3_Temporal", prompt_file, motor)

    def resolver(self, frase: str, borrador: Dict[str, Any], fecha_ref: str, traza: TrazaEjecucion,
                 objecion: Optional[str] = None) -> Dict[str, Any]:
        user = (f'Frase: "{frase}"\nBorrador de A2: {_dump(borrador)}\n'
                f"Fecha de referencia: {fecha_ref} ({DIA_REF.get(fecha_ref, 'martes')})")
        if objecion:
            user += f"\nObjeción de A4: {objecion}"
        data = _extraer_json(self.invocar(user, max_new_tokens=220))
        ev = dict(borrador)
        ev["fecha"] = data.get("fecha")
        for campo in ("hora_inicio", "duracion_minutos", "recordatorio_minutos", "participantes"):
            if campo in data:
                ev[campo] = data[campo]
        ev["zona_horaria"] = data.get("zona_horaria") or ZONA_DEFECTO
        ev["recurrence"] = data.get("recurrence")
        traza.registrar_agente(self.nombre, f"sin herramientas: {_dump({k: ev.get(k) for k in ('fecha', 'hora_inicio')})}", herramientas=[])
        traza.registrar_mensaje("A3", "A4", ev)
        return ev


# ---------------------------------------------------------------------------
# A4
# ---------------------------------------------------------------------------

class AgenteVerificadorAgente(_AgenteV3):
    def __init__(self, motor: Any, prompt_file: str = "a4_agente_v1.txt"):
        super().__init__("A4_Verificador", prompt_file, motor)

    @staticmethod
    def _aplicar(evento: Dict[str, Any], correcciones: Any, violaciones: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
        """Aplica solo correcciones acotadas; devuelve (evento, rechazadas)."""
        ev, rechazadas = dict(evento), []
        if not isinstance(correcciones, dict):
            return ev, ["correcciones no es un objeto"]
        dudosos = {_norm(d) for v in violaciones if v["codigo"] == "V4" for d in v.get("dudosos", [])}
        con_violacion = {v["campo"]: v for v in violaciones}
        for campo, valor in correcciones.items():
            if campo == "participantes":
                actuales = [str(p) for p in (ev.get("participantes") or [])]
                if (isinstance(valor, list) and {_norm(str(x)) for x in valor} <= {_norm(p) for p in actuales}
                        and {_norm(p) for p in actuales} - {_norm(str(x)) for x in valor} <= dudosos):
                    ev["participantes"] = [p for p in actuales if _norm(p) in {_norm(str(x)) for x in valor}]
                else:
                    rechazadas.append(campo)
            elif campo in ("fecha", "hora_inicio", "duracion_minutos", "recordatorio_minutos") and campo in con_violacion:
                if valor is None or valor == con_violacion[campo].get("sugerencia"):
                    ev[campo] = valor
                else:
                    rechazadas.append(campo)
            else:
                rechazadas.append(campo)
        return ev, rechazadas

    def revisar(self, frase: str, evento: Dict[str, Any], fecha_ref: str, traza: TrazaEjecucion,
                vuelta: int = 1) -> Tuple[Dict[str, Any], str, str]:
        """Devuelve (evento, accion, motivo). accion: aprobar | corregir | devolver_a_A3."""
        violaciones = validar_contrato(frase, evento, fecha_ref)
        traza.registrar_mensaje("A4", "tool:validar_contrato", {"frase": frase})
        traza.registrar_mensaje("tool:validar_contrato", "A4", violaciones)
        user = (f'Frase: "{frase}"\nEvento propuesto: {_dump({k: evento.get(k) for k in evento})}\n'
                f"Reporte de validar_contrato: {_dump(violaciones) if violaciones else 'sin violaciones'}\n"
                f"Vuelta: {vuelta} de 2")
        data: Dict[str, Any] = {}
        for _ in range(2):   # intento + 1 reintento si la respuesta no se puede usar
            data = _extraer_json(self.invocar(user, max_new_tokens=260))
            if data.get("accion") in ("aprobar", "corregir", "devolver_a_A3"):
                break
            data = {}
        accion = data.get("accion") or "aprobar"
        motivo = str(data.get("motivo") or ("respuesta no usable: se aprueba" if not data else ""))
        if accion == "devolver_a_A3" and vuelta >= 2:
            accion, motivo = "aprobar", "no se puede devolver en la vuelta 2: " + motivo
        rechazadas: List[str] = []
        if accion == "corregir":
            evento, rechazadas = self._aplicar(evento, data.get("correcciones"), violaciones)
        traza.registrar_agente(self.nombre, f"[{accion}] {motivo}", accion=accion, vuelta=vuelta,
                               violaciones=[v["codigo"] for v in violaciones], correcciones_rechazadas=rechazadas,
                               razonamiento=data.get("razonamiento"))
        destino = "A3" if accion == "devolver_a_A3" else "SALIDA"
        traza.registrar_mensaje("A4", destino, {"accion": accion, "motivo": motivo})
        return evento, accion, motivo
