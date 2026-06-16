"""
cerebro/prompt_extraccion.py — El "cerebro": razona lo VARIABLE con Claude.

Recibe los datos ya extraídos de forma determinista (core.leer_cotizacion) + el
texto de la cotización, y devuelve un JSON con los campos que requieren CRITERIO:
partir nombre/apellidos, normalizar teléfono, fechas a dd/mm/aaaa, inferir
provincia, decidir si la dirección es de España, y resumir el cuestionario de salud.

Reglas que se imponen a Claude:
- No inventar datos. Si falta algo, dejarlo vacío y añadir un aviso.
- Fechas SIEMPRE dd/mm/aaaa.
- Apellidos = lo último del nombre; ante la duda, avisar (no adivinar a ciegas).
- Resumir el cuestionario de salud fiel pero apto para una casilla corta.
- NUNCA decidir marcar casillas de salud: eso lo hace el código según la regla.
"""
from __future__ import annotations

import json

from cerebro.cliente import MODELO, get_client

# Esquema que Claude DEBE rellenar (se fuerza con tool_choice).
_ESQUEMA = {
    "type": "object",
    "properties": {
        "nombre_completo": {"type": "string"},
        "nombre": {"type": "string"},
        "apellidos": {"type": "string"},
        "tipo_documento": {"type": "string", "description": "Pasaporte, NIE, NIF o DNI"},
        "numero_documento": {"type": "string"},
        "sexo": {"type": "string", "enum": ["Hombre", "Mujer", ""]},
        "peso_kg": {"type": "string"},
        "altura_cm": {"type": "string"},
        "fecha_nacimiento": {"type": "string", "description": "dd/mm/aaaa"},
        "telefono_movil": {
            "type": "string",
            "description": "Normalizado con prefijo de país, p.ej. '+971 0505582131'",
        },
        "telefono_fijo": {"type": "string"},
        "correo": {"type": "string"},
        "nacionalidad": {
            "type": "string",
            "description": "Gentilicio en español (p.ej. 'Salvadoreña'). Infiérela de los "
            "indicios (país, prefijo telefónico). Es inferida: añade siempre un aviso para confirmar.",
        },
        "direccion_en_espana": {
            "type": "boolean",
            "description": "True si la persona tiene una dirección real en España.",
        },
        "direccion_via": {
            "type": "string",
            "description": "Tipo de vía + nombre, p.ej. 'Av. de Rodajos'. SOLO la vía.",
        },
        "direccion_numero": {"type": "string", "description": "Solo el número de la vía, p.ej. '80'"},
        "direccion_piso": {"type": "string", "description": "Solo el piso, p.ej. '2'"},
        "direccion_puerta": {"type": "string", "description": "Solo la puerta/letra, p.ej. 'A'"},
        "municipio": {"type": "string"},
        "provincia": {"type": "string", "description": "Inferida del municipio si hace falta"},
        "codigo_postal": {"type": "string"},
        "fecha_efecto": {
            "type": "string",
            "description": "dd/mm/aaaa. Es la 'Fecha de inicio de la póliza', NO la de cabecera.",
        },
        "metodo_pago": {"type": "string"},
        "cuestionario_salud": {
            "type": "object",
            "properties": {
                "tiene_algun_si": {"type": "boolean"},
                "resumen_para_formulario": {
                    "type": "string",
                    "description": "Resumen breve y fiel, apto para una casilla corta. '' si todo No.",
                },
                "detalle_original": {"type": "string"},
            },
            "required": ["tiene_algun_si", "resumen_para_formulario", "detalle_original"],
        },
        "avisos": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Dudas, datos que faltan o ambigüedades para que la usuaria revise.",
        },
    },
    "required": [
        "nombre_completo", "nombre", "apellidos", "tipo_documento", "numero_documento",
        "sexo", "peso_kg", "altura_cm", "fecha_nacimiento", "telefono_movil",
        "telefono_fijo", "correo", "nacionalidad", "direccion_en_espana", "direccion_via",
        "direccion_numero", "direccion_piso", "direccion_puerta", "municipio",
        "provincia", "codigo_postal", "fecha_efecto",
        "metodo_pago", "cuestionario_salud", "avisos",
    ],
}

