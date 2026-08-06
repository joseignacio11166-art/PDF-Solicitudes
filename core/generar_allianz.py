"""
core/generar_allianz.py — Genera el Certificado de Póliza de Salud Allianz en Word editable.

Rellena la plantilla plantillas/allianz_certificado.docx (que tiene marcadores «CAMPO»)
con los datos del estudiante y devuelve el .docx en memoria. Todo el texto fijo
(coberturas, CIF, dirección de Allianz…) se mantiene idéntico al original.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date

from config import PLANTILLAS_DIR

PLANTILLA = PLANTILLAS_DIR / "allianz_certificado.docx"
POLIZA_PREFIJO = "58995003-"

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mas_un_ano(fecha: str) -> str:
    """dd/mm/aaaa -> mismo día/mes del año siguiente."""
    try:
        d, m, a = fecha.strip().split("/")
        return f"{d}/{m}/{int(a) + 1}"
    except Exception:
        return ""


def generar_allianz(datos: dict, hoy: date | None = None) -> bytes:
    hoy = hoy or date.today()
    fcert = f"{hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}"

    reps = {
        "«NOMBRE»": datos.get("nombre", ""),
        "«DOCTIPO»": datos.get("doc_tipo", "pasaporte"),
        "«DOCNUM»": datos.get("doc_num", ""),
        "«FNAC»": datos.get("fecha_nacimiento", ""),
        "«PAIS»": datos.get("pais", ""),
        "«LOCALIDAD»": datos.get("localidad", ""),
        "«POLIZA»": datos.get("poliza", ""),
        "«FINI»": datos.get("fecha_inicio", ""),
        "«FFIN»": datos.get("fecha_fin") or mas_un_ano(datos.get("fecha_inicio", "")),
        "«FCERT»": fcert,
    }

    zin = zipfile.ZipFile(PLANTILLA)
    xml = zin.read("word/document.xml").decode("utf-8")
    for marcador, valor in reps.items():
        xml = xml.replace(marcador, _esc(valor))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = xml.encode("utf-8") if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    return buf.getvalue()
