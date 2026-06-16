"""
cerebro/cliente.py — Carga la API key del .env y crea el cliente de Claude.

La clave se lee SIEMPRE del archivo .env (variable ANTHROPIC_API_KEY) y nunca
se escribe en código ni se imprime.
"""
from __future__ import annotations

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # carga las variables del .env de la carpeta del proyecto

MODELO = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")


def get_client() -> Anthropic:
    """Devuelve un cliente de Anthropic. Lanza error claro si falta la clave."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.startswith("PEGA_AQUI"):
        raise RuntimeError(
            "No hay ANTHROPIC_API_KEY válida en el archivo .env. "
            "Abre .env y pega tu clave (sk-ant-...)."
        )
    return Anthropic(api_key=api_key)


def test_conexion() -> tuple[bool, str]:
    """Hace una llamada mínima para comprobar que la clave funciona."""
    try:
        client = get_client()
        resp = client.messages.create(
            model=MODELO,
            max_tokens=5,
            messages=[{"role": "user", "content": "responde solo: ok"}],
        )
        texto = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return True, texto.strip()
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ok, detalle = test_conexion()
    if ok:
        print(f"conecta OK  (modelo: {MODELO}, respondió: {detalle!r})")
    else:
        print(f"ERROR de conexion -> {detalle}")
