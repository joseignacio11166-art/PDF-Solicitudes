"""
cerebro/vision.py — Lee una solicitud (PDF) MIRÁNDOLA como imagen, con Claude.

Sirve para PDFs escaneados/aplanados donde los datos son imagen y no hay texto que
extraer por coordenadas. Renderiza las páginas con pypdfium2 y se las pasa a Claude,
que devuelve los campos ya estructurados (para revisarlos y regenerar la solicitud).
"""
from __future__ import annotations

import base64
import io

from cerebro.cliente import MODELO, get_client

# Campos que Claude debe leer de la solicitud (imagen). Incluye los de repatriación de NM.
_ESQUEMA = {
    "type": "object",
    "properties": {
        "aseguradora": {"type": "string", "enum": ["Sanitas", "Nueva Mutua", "Generali", ""]},
        "nombre_completo": {"type": "string"},
        "nombre": {"type": "string"},
        "apellidos": {"type": "string", "description": "La última parte del nombre completo."},
        "tipo_documento": {"type": "string", "description": "Pasaporte, NIE, NIF o DNI"},
        "numero_documento": {"type": "string"},
        "sexo": {"type": "string", "enum": ["Hombre", "Mujer", ""],
                 "description": "Mira qué casilla está MARCADA (X). Si ninguna, vacío."},
        "estado_civil": {"type": "string"},
        "peso_kg": {"type": "string"},
        "altura_cm": {"type": "string"},
        "fecha_nacimiento": {"type": "string", "description": "dd/mm/aaaa"},
        "telefono_movil": {"type": "string"},
        "telefono_fijo": {"type": "string"},
        "correo": {"type": "string"},
        "nacionalidad": {"type": "string", "description": "Gentilicio en español si se puede inferir."},
        "direccion_espana": {"type": "string", "description": "La dirección completa en España, en una línea, tal cual aparece."},
        "municipio": {"type": "string"},
        "provincia": {"type": "string"},
        "codigo_postal": {"type": "string"},
        "fecha_efecto": {"type": "string", "description": "Fecha de alta deseada, dd/mm/aaaa."},
        "repat_direccion": {"type": "string", "description": "Dirección en el extranjero para repatriación (NM)."},
        "repat_poblacion": {"type": "string"},
        "repat_provincia": {"type": "string"},
        "repat_codigo_postal": {"type": "string"},
        "mediador": {"type": "string"},
        "salud_resumen": {"type": "string", "description": "Si hay algún 'Sí' en el cuestionario de salud, resúmelo. Si todo es No, vacío."},
        "avisos": {"type": "array", "items": {"type": "string"},
                   "description": "Dudas o datos ilegibles para que la persona revise."},
    },
    "required": ["aseguradora", "nombre_completo", "numero_documento", "sexo",
                 "municipio", "provincia", "codigo_postal", "avisos"],
}

_INSTRUCCIONES = """\
Eres un asistente de una correduría de seguros. Recibes la IMAGEN de una solicitud de
seguro de salud ya rellenada (puede estar escaneada o ser una foto). Lee con cuidado
TODOS los datos que veas y devuélvelos con la herramienta `devolver_datos`.

Reglas:
- Lee lo que REALMENTE aparece escrito. No inventes. Si un dato no se ve o está en blanco,
  déjalo vacío ("") y añade un aviso.
- Fechas SIEMPRE dd/mm/aaaa.
- `sexo`: fíjate en qué casilla (HOMBRE / MUJER) tiene la marca (X). Si ninguna está marcada, vacío.
- La dirección en España ponla entera en `direccion_espana` (una sola línea).
- Si es de Nueva Mutua, rellena también la dirección de repatriación (país de origen).
- `salud_resumen`: solo si ves algún "Sí" marcado en el cuestionario de salud.
"""


def _paginas_a_imagenes(ruta: str, max_paginas: int = 2, escala: float = 2.0) -> list[str]:
    import pypdfium2
    doc = pypdfium2.PdfDocument(ruta)
    fuera = []
    for i in range(min(len(doc), max_paginas)):
        img = doc[i].render(scale=escala).to_pil().convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        fuera.append(base64.b64encode(buf.getvalue()).decode())
    return fuera


