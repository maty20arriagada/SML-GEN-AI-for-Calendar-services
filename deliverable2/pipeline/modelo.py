# -*- coding: utf-8 -*-
"""
modelo.py -- Adaptadores de generacion.

GeneradorHF   : Qwen3-4B-Instruct-2507 en Colab T4 (fp16) con adapter LoRA opcional.
GeneradorMock : respuestas fijas, para tests y desarrollo sin GPU.

Ambos exponen el mismo metodo: generar(mensajes) -> str
"""

from __future__ import annotations


class GeneradorMock:
    """Respuestas predefinidas: {clave: salida}. La clave puede ser la frase
    exacta o '*'; si no hay coincidencia, devuelve `por_defecto`."""

    def __init__(self, respuestas: dict | None = None, por_defecto: str = "{}"):
        self.respuestas = respuestas or {}
        self.por_defecto = por_defecto
        self.llamadas = []

    def generar(self, mensajes, **kwargs) -> str:
        self.llamadas.append(mensajes)
        ultimo = ""
        for m in reversed(mensajes):
            if m.get("role") == "user":
                ultimo = m.get("content", "")
                break
        for clave, salida in self.respuestas.items():
            if clave != "*" and clave in ultimo:
                return salida
        return self.respuestas.get("*", self.por_defecto)


class GeneradorHF:
    """Modelo real sobre HuggingFace Transformers. Requiere GPU (Colab T4)."""

    def __init__(
        self,
        modelo_id: str = "Qwen/Qwen3-4B-Instruct-2507",
        adapter: str | None = None,
        dtype: str = "float16",
        device_map: str = "auto",
        semilla: int = 42,
    ):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        torch.manual_seed(semilla)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(semilla)

        self.tokenizer = AutoTokenizer.from_pretrained(modelo_id)
        modelo = AutoModelForCausalLM.from_pretrained(
            modelo_id,
            torch_dtype=getattr(torch, dtype),
            device_map=device_map,
        )
        if adapter:
            from peft import PeftModel

            modelo = PeftModel.from_pretrained(modelo, adapter)
            modelo = modelo.merge_and_unload()
        self.modelo = modelo.eval()
        self.modelo_id = modelo_id
        self.adapter = adapter

    def generar(
        self,
        mensajes,
        max_new_tokens: int = 256,
        temperature: float = 0.01,
        top_p: float = 0.95,
    ) -> str:
        try:
            # modelos hibridos de Qwen3: sin bloques de thinking
            prompt = self.tokenizer.apply_chat_template(
                mensajes, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            prompt = self.tokenizer.apply_chat_template(
                mensajes, tokenize=False, add_generation_prompt=True
            )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.modelo.device)
        with self.torch.no_grad():
            salidas = self.modelo.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                top_p=top_p,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        texto = self.tokenizer.decode(
            salidas[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True
        )
        return texto.strip()
