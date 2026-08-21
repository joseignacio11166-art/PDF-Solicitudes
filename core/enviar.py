"""
core/enviar.py — Envía una factura por correo, con el PDF adjunto, a través de n8n.

La app NO envía el correo ella misma (no tiene contraseña de ningún buzón): llama a un
**webhook de n8n** y n8n es quien manda el correo con la cuenta que tenga conectada.
Así la contraseña nunca sale del sitio donde vive.

Lo que se le manda a n8n (JSON):
    {destinatario, asunto, cuerpo, archivo, pdf_base64}

El flujo de n8n listo para importar está en `n8n/enviar_factura.json`.
La URL del webhook se configura desde la propia app (⚙️ Envío por correo).
"""
from __future__ import annotations

import base64

TIEMPO_MAXIMO = 45  # segundos


def enviar_factura(webhook: str, destinatario: str, asunto: str, cuerpo: str,
                   archivo: str, pdf: bytes) -> tuple[bool, str]:
    """Manda la factura. Devuelve (ok, mensaje para enseñar a la persona)."""
    webhook = (webhook or "").strip()
    if not webhook:
        return False, "Falta la dirección del webhook de n8n (⚙️ Envío por correo)."
    if not destinatario.strip():
        return False, "Falta el correo del destinatario."
    if not pdf:
        return False, "No hay PDF que adjuntar."

    import requests
    carga = {
        "destinatario": destinatario.strip(),
        "asunto": asunto,
        "cuerpo": cuerpo,
        "archivo": archivo or "factura.pdf",
        "pdf_base64": base64.b64encode(pdf).decode(),
    }
    try:
        r = requests.post(webhook, json=carga, timeout=TIEMPO_MAXIMO)
    except Exception as e:  # noqa: BLE001
        return False, f"No pude contactar con n8n: {e}"

    if r.status_code >= 400:
        detalle = (r.text or "")[:300]
        if r.status_code == 404:
            return False, ("n8n responde 404: el flujo no está activo o la dirección no es esa. "
                           "Comprueba que el workflow esté en **Active** y que hayas copiado la "
                           "URL de **Production**, no la de Test.")
        return False, f"n8n devolvió un error {r.status_code}. {detalle}"
    return True, "Correo enviado."


def texto_correo(cliente: str, numero: str, concepto: str, total_txt: str) -> tuple[str, str]:
    """Asunto y cuerpo por defecto del correo de una factura emitida."""
    asunto = f"Factura {numero} · Pagés Seguros"
    cuerpo = (
        f"Buenos días:\n\n"
        f"Adjunto la factura {numero}"
        + (f" correspondiente a {concepto.lower()}" if concepto else "")
        + f", por importe de {total_txt}.\n\n"
        "Quedamos a su disposición para cualquier aclaración.\n\n"
        "Un saludo,\n"
        "Pagés Seguros\n"
        "Calle Hermosilla 80, 2ª A · 28001 Madrid\n"
        "Tel: +34 910 574 872 · www.pagesseguros.com"
    )
    return asunto, cuerpo