_INSTRUCCIONES = """\
Eres un asistente de una correduría de seguros. Recibes los datos de una cotización
HiBroker (ya extraídos) y su texto completo. Devuelve los campos VARIABLES razonados
mediante la herramienta `devolver_datos`.

Reglas estrictas:
- NO inventes datos. Si un dato no aparece, déjalo vacío ("") y añade un aviso.
- Fechas SIEMPRE en formato dd/mm/aaaa.
- `fecha_efecto` = "Fecha de inicio de la póliza" (sección Método de Pago), NUNCA la
  "Fecha efecto" de la cabecera.
- Apellidos = la última parte del nombre completo. Si el orden es ambiguo (nombres
  extranjeros), haz tu mejor estimación Y añade un aviso para que se revise.
- `telefono_movil`: normaliza con prefijo internacional separado si se puede deducir
  el país (p.ej. "9710505582131" -> "+971 0505582131"). Si no estás seguro, deja el
  número tal cual y añade un aviso.
- `nacionalidad`: infiérela del país/indicios y exprésala como gentilicio español
  ('Salvadoreña', 'Ecuatoriana'…). Añade SIEMPRE un aviso de que es inferida.
- `direccion_en_espana`: true solo si hay una dirección real en España. Separa SIEMPRE
  la dirección en piezas: `direccion_via` (tipo+nombre, sin número), `direccion_numero`
  (solo el número), `direccion_piso` (solo el piso) y `direccion_puerta` (solo la letra/puerta).
  Infiere la provincia a partir del municipio.
- Cuestionario de salud: si alguna respuesta es "Sí", `tiene_algun_si`=true y resume
  el detalle de forma fiel y breve. Si todo es "No", `tiene_algun_si`=false y
  `resumen_para_formulario`="". NUNCA decides tú marcar casillas; solo resumes.
- La aseguradora YA la determina el código por el campo "Producto". El texto de
  "Tratamiento de datos Personales" menciona siempre a "Sanitas" como cláusula
  estándar en TODAS las cotizaciones: IGNÓRALO, no es señal de la aseguradora y no
  generes avisos por ello.
"""


def extraer_datos(datos_crudos: dict) -> dict:
    """Llama a Claude y devuelve el dict con los campos variables razonados."""
    client = get_client()

    # Pasamos los datos crudos (sin el texto largo duplicado) + el texto completo.
    crudos = {k: v for k, v in datos_crudos.items() if k != "_texto_completo"}
    texto = datos_crudos.get("_texto_completo", "")

    contenido = (
        "DATOS YA EXTRAÍDOS (determinista):\n"
        + json.dumps(crudos, ensure_ascii=False, indent=2)
        + "\n\nTEXTO COMPLETO DE LA COTIZACIÓN:\n"
        + texto
    )

    resp = client.messages.create(
        model=MODELO,
        max_tokens=2000,
        system=_INSTRUCCIONES,
        tools=[{
            "name": "devolver_datos",
            "description": "Devuelve los campos variables razonados de la cotización.",
            "input_schema": _ESQUEMA,
        }],
        tool_choice={"type": "tool", "name": "devolver_datos"},
        messages=[{"role": "user", "content": contenido}],
    )

    for bloque in resp.content:
        if getattr(bloque, "type", "") == "tool_use" and bloque.name == "devolver_datos":
            return bloque.input

    raise RuntimeError("Claude no devolvió los datos en el formato esperado.")


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from config import ENTRADAS_DIR
    from core.leer_cotizacion import leer_cotizacion

    for pdf in sorted(ENTRADAS_DIR.glob("*.pdf")):
        crudos = leer_cotizacion(pdf)
        print("=" * 70)
        print(f"ARCHIVO: {pdf.name}  ({crudos['aseguradora_detectada']})")
        datos = extraer_datos(crudos)
        print(json.dumps(datos, ensure_ascii=False, indent=2))
