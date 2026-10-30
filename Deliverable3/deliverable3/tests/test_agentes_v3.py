# -*- coding: utf-8 -*-
"""
test_agentes_v3.py - Agentes con decisión (A1-A4), bucle A4->A3, ablaciones E4* y baseline E0. Sin GPU.
El motor simulado responde según el rol (primer renglón del prompt de sistema).
"""

import json
import unittest

from deliverable3.agentes import BRAZOS
from deliverable3.agentes_v3 import (
    AgenteExtractorV3,
    AgenteTemporalReAct,
    AgenteTemporalSinTools,
    AgenteTriageV3,
    AgenteVerificadorAgente,
)
from deliverable3.grafo import ejecutar
from deliverable3.trazas import TrazaEjecucion

REF = "2026-09-01"
A2_BASE = {"titulo": "x", "hora_inicio": None, "duracion_minutos": None,
           "participantes": [], "ubicacion": None, "recordatorio_minutos": None}


class MotorGuion:
    """Cada rol tiene una lista de respuestas (se consumen en orden; la última se repite)."""

    def __init__(self, **guion):
        self.guion = {k: list(v) for k, v in guion.items()}
        self.llamadas = {}
        self.ultimo_user = {}

    def generar(self, mensajes, **kw):
        sistema = mensajes[0]["content"]
        rol = ("A1" if sistema.startswith("Eres A1") else "A3" if sistema.startswith("Eres A3")
               else "A4" if sistema.startswith("Eres A4") else "A2")
        self.llamadas[rol] = self.llamadas.get(rol, 0) + 1
        self.ultimo_user[rol] = [m for m in mensajes if m["role"] == "user"][-1]["content"]
        cola = self.guion.get(rol, ["{}"])
        r = cola.pop(0) if len(cola) > 1 else cola[0]
        return r if isinstance(r, str) else json.dumps(r)


def a3_llamar(*tools):
    return {"pensamiento": "p", "accion": "llamar", "tools": list(tools)}


A3_TERMINAR = {"pensamiento": "listo", "accion": "terminar"}
A1_OK = {"accion": "continuar", "razon": "evento", "idioma": "es"}
A4_APROBAR = {"razonamiento": "ok", "accion": "aprobar", "correcciones": {}, "motivo": "consistente"}


class TestA1(unittest.TestCase):
    def test_continuar_y_rechazar(self):
        t = TrazaEjecucion()
        self.assertTrue(AgenteTriageV3(MotorGuion(A1=[A1_OK])).evaluar("Reunión mañana a las 10", t, REF)["continuar"])
        r = AgenteTriageV3(MotorGuion(A1=[{"accion": "rechazar", "razon": "saludo"}])).evaluar("hola", t, REF)
        self.assertFalse(r["continuar"])

    def test_ve_la_senal_de_la_herramienta(self):
        m = MotorGuion(A1=[A1_OK])
        AgenteTriageV3(m).evaluar("Vuelo el 23 de septiembre a las 5 de la mañana", TrazaEjecucion(), REF)
        self.assertIn("Señal de detectar_expresion_temporal", m.ultimo_user["A1"])
        self.assertIn('"tiene_senal": true', m.ultimo_user["A1"])

    def test_respuesta_no_usable_no_borra_el_evento(self):
        r = AgenteTriageV3(MotorGuion(A1=["basura"])).evaluar("Reunión mañana", TrazaEjecucion(), REF)
        self.assertTrue(r["continuar"])


class TestA2(unittest.TestCase):
    def test_reintenta_una_vez_si_no_es_json(self):
        m = MotorGuion(A2=["no es json", dict(A2_BASE, titulo="Reunión")])
        t = TrazaEjecucion()
        d = AgenteExtractorV3(m).extraer("Reunión mañana", t)
        self.assertEqual(d["titulo"], "Reunión")
        self.assertEqual(m.llamadas["A2"], 2)
        self.assertTrue([x for x in t.turnos if x["tipo"] == "agente"][-1]["reintento"])

    def test_dos_fallos_dan_borrador_vacio(self):
        d = AgenteExtractorV3(MotorGuion(A2=["x"])).extraer("Reunión mañana", TrazaEjecucion())
        self.assertEqual(d["titulo"], "Reunión mañana")


