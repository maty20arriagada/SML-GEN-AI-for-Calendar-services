# Guion del video (máx. 3:00, solo se ven los primeros 3 minutos)

Grabación de pantalla del notebook en Colab, **sin edición que oculte la ejecución**. Requisito de la consigna: se ve el sistema
corriendo sobre inputs reales, con los **mensajes intermedios entre agentes** visibles junto a la salida final. Las salidas deben poder
rastrearse al repositorio (las trazas JSONL de estos inputs quedan en `resultados/traces/video/`).

| Tiempo | Qué se ve | Qué decir |
|---|---|---|
| 0:00–0:20 | Celda 3 (tests en verde) y celda 7 (modelo cargado en la T4) | La tarea (mensaje → evento de 9 campos), el modelo único (Qwen3-4B + LoRA) y que corre en una Colab T4 |
| 0:20–1:30 | Celda **DEMO**, input 1 (conjunto A: "…avísame 15 min antes") | Recorrer la secuencia: A1 decide continuar → A2 extrae → A3 elige herramientas y observa → A4 valida y decide. Mostrar la línea de E1 (solución D2) arriba y el resultado de E4 abajo: la diferencia es la duración |
| 1:30–2:15 | DEMO, inputs 2 y 3 (conjuntos B y C), sin elegir los más favorables | Señalar un bucle o una corrección de A4 si ocurre; mostrar que A3 no llama herramientas que la frase no necesita |
| 2:15–2:45 | El **caso de falla** (traza guardada, ver `documento/`) | Mostrar el input, qué mensaje intermedio falla y por qué falla (no "falta más datos") |
| 2:45–3:00 | Celda 10 (tabla E0/E1/E4 y ablaciones) | Cerrar con la tabla: n = 160, mismo criterio, y qué técnica aporta más |

Antes de grabar: correr la celda DEMO una vez para comprobar que no falla, y dejar el cuaderno con la fuente grande (Ctrl + `+`).
El link del video debe quedar abierto ("cualquiera con el enlace") y pegarse en `documento/deliverable3.tex` (`\videourl`) y en el README.

**Opcional, si sobra tiempo (no sustituye la demo de arriba):** `subir_a_colab/demo_calendarbot_d3.ipynb` corre el mismo E4 como chat y crea
el evento en Google Calendar tras confirmar. Sirve para mostrar el cierre extremo a extremo (frase → agentes → evento real) con una frase de B
("Café con el postulante a becario el viernes a las 11:00") y una rechazada ("Hola, ¿qué tal?"). Probarlo antes de grabar: pide `credentials.json`.
