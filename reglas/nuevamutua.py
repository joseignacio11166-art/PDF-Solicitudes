"""
reglas/nuevamutua.py — Reglas y posiciones del overlay de Nueva Mutua.

El PDF de Nueva Mutua NO tiene campos: se escribe el texto ENCIMA por coordenadas
(calibradas sobre el PDF en blanco). Devuelve, por página, una lista de
(texto, x, y) en coordenadas de reportlab (origen abajo-izquierda).

Coordenadas calibradas con pdfplumber sobre plantillas/nuevamutua_blanco.pdf.
La casilla "x" de PAGO POR TARJETA y el "SÍ" de ¿aporta cuestionario? ya vienen
PREIMPRESOS en el blanco, así que no se añaden.
"""
from __future__ import annotations

from datetime import date

from config import FIJOS_NUEVA_MUTUA, OFICINA

H = 842  # alto de página
DY = 9    # ajuste vertical: baseline = H - top - DY

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _y(top: float) -> float:
    return H - top - DY


def _direccion_linea(datos: dict) -> str:
    """Dirección en una sola línea (Nueva Mutua). Oficina por defecto si no es de España."""
    if datos.get("direccion_en_espana") and datos.get("direccion_via"):
        via = datos.get("direccion_via", "")
        numero = datos.get("direccion_numero", "")
        piso = datos.get("direccion_piso", "")
        puerta = datos.get("direccion_puerta", "")
    else:
        via, numero = OFICINA["via"], OFICINA["numero"]
        piso, puerta = OFICINA["piso"], OFICINA["puerta"]
    linea = f"{via} {numero}".strip()
    if piso:
        linea += f", PISO {piso}"
        if puerta:
            linea += f" {puerta}"
    return linea


def _dato_direccion(datos: dict, campo: str) -> str:
    """Municipio/provincia/cp: del formulario o, si no es de España, de oficina."""
    if datos.get("direccion_en_espana") and datos.get("direccion_via"):
        return datos.get(campo, "")
    return {"municipio": OFICINA["municipio"], "provincia": OFICINA["provincia"],
            "codigo_postal": OFICINA["codigo_postal"]}.get(campo, "")


def construir_textos_nuevamutua(datos: dict, hoy: date | None = None) -> dict:
    """Devuelve {"pagina1": [(txt,x,y)], "pagina2": [...], "avisos": [...], "parar": bool}."""
    hoy = hoy or date.today()
    avisos: list[str] = []

    nombre = datos.get("nombre_completo", "")
    doc = datos.get("numero_documento", "")

    # Fecha alta deseada = fecha de inicio de la póliza (dd/mm/aaaa)
    dia = mes = anio2 = ""
    try:
        d, m, a = datos.get("fecha_efecto", "").split("/")
        dia, mes, anio2 = d.zfill(2), m.zfill(2), a[-2:]
    except Exception:
        avisos.append("No pude leer la fecha de alta deseada (fecha de inicio de la póliza).")

    # Sexo: X sobre la rayita antes de HOMBRE (x≈68) o MUJER (x≈123)
    sexo_x = []
    if datos.get("sexo") == "Mujer":
        sexo_x = [("X", 123, _y(502))]
    elif datos.get("sexo") == "Hombre":
        sexo_x = [("X", 68, _y(502))]

    pagina1 = [
        # Cabecera
        (dia, 124, _y(139)),
        (mes, 142, _y(139)),
        (anio2, 172, _y(139)),
        # MEDIADOR "ROSE & PAGES" ya viene PREIMPRESO en la plantilla (no añadir).
        # Tomador
        (nombre, 120, _y(179)),
        (doc, 76, _y(193)),
        (_direccion_linea(datos), 43, _y(221)),                     # dirección en línea de abajo
        (_dato_direccion(datos, "municipio"), 85, _y(235)),
        (_dato_direccion(datos, "provincia"), 321, _y(235)),
        (_dato_direccion(datos, "codigo_postal"), 100, _y(249)),
        (datos.get("correo", ""), 360, _y(249)),
        (datos.get("telefono_fijo", ""), 96, _y(264)),
        (datos.get("telefono_movil", ""), 343, _y(264)),
        # Prestación del servicio → "el mismo" (literal, confirmado)
        ("el mismo", 43, _y(351)),
        # Estudiante
        (nombre, 122, _y(451)),
        (doc, 121, _y(472)),
        (datos.get("fecha_nacimiento", ""), 391, _y(472)),
        (FIJOS_NUEVA_MUTUA["parentesco"], 421, _y(511)),           # "el mismo"
        # Cuestionario de salud: peso y estatura
        (datos.get("peso_kg", ""), 290, _y(571)),
        (datos.get("altura_cm", ""), 470, _y(571)),
    ] + sexo_x

    # Cuestionario salud SI/NO (REGLA CRÍTICA)
    salud = datos.get("cuestionario_salud", {})
    parar = bool(salud.get("tiene_algun_si"))
    if parar:
        avisos.append(
            "🛑 El cuestionario de salud tiene algún 'Sí'. NO se marca el 'NO' "
            "automáticamente: este caso requiere gestión manual."
        )
    else:
        pagina1.append(("X", 90, _y(737)))  # X sobre NO

    # Página 2: fecha de la solicitud = HOY (En Madrid, a __ de __ de __). Firma vacía.
    pagina2 = [
        ("Madrid", 60, _y(677)),
        (str(hoy.day), 156, _y(677)),
        (MESES[hoy.month - 1], 195, _y(677)),
        (str(hoy.year), 292, _y(677)),
    ]

    # Quitar entradas con texto vacío
    pagina1 = [(t, x, y) for (t, x, y) in pagina1 if str(t).strip()]
    pagina2 = [(t, x, y) for (t, x, y) in pagina2 if str(t).strip()]

    return {"pagina1": pagina1, "pagina2": pagina2, "avisos": avisos, "parar": parar}
