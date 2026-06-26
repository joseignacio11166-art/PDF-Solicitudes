"""
reglas/nuevamutua.py — Reglas y posiciones del overlay de Nueva Mutua (v2 2026).

El PDF de Nueva Mutua NO tiene campos: se escribe el texto ENCIMA por coordenadas
(calibradas sobre plantillas/nuevamutua_blanco.pdf = SOLICITUD v2 mayo 2026).

Cambios de la v2 respecto a la anterior:
- Es para UNA sola persona (el tomador ES el estudiante): un único bloque de datos.
- El MEDIADOR ya NO viene preimpreso → se escribe "ROSE & PAGES".
- En vez de "prestación del servicio en España" hay "Dirección en el extranjero
  para el caso de repatriación" (datos del país de origen; se rellenan a mano).
- DOS preguntas de salud (Sí/No): se marca "NO" en ambas si no se declara nada.
- El método de pago ya no lleva "X" (es anual fijo, preimpreso) → no se añade.
- "¿Aporta cuestionario de salud? SÍ" viene preimpreso → no se añade.
"""
from __future__ import annotations

from datetime import date

from config import FIJOS_NUEVA_MUTUA, OFICINA

H = 842
DY = 9

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _y(top: float) -> float:
    return H - top - DY


def _partes(fecha: str) -> tuple[str, str, str]:
    try:
        d, m, a = fecha.strip().split("/")
        return d.zfill(2), m.zfill(2), a
    except Exception:
        return "", "", ""


def _direccion_linea(datos: dict) -> str:
    """Dirección en España en una sola línea. Oficina por defecto si no es de España."""
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


def _dato_dir(datos: dict, campo: str) -> str:
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
    correo = datos.get("correo", "")

    dir_linea = _direccion_linea(datos)
    mun = _dato_dir(datos, "municipio")
    prov = _dato_dir(datos, "provincia")
    cp = _dato_dir(datos, "codigo_postal")

    # Fecha de alta deseada (dd/mm/aaaa)
    dia = mes = anio2 = ""
    try:
        d, m, a = datos.get("fecha_efecto", "").split("/")
        dia, mes, anio2 = d.zfill(2), m.zfill(2), a[-2:]
    except Exception:
        avisos.append("No pude leer la fecha de alta deseada (fecha de inicio de la póliza).")

    # Nacimiento
    dn, mn, an = _partes(datos.get("fecha_nacimiento", ""))

    # Sexo (casillas: Hombre x≈268, Mujer x≈314)
    sexo_x = []
    if datos.get("sexo") == "Mujer":
        sexo_x = [("X", 314, _y(315))]
    elif datos.get("sexo") == "Hombre":
        sexo_x = [("X", 268, _y(315))]

    # Dirección en el extranjero (repatriación) — se rellena a mano si la hay
    rep_dir = datos.get("repat_direccion", "")
    rep_pob = datos.get("repat_poblacion", "")
    rep_prov = datos.get("repat_provincia", "")
    rep_cp = datos.get("repat_cp", "")

    pagina1 = [
        # Cabecera
        (dia, 125, _y(138)),
        (mes, 143, _y(138)),
        (anio2, 172, _y(138)),
        (FIJOS_NUEVA_MUTUA["mediador"], 240, _y(138)),   # MEDIADOR (ya no preimpreso)
        # Datos del tomador (= estudiante)
        (nombre, 120, _y(179)),
        (doc, 120, _y(193)),
        (dir_linea, 43, _y(221)),                        # dirección en España (línea de abajo)
        (mun, 85, _y(235)),
        (prov, 321, _y(235)),
        (cp, 100, _y(249)),
        (correo, 360, _y(249)),
        (datos.get("telefono_fijo", ""), 96, _y(264)),
        (datos.get("telefono_movil", ""), 343, _y(264)),
        # Fecha de nacimiento (+ sexo abajo)
        (dn, 166, _y(317)),
        (mn, 194, _y(317)),
        (an, 213, _y(317)),
        # Dirección en el extranjero (repatriación)
        (rep_dir, 43, _y(407)),
        (rep_pob, 85, _y(421)),
        (rep_prov, 321, _y(421)),
        (rep_cp, 100, _y(434)),
        # Peso / estatura
        (datos.get("peso_kg", ""), 290, _y(481)),
        (datos.get("altura_cm", ""), 470, _y(481)),
    ] + sexo_x

    # Cuestionario de salud: DOS preguntas Sí/No.
    # Posición de la X: en "Sí" (x≈52) o en "No" (x≈90), para cada pregunta.
    salud = datos.get("cuestionario_salud", {})
    p1, p2 = salud.get("p1"), salud.get("p2")
    parar = False
    SI_X, NO_X = 52, 90
    if p1 is not None or p2 is not None:
        # Respuestas explícitas elegidas a mano: la X va donde se elija.
        for ans, top in [(p1, 688), (p2, 749)]:
            if ans == "Sí":
                pagina1.append(("X", SI_X, _y(top)))
            elif ans == "No":
                pagina1.append(("X", NO_X, _y(top)))
        if p1 == "Sí" or p2 == "Sí":
            avisos.append("Marcaste 'Sí' en alguna pregunta de salud: recuerda escribir el "
                          "detalle a mano en el PDF.")
    else:
        # Flujo cotización: si hay algún 'Sí' no se marca (gestión manual); si no, NO en ambas.
        parar = bool(salud.get("tiene_algun_si"))
        if parar:
            avisos.append("🛑 El cuestionario de salud tiene algún 'Sí'. NO se marca el 'NO' "
                          "automáticamente: este caso requiere gestión manual.")
        else:
            pagina1.append(("X", NO_X, _y(688)))
            pagina1.append(("X", NO_X, _y(749)))

    # Página 2: fecha de la solicitud = HOY. Firma vacía.
    pagina2 = [
        ("Madrid", 60, _y(712)),
        (str(hoy.day), 156, _y(712)),
        (MESES[hoy.month - 1], 195, _y(712)),
        (str(hoy.year), 340, _y(712)),
    ]

    pagina1 = [(t, x, y) for (t, x, y) in pagina1 if str(t).strip()]
    pagina2 = [(t, x, y) for (t, x, y) in pagina2 if str(t).strip()]
    return {"pagina1": pagina1, "pagina2": pagina2, "avisos": avisos, "parar": parar}