def leer_solicitud(ruta: str) -> dict:
    """Devuelve los datos de la solicitud leídos de la imagen del PDF."""
    client = get_client()
    imagenes = _paginas_a_imagenes(ruta)
    contenido = [{"type": "image",
                  "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}
                 for b64 in imagenes]
    contenido.append({"type": "text", "text": "Lee esta solicitud y devuelve los datos."})

    resp = client.messages.create(
        model=MODELO,
        max_tokens=2000,
        system=_INSTRUCCIONES,
        tools=[{"name": "devolver_datos",
                "description": "Devuelve los datos leídos de la solicitud.",
                "input_schema": _ESQUEMA}],
        tool_choice={"type": "tool", "name": "devolver_datos"},
        messages=[{"role": "user", "content": contenido}],
    )
    for bloque in resp.content:
        if getattr(bloque, "type", "") == "tool_use" and bloque.name == "devolver_datos":
            return bloque.input
    raise RuntimeError("La IA no devolvió los datos en el formato esperado.")


# ========================================================================
# FACTURAS RECIBIDAS (administración: cuentas por pagar)
# ========================================================================
_ESQUEMA_FACTURA = {
    "type": "object",
    "properties": {
        "proveedor": {"type": "string", "description": "Nombre de QUIEN EMITE la factura (el que cobra)."},
        "cif_proveedor": {"type": "string"},
        "numero": {"type": "string", "description": "Número de la factura."},
        "fecha": {"type": "string", "description": "Fecha de emisión, dd/mm/aaaa."},
        "vencimiento": {"type": "string",
                        "description": "Fecha límite de pago, dd/mm/aaaa. Vacío si no aparece."},
        "base": {"type": "number", "description": "Base imponible (sin IVA)."},
        "iva": {"type": "number", "description": "Importe del IVA. 0 si no lleva."},
        "retencion": {"type": "number", "description": "Retención/IRPF como número POSITIVO. 0 si no lleva."},
        "total": {"type": "number", "description": "Total a pagar."},
        "moneda": {"type": "string", "description": "EUR, USD…"},
        "concepto": {"type": "string", "description": "Resumen corto de qué se factura."},
        "forma_pago": {"type": "string", "description": "Transferencia, domiciliado… con IBAN si aparece."},
        "avisos": {"type": "array", "items": {"type": "string"},
                   "description": "Dudas o datos que no se leen bien, para que la persona los revise."},
    },
    "required": ["proveedor", "numero", "fecha", "base", "iva", "total", "avisos"],
}

_INSTRUCCIONES_FACTURA = """\
Eres el asistente de administración de una correduría de seguros (Pagés Seguros).
Recibes la IMAGEN de una factura que le han ENVIADO a Pagés y que hay que pagar.
Lee los datos y devuélvelos con la herramienta `devolver_factura`.

Reglas:
- `proveedor` es QUIEN EMITE la factura (el que cobra), NO Pagés Seguros. Si ves a
  Pagés como cliente/destinatario, el proveedor es el otro.
- Importes como número, con punto decimal (1234.56), sin símbolo de moneda ni puntos
  de millar. La `retencion` en positivo aunque en la factura reste.
- Fechas SIEMPRE dd/mm/aaaa. Si el vencimiento no aparece, déjalo vacío y añade un aviso.
- Si un dato no se ve, déjalo vacío (o 0) y añade un aviso. NO inventes nada.
- Comprueba que base + iva - retencion ≈ total; si no cuadra, añade un aviso.
"""


def leer_factura(ruta: str) -> dict:
    """Lee una factura recibida (PDF, aunque sea escaneada) y devuelve sus datos."""
    client = get_client()
    imagenes = _paginas_a_imagenes(ruta, max_paginas=3)
    contenido = [{"type": "image",
                  "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}
                 for b64 in imagenes]
    contenido.append({"type": "text", "text": "Lee esta factura y devuelve sus datos."})

    resp = client.messages.create(
        model=MODELO,
        max_tokens=2000,
        system=_INSTRUCCIONES_FACTURA,
        tools=[{"name": "devolver_factura",
                "description": "Devuelve los datos leídos de la factura.",
                "input_schema": _ESQUEMA_FACTURA}],
        tool_choice={"type": "tool", "name": "devolver_factura"},
        messages=[{"role": "user", "content": contenido}],
    )
    for bloque in resp.content:
        if getattr(bloque, "type", "") == "tool_use" and bloque.name == "devolver_factura":
            return bloque.input
    raise RuntimeError("La IA no devolvió los datos de la factura en el formato esperado.")
