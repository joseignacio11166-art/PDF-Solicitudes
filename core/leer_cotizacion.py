"""
core/leer_cotizacion.py — Lectura DETERMINISTA de la cotización HiBroker.

Las cotizaciones de HiBroker tienen una estructura muy regular ("Etiqueta: valor"),
así que extraemos los campos crudos con el código (sin IA). El "cerebro" (Claude)
se encarga después de lo que requiere CRITERIO (partir nombre/apellidos, normalizar
teléfonos, resumir salud, decidir dirección...).

Salida: un dict `datos_crudos` con lo que pone LITERALMENTE el PDF + la aseguradora
detectada + el cuestionario de salud ya parseado.
"""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from config import DETECCION_PRODUCTO


# Etiquetas "Etiqueta: valor" que aparecen en la cotización (datos del asegurado).
_CAMPOS_SIMPLES = {
    "nombre": "Nombre",
    "tipo_documento": "Tipo de Documento de Identidad",
    "numero_documento": "Número Documento de Identidad",
    "sexo": "Sexo",
    "peso_kg": "Peso (kg)",
    "altura_cm": "Altura (cm)",
    "fecha_nacimiento": "Fecha de nacimiento",
    "telefono_movil": "Teléfono móvil",
    "telefono_fijo": "Teléfono fijo",
    "correo": "Correo electrónico",
    "direccion": "Dirección",
    "numero_via": "Número",
    "portal_edificio_piso": "Portal, edificio, piso",
    "codigo_postal": "Código Postal",
    "municipio": "Municipio",
    "pais": "País",
}

# Las 4 preguntas del cuestionario de salud, en orden.
_PREGUNTAS_SALUD = [
    "¿Padece o ha padecido de alguna enfermedad o ha sufrido un accidente en los "
    "últimos cinco años que haya precisado de un tratamiento médico?",
    "¿Ha estado alguna vez o tiene previsto ser hospitalizado y/o intervenido "
    "quirúrgicamente?",
    "¿Se encuentra actualmente bajo tratamiento médico?",
    "¿Tiene algún síntoma o dolor, no diagnosticado y manifestado de forma "
    "continuada o reiterada?",
]


def _texto_completo(ruta_pdf: Path) -> str:
    """Devuelve el texto de todas las páginas concatenado."""
    partes = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def _valor_tras_etiqueta(texto: str, etiqueta: str) -> str:
    """
    Busca 'Etiqueta: valor' y devuelve el valor (o '' si está vacío).

    Captura SOLO hasta el fin de la línea ([^\\n]*), para que un campo vacío
    (p.ej. 'Teléfono fijo:') no se trague la línea siguiente.
    """
    patron = re.compile(
        r"^[ \t]*" + re.escape(etiqueta) + r"[ \t]*:[ \t]*([^\n]*)",
        re.MULTILINE,
    )
    m = patron.search(texto)
    return m.group(1).strip() if m else ""


def detectar_aseguradora(producto: str) -> str | None:
    """Decide la aseguradora a partir del código del campo 'Producto'."""
    p = (producto or "").strip().upper()
    for clave, aseguradora in DETECCION_PRODUCTO.items():
        if clave.upper() in p:
            return aseguradora
    return None


def _parsear_cuestionario_salud(texto: str) -> dict:
    """
    Parsea las 4 preguntas de salud. Devuelve cada respuesta (Sí/No), el detalle
    si lo hay, y si hay ALGÚN 'Sí' (regla crítica: si hay un 'Sí' no se marca a
    ciegas y se debe gestionar a mano).

    Las preguntas pueden partirse en varias líneas en el PDF, así que NO casamos
    el texto completo de la pregunta: localizamos cada item numerado "1." .. "4."
    y, dentro de su bloque, tomamos la respuesta que sigue al "?:".
    """
    # Acotar a la sección del cuestionario (evita falsos "1." en otras partes).
    ini = texto.find("Cuestionario de salud")
    seccion = texto[ini:] if ini != -1 else texto

    inicios = list(re.finditer(r"(?m)^\s*([1-4])\.\s", seccion))
    respuestas = []
    tiene_algun_si = False
    detalle_global = ""

    for idx, m in enumerate(inicios):
        num = int(m.group(1))
        fin = inicios[idx + 1].start() if idx + 1 < len(inicios) else len(seccion)
        bloque = seccion[m.start():fin]

        ans = re.search(r"\?\s*:\s*(Si|Sí|No)\b", bloque, re.IGNORECASE)
        valor = ""
        if ans:
            bruto = ans.group(1).lower()
            valor = "Sí" if bruto in ("si", "sí") else "No"
            if valor == "Sí":
                tiene_algun_si = True

        det = re.search(r"Detalles\s*:\s*([^\n]+)", bloque)
        detalle = det.group(1).strip() if det else ""
        if detalle:
            detalle_global = detalle

        respuestas.append({
            "numero": num,
            "pregunta": _PREGUNTAS_SALUD[num - 1] if 1 <= num <= 4 else "",
            "respuesta": valor,
            "detalle": detalle,
        })

    return {
        "respuestas": respuestas,
        "tiene_algun_si": tiene_algun_si,
        "detalle_original": detalle_global,
    }


def leer_cotizacion(ruta_pdf: str | Path) -> dict:
    """
    Lee una cotización HiBroker y devuelve los datos crudos + aseguradora detectada.
    """
    ruta_pdf = Path(ruta_pdf)
    texto = _texto_completo(ruta_pdf)

    # Campo "Producto": es la línea JUSTO debajo del encabezado "Producto"
    # (p.ej. "SANITAS_STUDENTS"). OJO: no buscar la palabra "Sanitas" en todo el
    # texto, porque la cláusula legal de la pág. 4 la contiene en las 3 cotizaciones.
    m_prod = re.search(r"(?m)^[ \t]*Producto[ \t]*\n[ \t]*([A-Za-z0-9_]+)", texto)
    producto = m_prod.group(1).strip() if m_prod else ""

    datos = {campo: _valor_tras_etiqueta(texto, etq) for campo, etq in _CAMPOS_SIMPLES.items()}
    datos["producto"] = producto
    datos["aseguradora_detectada"] = detectar_aseguradora(producto)

    # Cabecera
    datos["fecha_efecto_cabecera"] = _valor_tras_etiqueta(texto, "Fecha efecto")
    datos["mediador_cotizacion"] = _valor_tras_etiqueta(texto, "Mediador")

    # Sección Método de Pago (la fecha BUENA de efecto está aquí, NO en la cabecera)
    datos["fecha_inicio_poliza"] = _valor_tras_etiqueta(texto, "Fecha de inicio de la póliza")
    datos["metodo_pago"] = _valor_tras_etiqueta(texto, "Método de pago")

    # Cuestionario de salud
    datos["cuestionario_salud"] = _parsear_cuestionario_salud(texto)

    datos["_texto_completo"] = texto
    return datos


if __name__ == "__main__":
    # Prueba rápida contra las cotizaciones de la carpeta entradas/.
    import json
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # tildes/ñ legibles en consola
    except Exception:
        pass
    from config import ENTRADAS_DIR

    for pdf in sorted(ENTRADAS_DIR.glob("*.pdf")):
        d = leer_cotizacion(pdf)
        d.pop("_texto_completo", None)
        print("=" * 70)
        print(f"ARCHIVO: {pdf.name}")
        print(f"  Producto: {d['producto']!r}  ->  {d['aseguradora_detectada']}")
        print(json.dumps(d, ensure_ascii=False, indent=2))