class TestA3(unittest.TestCase):
    FRASE = "Reunión de pauta el viernes 18 a las 10 con la candidata a diseñadora"
    BORR = dict(A2_BASE, titulo="Reunión de pauta", hora_inicio="10:00", participantes=["candidata"])

    def test_elige_herramientas_observa_y_termina(self):
        m = MotorGuion(A3=[a3_llamar("resolver_fecha", "normalizar_hora", "expandir_participantes"), A3_TERMINAR])
        t = TrazaEjecucion()
        ev = AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, t)
        self.assertEqual(ev["fecha"], "2026-09-18")
        self.assertEqual(ev["hora_inicio"], "10:00")
        self.assertEqual(ev["participantes"], ["candidata a diseñadora"])
        self.assertEqual(m.llamadas["A3"], 2)
        self.assertIn("resolver_fecha -> \"2026-09-18\"", m.ultimo_user["A3"])   # el 2º paso ve la observación
        msgs = [x for x in t.turnos if x["tipo"] == "mensaje"]
        self.assertIn(("A3", "tool:resolver_fecha"), [(x["de"], x["a"]) for x in msgs])
        self.assertIn(("tool:resolver_fecha", "A3"), [(x["de"], x["a"]) for x in msgs])

    def test_no_llama_lo_que_no_pidio(self):
        m = MotorGuion(A3=[a3_llamar("resolver_fecha"), A3_TERMINAR])
        ev = AgenteTemporalReAct(m).resolver(self.FRASE, dict(self.BORR, duracion_minutos=45), REF, TrazaEjecucion())
        self.assertEqual(ev["duracion_minutos"], 45)          # sin calcular_duracion se conserva lo de A2
        self.assertEqual(ev["hora_inicio"], "10:00")          # sin normalizar_hora se conserva el borrador

    def test_terminar_sin_observar_deja_la_fecha_en_null(self):
        ev = AgenteTemporalReAct(MotorGuion(A3=[A3_TERMINAR])).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())
        self.assertIsNone(ev["fecha"])

    def test_json_invalido_dos_veces_activa_el_respaldo(self):
        t = TrazaEjecucion()
        ev = AgenteTemporalReAct(MotorGuion(A3=["???"])).resolver(self.FRASE, self.BORR, REF, t)
        self.assertEqual(ev["fecha"], "2026-09-18")
        ultimo = [x for x in t.turnos if x["tipo"] == "agente"][-1]
        self.assertTrue(ultimo["respaldo"])

    def test_guardia_terminar_sin_observar_pide_reconsiderar_una_vez(self):
        m = MotorGuion(A3=[A3_TERMINAR, a3_llamar("resolver_fecha"), A3_TERMINAR])
        t = TrazaEjecucion()
        ev = AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, t)
        self.assertEqual(ev["fecha"], "2026-09-18")
        self.assertEqual(m.llamadas["A3"], 3)             # terminar vacío -> reconsidera -> llamar -> terminar
        ultimo = [x for x in t.turnos if x["tipo"] == "agente"][-1]
        self.assertTrue(ultimo["guardia_terminar_vacio"])

    def test_la_guardia_actua_una_sola_vez(self):
        m = MotorGuion(A3=[A3_TERMINAR])
        ev = AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())
        self.assertIsNone(ev["fecha"])
        self.assertEqual(m.llamadas["A3"], 2)

    def test_tolera_variantes_de_formato_en_los_nombres_de_herramientas(self):
        for tools in (["resolver_fecha()", "Normalizar_Hora"], "resolver_fecha", ["`resolver_fecha`"]):
            m = MotorGuion(A3=[{"accion": "llamar", "tools": tools}, A3_TERMINAR])
            ev = AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())
            self.assertEqual(ev["fecha"], "2026-09-18", tools)
        m = MotorGuion(A3=[{"accion": "llamar", "tool": "resolver_fecha"}, A3_TERMINAR])
        self.assertEqual(AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())["fecha"], "2026-09-18")

    def test_herramienta_inventada_no_cuenta(self):
        m = MotorGuion(A3=[{"accion": "llamar", "tools": ["calcular_hora_magica"]}])
        t = TrazaEjecucion()
        ev = AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, t)
        self.assertEqual(ev["fecha"], "2026-09-18")   # dos respuestas no usables -> respaldo declarado
        self.assertTrue([x for x in t.turnos if x["tipo"] == "agente"][-1]["respaldo"])

    def test_tope_de_pasos(self):
        m = MotorGuion(A3=[a3_llamar("resolver_fecha")])
        AgenteTemporalReAct(m, max_pasos=3).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())
        self.assertEqual(m.llamadas["A3"], 3)

    def test_objecion_de_a4_llega_al_prompt(self):
        m = MotorGuion(A3=[a3_llamar("calcular_duracion"), A3_TERMINAR])
        AgenteTemporalReAct(m).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion(), objecion="la duración es el aviso previo")
        self.assertIn("Objeción de A4: la duración es el aviso previo", m.ultimo_user["A3"])

    def test_sin_herramientas_el_modelo_calcula_todo(self):
        m = MotorGuion(A3=[{"fecha": "2026-09-04", "hora_inicio": "10:00", "zona_horaria": "America/Santiago"}])
        ev = AgenteTemporalSinTools(m).resolver(self.FRASE, self.BORR, REF, TrazaEjecucion())
        self.assertEqual(ev["fecha"], "2026-09-04")   # el error de "viernes 18" que las herramientas evitan
        self.assertEqual(m.llamadas["A3"], 1)


