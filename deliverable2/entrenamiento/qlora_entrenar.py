# -*- coding: utf-8 -*-
"""
qlora_entrenar.py -- Motor de fine-tuning QLoRA del extractor semantico.

Un unico motor para dos entornos:
  * Colab T4  -> entrenamiento real (4-bit NF4 + LoRA, fp16)
  * local     -> smoke tests en CPU (LoRA sin cuantizar, pocos pasos)

Decisiones de calidad:
  * Formato prompt-completacion + completion_only_loss=True: la loss se
    calcula SOLO sobre el JSON objetivo, no sobre el prompt.
  * max_length se mide sobre los datos (el prompt de reglas ya ocupa ~520
    tokens); si un ejemplo no cabe, el motor aborta en vez de truncar el objetivo.
  * Seleccion de checkpoint por eval_loss y reporte de exact-match sobre
    hard_dev (patrones dificles) y dev (general), generando por lotes.
  * --reanudar continua desde el ultimo checkpoint tras una desconexion.

Uso:
  # Colab T4 (entrenamiento real)
  python entrenamiento/qlora_entrenar.py --modelo Qwen/Qwen3-4B-Instruct-2507 --epocas 3

  # experimento de tamano (rubro model economy)
  python entrenamiento/qlora_entrenar.py --modelo Qwen/Qwen2.5-0.5B-Instruct --epocas 6

  # smoke test local sin GPU (valida el codigo, NO es evidencia)
  python entrenamiento/qlora_entrenar.py --smoke --max-steps 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

RUTA_DATOS_DEFAULT = os.path.join(RAIZ, "datos")


# ---------------------------------------------------------------------------
# datos
# ---------------------------------------------------------------------------

def cargar_jsonl(ruta: str) -> list:
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def cargar_todo(ruta_datos: str):
    train = cargar_jsonl(os.path.join(ruta_datos, "train.jsonl"))
    dev = cargar_jsonl(os.path.join(ruta_datos, "dev.jsonl"))
    hard = cargar_jsonl(os.path.join(ruta_datos, "hard_dev.jsonl"))
    with open(os.path.join(ruta_datos, "prompts.json"), encoding="utf-8") as f:
        prompts = json.load(f)
    return train, dev, hard, prompts


def a_ejemplo(fila: dict, system: str) -> dict:
    """Par prompt (system+user) / completion (JSON objetivo) en formato de chat."""
    return {
        "prompt": [
            {"role": "system", "content": system},
            {"role": "user", "content": 'Frase: "%s"' % fila["texto"]},
        ],
        "completion": [
            {"role": "assistant",
             "content": json.dumps(fila["target"], ensure_ascii=False)},
        ],
    }


# ---------------------------------------------------------------------------
# evaluacion por exact-match (la metrica que decide)
# ---------------------------------------------------------------------------

def extraer_json(crudo: str) -> dict:
    for match in re.finditer(r"\{", crudo):
        try:
            obj, _ = json.JSONDecoder().raw_decode(crudo[match.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return {}


def plantilla(tokenizer, mensajes, generacion: bool) -> str:
    try:
        return tokenizer.apply_chat_template(
            mensajes, tokenize=False, add_generation_prompt=generacion, enable_thinking=False)
    except TypeError:
        return tokenizer.apply_chat_template(
            mensajes, tokenize=False, add_generation_prompt=generacion)


def tokenizar(ejemplos, tokenizer):
    """
    Pretokeniza con la mascara de loss construida aqui: input_ids del chat
    completo y completion_mask=1 SOLO sobre la respuesta del asistente.

    No se delega en trl: trl 0.21 mide el prompt con apply_chat_template sin
    return_dict=False, y en transformers v5 eso devuelve un dict (len=2), asi
    que enmascara 2 tokens y entrena sobre todo el prompt de sistema. Con
    input_ids ya presentes, trl no retokeniza.
    """
    filas, n_prompt, n_total = [], [], []
    for ej in ejemplos:
        texto_prompt = plantilla(tokenizer, ej["prompt"], generacion=True)
        texto_total = plantilla(tokenizer, ej["prompt"] + ej["completion"], generacion=False)
        ids_prompt = tokenizer(texto_prompt, add_special_tokens=False).input_ids
        ids_total = tokenizer(texto_total, add_special_tokens=False).input_ids
        if ids_total[:len(ids_prompt)] != ids_prompt:
            raise SystemExit("la plantilla de chat no deja el prompt como prefijo de "
                             "prompt+completion: la mascara de loss seria incorrecta")
        filas.append({"input_ids": ids_total,
                      "completion_mask": [0] * len(ids_prompt) + [1] * (len(ids_total) - len(ids_prompt))})
        n_prompt.append(len(ids_prompt))
        n_total.append(len(ids_total))
    n_resp = [t - p for p, t in zip(n_prompt, n_total)]
    largos = {"prompt_max": max(n_prompt), "respuesta_min": min(n_resp), "respuesta_max": max(n_resp),
              "total_min": min(n_total), "total_max": max(n_total),
              "total_medio": round(sum(n_total) / len(n_total), 1)}
    return filas, largos


def generar_lote(model, tokenizer, textos, system: str) -> list:
    """Generacion greedy por lotes (padding a la izquierda + KV cache)."""
    import torch
    prompts = [plantilla(tokenizer, [{"role": "system", "content": system},
                                     {"role": "user", "content": 'Frase: "%s"' % t}],
                         generacion=True)
               for t in textos]
    inputs = tokenizer(prompts, return_tensors="pt", padding=True,
                       add_special_tokens=False).to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=128, do_sample=False, use_cache=True,
                             pad_token_id=tokenizer.pad_token_id)
    largo = inputs.input_ids.shape[-1]
    return [extraer_json(tokenizer.decode(o[largo:], skip_special_tokens=True)) for o in out]


def evaluar_exacto(model, tokenizer, filas, campos, system, limite=None, titulo="", lote=16):
    from collections import Counter
    filas = filas[:limite] if limite else filas
    aciertos, total, fallos = Counter(), Counter(), []
    exactos = 0
    t0 = time.time()
    lado_original = tokenizer.padding_side
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    preds = []
    for i in range(0, len(filas), lote):
        preds.extend(generar_lote(model, tokenizer, [f["texto"] for f in filas[i:i + lote]], system))
    tokenizer.padding_side = lado_original
    for fila, pred in zip(filas, preds):
        tgt = fila["target"]
        ok_fila = True
        for campo in campos:
            total[campo] += 1
            if pred.get(campo) == tgt.get(campo):
                aciertos[campo] += 1
            else:
                ok_fila = False
                fallos.append({"texto": fila["texto"], "campo": campo,
                               "gt": tgt.get(campo), "pred": pred.get(campo)})
        exactos += ok_fila
    resumen = {
        "conjunto": titulo, "n": len(filas), "exactos": exactos,
        "exactitud": round(100.0 * exactos / max(len(filas), 1), 1),
        "por_campo": {c: round(100.0 * aciertos[c] / max(total[c], 1), 1) for c in campos},
        "fallos": fallos[:40],
        "segundos": round(time.time() - t0, 1),
    }
    print("\n=== %s: exacto %d/%d = %.1f%% (%.1fs) ===" % (
        titulo, exactos, len(filas), resumen["exactitud"], resumen["segundos"]))
    for campo in campos:
        print("  %-22s %5.1f%%" % (campo, resumen["por_campo"][campo]))
    for f in fallos[:10]:
        print("   FALLA %-50s %s: gt=%r pred=%r" % (
            f["texto"][:50], f["campo"], f["gt"], f["pred"]))
    return resumen


# ---------------------------------------------------------------------------
# modelo
# ---------------------------------------------------------------------------

def construir_modelo(args, tokenizer):
    import torch
    if args.smoke:
        # modelo diminuto aleatorio: valida el CODIGO del bucle, no aprende nada
        from transformers import Qwen2Config, Qwen2ForCausalLM
        cfg = Qwen2Config(
            vocab_size=len(tokenizer), hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            max_position_embeddings=1024,
        )
        return Qwen2ForCausalLM(cfg), "smoke (modelo diminuto aleatorio)"

    from transformers import AutoModelForCausalLM
    cuda = torch.cuda.is_available()
    cuantizar = (not args.sin_cuantizar) and cuda

    if cuantizar:
        from transformers import BitsAndBytesConfig
        bnb = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16,
        )
        modelo = AutoModelForCausalLM.from_pretrained(
            args.modelo, quantization_config=bnb, device_map="auto")
        modo = "4-bit NF4 + LoRA (GPU)"
    else:
        modelo = AutoModelForCausalLM.from_pretrained(args.modelo)
        modo = "sin cuantizar + LoRA (CPU/smoke)"
    return modelo, modo


def aplicar_lora(modelo, args):
    from peft import LoraConfig, get_peft_model
    # checkpointing NO reentrante: con el modelo base congelado (4-bit), la
    # variante reentrante corta el grafo y ningun gradiente llega a LoRA
    # ("No inf checks were recorded" del GradScaler en T4).
    gc_kwargs = {"use_reentrant": False}
    if getattr(modelo, "is_loaded_in_4bit", False) or getattr(modelo, "is_loaded_in_8bit", False):
        from peft import prepare_model_for_kbit_training
        modelo = prepare_model_for_kbit_training(
            modelo, use_gradient_checkpointing=True, gradient_checkpointing_kwargs=gc_kwargs)
    else:
        modelo.gradient_checkpointing_enable(gradient_checkpointing_kwargs=gc_kwargs)
    modelo.enable_input_require_grads()
    lora = LoraConfig(
        r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    modelo = get_peft_model(modelo, lora)
    modelo.print_trainable_parameters()
    return modelo


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fine-tuning QLoRA del extractor semantico")
    ap.add_argument("--modelo", default="Qwen/Qwen3-4B-Instruct-2507")
    ap.add_argument("--datos", default=RUTA_DATOS_DEFAULT)
    ap.add_argument("--epocas", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--accum", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=None,
                    help="tokens por ejemplo; por defecto el maximo medido en los datos + margen")
    ap.add_argument("--max-steps", type=int, default=None, help="corta el entrenamiento (smoke/depuracion)")
    ap.add_argument("--eval-limite", type=int, default=None, help="limita frases en la evaluacion")
    ap.add_argument("--eval-lote", type=int, default=16, help="frases por lote al generar en la evaluacion")
    ap.add_argument("--reanudar", action="store_true",
                    help="continua desde el ultimo checkpoint en --salida (tras una desconexion de Colab)")
    ap.add_argument("--sin-cuantizar", action="store_true", help="no usar bitsandbytes (CPU)")
    ap.add_argument("--smoke", action="store_true", help="modelo diminuto aleatorio: solo valida codigo")
    ap.add_argument("--salida", default="qwen-semantic-lora")
    ap.add_argument("--semilla", type=int, default=42)
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from transformers import AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    torch.manual_seed(args.semilla)

    train_raw, dev_raw, hard_raw, prompts = cargar_todo(args.datos)
    system = prompts["prompt_semantico"]
    campos = prompts["campos_modelo"]
    print("datos: train=%d dev=%d hard_dev=%d | campos=%s" % (
        len(train_raw), len(dev_raw), len(hard_raw), campos))

    # el smoke usa el tokenizer real del modelo: valida la plantilla de chat que se entrenara
    tokenizer = AutoTokenizer.from_pretrained(args.modelo)

    modelo, modo = construir_modelo(args, tokenizer)
    modelo = aplicar_lora(modelo, args)
    print("modo de entrenamiento:", modo)

    tok_train, largos = tokenizar([a_ejemplo(f, system) for f in train_raw], tokenizer)
    tok_dev, largos_dev = tokenizar([a_ejemplo(f, system) for f in dev_raw], tokenizer)
    total_max = max(largos["total_max"], largos_dev["total_max"])
    if args.max_length is None:
        args.max_length = total_max + 8
    elif args.max_length < total_max:
        raise SystemExit("--max-length %d truncaria ejemplos (el mas largo tiene %d tokens): "
                         "el JSON objetivo quedaria fuera de la loss" % (args.max_length, total_max))
    print("tokens por ejemplo: prompt<=%d | respuesta %d-%d (lo unico con loss) | "
          "total %d-%d | max_length=%d" % (
              largos["prompt_max"], largos["respuesta_min"], largos["respuesta_max"],
              largos["total_min"], total_max, args.max_length))

    ds_train = Dataset.from_list(tok_train)
    ds_dev = Dataset.from_list(tok_dev)

    cuda = torch.cuda.is_available()
    # precision explicita por entorno: trl activa bf16 por defecto si fp16=False,
    # y transformers v5 lo rechaza en CPU. En T4 va fp16 (nunca bf16).
    precision = {"fp16": cuda, "bf16": False}
    if not cuda:
        precision["use_cpu"] = True
    # warmup_steps calculado a mano: portable entre transformers 4.x y 5.x
    # (en v5 desaparecio warmup_ratio)
    pasos_por_epoca = max(1, len(train_raw) // (args.batch * args.accum))
    total_pasos = args.max_steps if args.max_steps else int(pasos_por_epoca * args.epocas)
    warmup_steps = max(1, int(0.03 * total_pasos))
    cfg = SFTConfig(
        output_dir=args.salida,
        num_train_epochs=args.epocas,
        max_steps=args.max_steps if args.max_steps else -1,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
        **precision,
        logging_steps=25,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,                  # el mejor checkpoint siempre se conserva
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        max_length=args.max_length,          # trl>=0.21: max_length, no max_seq_length
        completion_only_loss=True,           # loss solo sobre el JSON objetivo
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to=[],
        seed=args.semilla,
    )

    trainer = SFTTrainer(
        model=modelo, args=cfg,
        train_dataset=ds_train, eval_dataset=ds_dev,
        processing_class=tokenizer,
    )
    # con modelos 4-bit, trl 0.21 re-aplica prepare_model_for_kbit_training, que
    # congela TODOS los parametros (LoRA incluida). El optimizador se crea en
    # train(), asi que basta con reactivar los pesos LoRA aqui.
    for n, p in trainer.model.named_parameters():
        if "lora_" in n:
            p.requires_grad_(True)
    # guarda: lo que trl va a entrenar debe ser exactamente la mascara construida aqui
    mascara = trainer.train_dataset[0]["completion_mask"]
    if sum(mascara) != sum(tok_train[0]["completion_mask"]) or len(mascara) != len(tok_train[0]["input_ids"]):
        raise SystemExit("trl altero la mascara de loss (%d tokens con loss, se esperaban %d)" % (
            sum(mascara), sum(tok_train[0]["completion_mask"])))
    print("mascara de loss verificada: %d de %d tokens del ejemplo 0 entrenan (solo el JSON)" % (
        sum(mascara), len(mascara)))
    # guarda: un backward de prueba debe dejar gradiente en los pesos LoRA
    # (sobre trainer.model: es lo que se entrena, aunque trl lo haya re-envuelto)
    modelo_t = trainer.model
    lote = trainer.data_collator([trainer.train_dataset[0]])
    lote = {k: v.to(modelo_t.device) for k, v in lote.items() if hasattr(v, "to")}
    modelo_t.train()
    with torch.autocast(device_type=modelo_t.device.type, dtype=torch.float16, enabled=cuda):
        perdida = modelo_t(**lote).loss
    perdida.backward()
    estado = {}
    for n, p in modelo_t.named_parameters():
        if p.requires_grad:
            k = ("sin_grad" if p.grad is None else "no_finito" if not torch.isfinite(p.grad).all()
                 else "cero" if p.grad.abs().sum() == 0 else "ok")
            estado[k] = estado.get(k, 0) + 1
    modelo_t.zero_grad(set_to_none=True)
    con_grad = estado.get("ok", 0)
    if con_grad == 0:
        raise SystemExit("el backward de prueba no dejo gradiente en LoRA: el entrenamiento no aprenderia "
                         "(loss=%s, claves del lote=%s, entrenables=%s, mismo_modelo=%s)" % (
                             perdida.item(), sorted(lote), estado, modelo_t is modelo))
    print("gradiente verificado: %d tensores LoRA reciben gradiente (loss inicial %.3f)" % (
        con_grad, perdida.item()))
    reanudar = False
    if args.reanudar:
        from transformers.trainer_utils import get_last_checkpoint
        ultimo = get_last_checkpoint(args.salida) if os.path.isdir(args.salida) else None
        print("reanudando desde:", ultimo or "(no hay checkpoints; empieza de cero)")
        reanudar = ultimo or False
    t0 = time.time()
    resultado = trainer.train(resume_from_checkpoint=reanudar)
    print("entrenamiento en %.1fs | train loss final: %.4f" % (
        time.time() - t0, resultado.training_loss))

    historial = [(h.get("step"), h.get("eval_loss")) for h in trainer.state.log_history if "eval_loss" in h]
    if historial:
        mejor = min(historial, key=lambda x: x[1])
        print("curva eval_loss:", ["%s:%.3f" % (s, e) for s, e in historial[-8:]])
        print("mejor eval_loss en step %s (%.4f)" % (mejor[0], mejor[1]))

    # --- evaluacion por exact-match ---------------------------------------
    modelo.eval()
    resumen = {
        "modelo": args.modelo, "modo": modo, "epocas": args.epocas,
        "max_steps": args.max_steps, "semilla": args.semilla,
        "train_loss_final": resultado.training_loss,
        "eval_loss_historial": historial,
    }
    modelo.config.use_cache = True           # gradient checkpointing lo apago al entrenar
    if not args.smoke:
        resumen["hard_dev"] = evaluar_exacto(
            modelo, tokenizer, hard_raw, campos, system,
            limite=args.eval_limite, titulo="hard_dev (patrones dificles)", lote=args.eval_lote)
        resumen["dev"] = evaluar_exacto(
            modelo, tokenizer, dev_raw, campos, system,
            limite=args.eval_limite, titulo="dev (general)", lote=args.eval_lote)
    else:
        # modelo aleatorio: solo se valida que la generacion por lotes corre
        evaluar_exacto(modelo, tokenizer, hard_raw, campos, system,
                       limite=4, titulo="[smoke] generacion por lotes", lote=2)

    # --- guardar ----------------------------------------------------------
    os.makedirs(args.salida, exist_ok=True)
    trainer.save_model(args.salida)
    tokenizer.save_pretrained(args.salida)
    resumen["config"] = {
        "lora": {"r": args.r, "alpha": args.alpha, "dropout": args.dropout},
        "lr": args.lr, "batch_efectivo": args.batch * args.accum,
        "max_length": args.max_length, "tokens": largos, "completion_only_loss": True,
        "n_train": len(train_raw), "n_dev": len(dev_raw), "n_hard_dev": len(hard_raw),
        "target": campos,
    }
    with open(os.path.join(args.salida, "config_entrenamiento.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print("\nadapter + configuracion guardados en: %s" % args.salida)


if __name__ == "__main__":
    main()
