"""
core/rellenar_sanitas.py — Rellena el PDF AcroForm de Sanitas y lo deja EDITABLE.

REQUISITO: NUNCA aplanar. La persona debe poder corregir campos y firmar encima.
Por eso activamos NeedAppearances (para que el visor muestre los valores) y NO
fusionamos/aplanamos nada. La firma se deja vacía.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from config import PLANTILLA_SANITAS, SALIDAS_DIR
from reglas.sanitas import construir_valores_sanitas


def rellenar_sanitas(datos: dict, ruta_salida: str | Path | None = None, hoy: date | None = None) -> dict:
    """
    Rellena la plantilla de Sanitas con los datos (ya revisados).
    Devuelve {"ruta": Path, "avisos": [...], "parar": bool}.
    """
    construido = construir_valores_sanitas(datos, hoy=hoy)
    valores = construido["valores"]

    reader = PdfReader(str(PLANTILLA_SANITAS))
    writer = PdfWriter()
    writer.append(reader)

    # Escribir los valores en cada página donde aparezcan sus campos.
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, valores, auto_regenerate=False)
        except Exception:
            # Algún campo puede no estar en esta página; se ignora y sigue.
            pass

    # NeedAppearances: el visor regenera la apariencia -> los valores se ven y el
    # PDF sigue siendo editable (no aplanado).
    try:
        writer.set_need_appearances_writer(True)
    except Exception:
        pass

    SALIDAS_DIR.mkdir(exist_ok=True)
    if ruta_salida is None:
        apellidos = (datos.get("apellidos") or "solicitud").strip().replace(" ", "_")
        ruta_salida = SALIDAS_DIR / f"sanitas_{apellidos}.pdf"
    ruta_salida = Path(ruta_salida)

    with open(ruta_salida, "wb") as fh:
        writer.write(fh)

    return {"ruta": ruta_salida, "avisos": construido["avisos"], "parar": construido["parar"]}


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from config import ENTRADAS_DIR
    from core.leer_cotizacion import leer_cotizacion
    from cerebro.prompt_extraccion import extraer_datos

    # Probar con la cotización de Sanitas (Isabella).
    for pdf in sorted(ENTRADAS_DIR.glob("*.pdf")):
        crudos = leer_cotizacion(pdf)
        if crudos.get("aseguradora_detectada") != "SANITAS":
            continue
        print(f"Cotización: {pdf.name}")
        datos = extraer_datos(crudos)
        res = rellenar_sanitas(datos)
        print(f"PDF generado: {res['ruta']}")
        print(f"parar={res['parar']}  avisos={res['avisos']}")

        # Verificación: releer los valores escritos en el PDF resultante.
        print("\n--- Verificación de campos escritos ---")
        r = PdfReader(str(res["ruta"]))
        campos = r.get_fields()
        comprobar = [
            "pto. anterior", "mediador", "codigo mediador", "asegurados",
            "nombre tomador", "numero documento", "mes1", "año1",
            "domicilio tomador", "domicilio tomador n", "municipio tomador",
            "No Consiento", "No Consiento_2", "toggle_6",
            "nombre asegurado pag310", "parentesco10", "peso10", "estatura10",
            "No_310", "No_430", "No_530", "No_630", "No_630a",
            "No_61301", "No_6301", "No_630111",
            "dia2 firma", "día_3", "día_730",
        ]
        for c in comprobar:
            val = campos.get(c, {}).get("/V") if c in campos else "(no existe)"
            print(f"  {c:28} = {val!r}")
        break