class TestA4(unittest.TestCase):
    EV = {"titulo": "Ensayo de la orquesta", "fecha": "2026-09-26", "hora_inicio": "18:00", "duracion_minutos": None,
          "participantes": ["orquesta"], "ubicacion": None, "recordatorio_minutos": None,
          "zona_horaria": "America/Santiago", "recurrence": None}
    FRASE = "Ensayo de la orquesta el 26 de septiembre a las 18:00"

    def test_corrige_quitando_un_dudoso(self):
        m = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"participantes": []}, "motivo": "complemento del título"}])
        ev, accion, _ = AgenteVerificadorAgente(m).revisar(self.FRASE, dict(self.EV), REF, TrazaEjecucion())
        self.assertEqual((accion, ev["participantes"]), ("corregir", []))

    def test_no_puede_inventar_ni_quitar_no_dudosos(self):
        t = TrazaEjecucion()
        ev0 = dict(self.EV, participantes=["Camila"])
        m = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"participantes": []}, "motivo": "x"}])
        ev, _, _ = AgenteVerificadorAgente(m).revisar("Cena con Camila el 26 de septiembre a las 18:00", ev0, REF, t)
        self.assertEqual(ev["participantes"], ["Camila"])
        self.assertEqual([x for x in t.turnos if x["tipo"] == "agente"][-1]["correcciones_rechazadas"], ["participantes"])
        m2 = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"participantes": ["orquesta", "fantasma"]}, "motivo": "x"}])
        ev2, _, _ = AgenteVerificadorAgente(m2).revisar(self.FRASE, dict(self.EV), REF, TrazaEjecucion())
        self.assertEqual(ev2["participantes"], ["orquesta"])

    def test_fecha_inexistente_solo_se_puede_anular(self):
        ev0 = dict(self.EV, fecha="2026-10-31", participantes=[])
        m = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"fecha": None}, "motivo": "no existe"}])
        ev, _, _ = AgenteVerificadorAgente(m).revisar("Reunión el 31/09 a las 18:00", ev0, REF, TrazaEjecucion())
        self.assertIsNone(ev["fecha"])
        m2 = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"fecha": "2026-11-01"}, "motivo": "x"}])
        ev2, _, _ = AgenteVerificadorAgente(m2).revisar("Reunión el 31/09 a las 18:00", ev0, REF, TrazaEjecucion())
        self.assertEqual(ev2["fecha"], "2026-10-31")   # valor distinto de null y de la sugerencia: se rechaza

    def test_ampm_acepta_la_sugerencia_del_reporte(self):
        ev0 = dict(self.EV, hora_inicio="09:00", participantes=[])
        m = MotorGuion(A4=[{"accion": "corregir", "correcciones": {"hora_inicio": "21:00"}, "motivo": "pm"}])
        ev, _, _ = AgenteVerificadorAgente(m).revisar("Cena el 26 de septiembre a las 9 pm", ev0, REF, TrazaEjecucion())
        self.assertEqual(ev["hora_inicio"], "21:00")

    def test_devolver_en_la_vuelta_2_se_convierte_en_aprobar(self):
        m = MotorGuion(A4=[{"accion": "devolver_a_A3", "motivo": "revisa"}])
        _, accion, _ = AgenteVerificadorAgente(m).revisar(self.FRASE, dict(self.EV), REF, TrazaEjecucion(), vuelta=2)
        self.assertEqual(accion, "aprobar")

    def test_respuesta_no_usable_reintenta_y_aprueba(self):
        m = MotorGuion(A4=["???"])
        _, accion, _ = AgenteVerificadorAgente(m).revisar(self.FRASE, dict(self.EV), REF, TrazaEjecucion())
        self.assertEqual((accion, m.llamadas["A4"]), ("aprobar", 2))

    def test_siempre_hay_llamada_al_modelo(self):
        m = MotorGuion(A4=[A4_APROBAR])
        AgenteVerificadorAgente(m).revisar(self.FRASE, dict(self.EV, participantes=[]), REF, TrazaEjecucion())
        self.assertEqual(m.llamadas["A4"], 1)


