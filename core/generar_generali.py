"""
core/generar_generali.py — Arma el correo de Generali a partir de la cotización.

Por ahora toma los datos DETERMINISTAS del lector. La normalización fina del
teléfono (p.ej. "+971 0505582131") y la decisión de dirección las afinará el
"cerebro" (Claude) más adelante; aquí dejamos los valores tal cual vienen.
"""
from __future__ import annotations

from reglas.generali import construir_correo_generali


def generar_generali(datos: dict) -> dict:
    """
    `datos` = salida de core.leer_cotizacion.leer_cotizacion().
    Devuelve {"asunto": ..., "cuerpo": ..., "avisos": [...]}.
    """
    avisos = []

    # FECHA_EFECTO = "Fecha de inicio de la póliza" (sección Método de Pago),
    # NO la "Fecha efecto" de la cabecera.
    fecha_efecto = datos.get("fecha_inicio_poliza", "")
    if not fecha_efecto:
        avisos.append("Falta la 'Fecha de inicio de la póliza' (efecto del correo).")

    telefono = datos.get("telefono_movil", "")
    if not telefono:
        avisos.append("Falta el teléfono móvil.")

    direccion = datos.get("direccion", "")
    if not direccion:
        avisos.append("Falta la dirección de la persona.")

    variables = {
        "nombre_completo": datos.get("nombre", ""),
        "fecha_efecto": fecha_efecto,
        "correo": datos.get("correo", ""),
        "telefono": telefono,
        "direccion": direccion,
    }

    correo = construir_correo_generali(variables)
    correo["avisos"] = avisos
    return correo


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from config import ENTRADAS_DIR
    from core.leer_cotizacion import leer_cotizacion

    # Buscar la cotización de Generali (ALUMNUSCARE) en entradas/.
    for pdf in sorted(ENTRADAS_DIR.glob("*.pdf")):
        datos = leer_cotizacion(pdf)
        if datos.get("aseguradora_detectada") == "GENERALI":
            correo = generar_generali(datos)
            print(f"# Cotización: {pdf.name}\n")
            print("ASUNTO:")
            print(correo["asunto"])
            print("\nCUERPO:")
            print(correo["cuerpo"])
            if correo["avisos"]:
                print("\nAVISOS:")
                for a in correo["avisos"]:
                    print(f"  - {a}")
            print("\n" + "=" * 70)
