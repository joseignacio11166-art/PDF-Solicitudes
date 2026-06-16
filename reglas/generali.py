"""
reglas/generali.py — Plantilla y reglas del correo de Generali.

Resultado de Generali = un CORREO (asunto + cuerpo), NO un PDF.
Las líneas 1# a 10#, el pago y la nota son FIJAS (config.FIJOS_GENERALI).
Solo son variables: nombre completo, fecha de efecto, correo, teléfono y dirección.
"""
from __future__ import annotations

from config import FIJOS_GENERALI

# Plantilla del cuerpo. Los {marcadores} se rellenan con datos de la cotización;
# el resto es texto FIJO confirmado por la usuaria.
_PLANTILLA_CUERPO = """\
1# Código Tipología: {codigo_tipologia}
2# Código Tipo de Petición: {codigo_tipo_peticion}
3# Código Entidad/Mediador: {codigo_entidad_mediador}
4# Código Peticionario:
5# Mail Peticionario: {mail_peticionario}
6# Teléfono Peticionario:
7# Cliente (DNI) (Opcional):
8# Póliza (RamoCiaPóliza) (Opcional):
9# Aplicación (Opcional):
10# Agrupación Ramo: {agrupacion_ramo}
11# Observaciones:

* Efecto: {fecha_efecto}
* Pago: {pago}
* Correo: {correo}
* Teléfono: {telefono}
* Dirección: {direccion}

Nota: {nota}"""


def construir_correo_generali(variables: dict) -> dict:
    """
    Construye asunto y cuerpo del correo de Generali.

    `variables` (lo que sale de la cotización / del cerebro) debe traer:
      - nombre_completo
      - fecha_efecto   (la "Fecha de inicio de la póliza", dd/mm/aaaa)
      - correo
      - telefono
      - direccion
    """
    f = FIJOS_GENERALI

    asunto = f"{f['asunto_prefijo']} ({variables.get('nombre_completo', '').strip()})"

    cuerpo = _PLANTILLA_CUERPO.format(
        codigo_tipologia=f["codigo_tipologia"],
        codigo_tipo_peticion=f["codigo_tipo_peticion"],
        codigo_entidad_mediador=f["codigo_entidad_mediador"],
        mail_peticionario=f["mail_peticionario"],
        agrupacion_ramo=f["agrupacion_ramo"],
        pago=f["pago"],
        nota=f["nota"],
        fecha_efecto=variables.get("fecha_efecto", "").strip(),
        correo=variables.get("correo", "").strip(),
        telefono=variables.get("telefono", "").strip(),
        direccion=variables.get("direccion", "").strip(),
    )

    return {"asunto": asunto, "cuerpo": cuerpo}