class TestGrafoE4(unittest.TestCase):
    FRASE = "puedes agendar la reunión de sincronización el 10 a las 14? avísame 15 min antes"
    A2 = dict(A2_BASE, titulo="reunión de sincronización", hora_inicio="14:00", recordatorio_minutos=15)

    def motor(self, **extra):
        guion = dict(A1=[A1_OK], A2=[self.A2], A3=[a3_llamar("resolver_fecha", "normalizar_hora", "calcular_duracion", "extraer_recordatorio"), A3_TERMINAR] * 2,
                     A4=[A4_APROBAR])
        guion.update(extra)
        return MotorGuion(**guion)

    def test_flujo_completo_y_mensajes_entre_agentes(self):
        m = self.motor()
        ev, t = ejecutar(self.FRASE, cfg=BRAZOS["E4"], motor=m, fecha_ref=REF)
        self.assertEqual(ev["fecha"], "2026-09-10")
        self.assertIsNone(ev["duracion_minutos"])           # calcular_duracion_v2 no toma el aviso previo
        self.assertEqual(ev["recordatorio_minutos"], 15)
        pares = [(x["de"], x["a"]) for x in t.turnos if x["tipo"] == "mensaje"]
        for par in [("Entrada", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "A4"), ("A4", "SALIDA")]:
            self.assertIn(par, pares)
        self.assertEqual(t.turnos[-1]["estado"], "APROBADO")

    def test_a4_corrige_la_duracion_que_a2_tomo_del_aviso(self):
        a2 = dict(self.A2, duracion_minutos=15)
        m = self.motor(A2=[a2], A4=[{"accion": "corregir", "correcciones": {"duracion_minutos": None}, "motivo": "es el aviso previo"}])
        ev, t = ejecutar(self.FRASE, cfg=BRAZOS["E4"], motor=m, fecha_ref=REF)
        self.assertIsNone(ev["duracion_minutos"])
        self.assertEqual(t.turnos[-1]["estado"], "CORREGIDO")
        m2 = self.motor(A2=[a2])   # A4 aprueba pese a la violación: la decisión es suya y queda en la traza
        ev2, _ = ejecutar(self.FRASE, cfg=BRAZOS["E4"], motor=m2, fecha_ref=REF)
        self.assertEqual(ev2["duracion_minutos"], 15)

    def test_bucle_a4_devuelve_a_a3_una_vez(self):
        m = self.motor(A4=[{"accion": "devolver_a_A3", "motivo": "revisa la duración"}, A4_APROBAR])
        ev, t = ejecutar(self.FRASE, cfg=BRAZOS["E4"], motor=m, fecha_ref=REF)
        self.assertEqual(m.llamadas["A3"], 4)               # 2 pasos + 2 pasos tras la objeción
        self.assertEqual(m.llamadas["A4"], 2)
        self.assertIn(("A4", "A3"), [(x["de"], x["a"]) for x in t.turnos if x["tipo"] == "mensaje"])
        self.assertIn("Objeción de A4: revisa la duración", m.ultimo_user["A3"])

    def test_a4_que_insiste_en_devolver_no_genera_bucle_infinito(self):
        m = self.motor(A4=[{"accion": "devolver_a_A3", "motivo": "otra vez"}])
        ejecutar(self.FRASE, cfg=BRAZOS["E4"], motor=m, fecha_ref=REF)
        self.assertEqual(m.llamadas["A4"], 2)

    def test_a1_rechaza_y_el_flujo_se_detiene(self):
        m = self.motor(A1=[{"accion": "rechazar", "razon": "saludo"}])
        ev, t = ejecutar("hola qué tal", cfg=BRAZOS["E4"], motor=m, fecha_ref=REF)
        self.assertIsNone(ev["fecha"])
        self.assertEqual(t.turnos[-1]["estado"], "RECHAZADO")
        self.assertNotIn("A2", m.llamadas)

    def test_ablacion_t5_sin_a1(self):
        m = self.motor()
        ejecutar(self.FRASE, cfg=BRAZOS["E4T5"], motor=m, fecha_ref=REF)
        self.assertNotIn("A1", m.llamadas)

    def test_ablacion_t4_sin_a4(self):
        m = self.motor()
        _, t = ejecutar(self.FRASE, cfg=BRAZOS["E4T4"], motor=m, fecha_ref=REF)
        self.assertNotIn("A4", m.llamadas)
        self.assertEqual(t.turnos[-1]["estado"], "SIN_A4")

    def test_ablacion_t1_sin_herramientas(self):
        m = self.motor(A3=[{"fecha": "2026-09-10", "hora_inicio": "14:00"}])
        ev, _ = ejecutar(self.FRASE, cfg=BRAZOS["E4T1"], motor=m, fecha_ref=REF)
        self.assertEqual(m.llamadas["A3"], 1)
        self.assertEqual(ev["fecha"], "2026-09-10")

    def test_ablaciones_t2_y_t3_cambian_solo_el_prompt_de_a4(self):
        self.assertEqual(BRAZOS["E4T2"]["a4_prompt"], "a4_sin_fewshot_v1.txt")
        self.assertEqual(BRAZOS["E4T3"]["a4_prompt"], "a4_sin_cot_v1.txt")
        for k in ("a1", "a3", "a4"):
            self.assertEqual(BRAZOS["E4T2"][k], BRAZOS["E4"][k])
            self.assertEqual(BRAZOS["E4T3"][k], BRAZOS["E4"][k])

    def test_prompts_de_a4_difieren_en_ejemplos_y_razonamiento(self):
        from deliverable3.agentes import _cargar_prompt
        completo, sin_fs, sin_cot = (_cargar_prompt(n) for n in ("a4_agente_v1.txt", "a4_sin_fewshot_v1.txt", "a4_sin_cot_v1.txt"))
        self.assertIn("EJEMPLOS CONTRASTIVOS", completo)
        self.assertNotIn("EJEMPLOS CONTRASTIVOS", sin_fs)
        self.assertIn("razonamiento", sin_fs)
        self.assertIn("EJEMPLOS CONTRASTIVOS", sin_cot)
        self.assertNotIn("razonamiento", sin_cot)

    def test_e0_prompt_directo_una_llamada_sin_agentes(self):
        class Directo:
            llamadas = 0

            def generar(self, mensajes, **kw):
                Directo.llamadas += 1
                return json.dumps({"titulo": "Reunión", "fecha": "2026-09-10", "hora_inicio": "14:00", "duracion_minutos": None,
                                   "participantes": [], "ubicacion": None, "recordatorio_minutos": None,
                                   "zona_horaria": "America/Santiago", "recurrence": None})
        ev, t = ejecutar("Reunión el 10/09 a las 14:00", cfg=BRAZOS["E0"], motor=Directo(), fecha_ref=REF)
        self.assertEqual((ev["fecha"], Directo.llamadas), ("2026-09-10", 1))
        self.assertEqual(t.turnos[-1]["estado"], "DIRECTO")

    def test_e0_sin_json_da_evento_vacio(self):
        class Prosa:
            def generar(self, mensajes, **kw):
                return "Claro, con gusto agendo esa reunión."
        ev, _ = ejecutar("Reunión el 10/09 a las 14:00", cfg=BRAZOS["E0"], motor=Prosa(), fecha_ref=REF)
        self.assertIsNone(ev["fecha"])


class TestRegresion(unittest.TestCase):
    def test_e1_e2_e3_siguen_intactos(self):
        from deliverable3.agentes import BRAZOS as B
        self.assertEqual(B["E2"]["gramatica"], "v2")
        self.assertEqual(B["E3"]["a3_version"], "v2")
        self.assertNotIn("version", B["E2"])


if __name__ == "__main__":
    unittest.main()
