"""
Notificaciones - Agentcall
Envio de correos via Resend API para confirmacion de casos.
"""

import os
import logging
import requests as http_requests
from datetime import datetime
from string import Template

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get(
    "RESEND_FROM", "TusAbogados.com <onboarding@resend.dev>"
)


def _email_configurado():
    """Verifica que Resend API este configurado."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY no configurada.")
        return False
    return True


def enviar_correo(destinatario, asunto, html_body):
    """Envia un correo via Resend API."""
    if not _email_configurado():
        logger.warning(f"[EMAIL DESHABILITADO] A {destinatario}: {asunto}")
        return False

    try:
        logger.info(f"[RESEND] Enviando a {destinatario}...")
        payload = {
            "from": RESEND_FROM,
            "to": [destinatario],
            "subject": asunto,
            "html": html_body,
        }
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        }
        response = http_requests.post(
            "https://api.resend.com/emails",
            json=payload, headers=headers, timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            logger.info(
                f"[RESEND] OK - a {destinatario} (id: {data.get('id', 'N/A')})"
            )
            return True
        else:
            logger.error(
                f"[RESEND] Error {response.status_code}: {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"[RESEND] Error: {type(e).__name__}: {e}")
        return False


def enviar_correo_autorizacion_caso(datos):
    """
    Envía correo confirmando que el usuario autorizó el caso.
    datos: dict con nombre, email, categoria, descripcion_caso
    """
    nombre = datos.get("nombre", "")
    email = datos.get("email", "")
    categoria = datos.get("categoria", "")
    descripcion = datos.get("descripcion_caso", "")

    if not email:
        logger.warning("No se puede enviar correo: email vacío")
        return False

    html = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;'>"
        "<div style='background:linear-gradient(135deg,#1a73e8,#0d47a1);"
        "padding:30px;text-align:center;border-radius:12px 12px 0 0;'>"
        "<h1 style='color:#fff;margin:0;'>TusAbogados.com</h1>"
        "<p style='color:#bbdefb;margin:8px 0 0;'>Confirmación de Caso</p>"
        "</div>"
        "<div style='padding:30px;background:#fff;border:1px solid #eee;'>"
        f"<p>Hola <strong style='color:#1a73e8;'>{nombre}</strong>,</p>"
        "<p>Le confirmamos que ha <strong>autorizado</strong> a TusAbogados.com "
        "para que lleve su caso.</p>"
        "<div style='background:#f8f9fa;padding:15px;border-radius:8px;"
        "margin:15px 0;'>"
        f"<p style='margin:5px 0;'><strong>Categoría:</strong> {categoria}</p>"
        f"<p style='margin:5px 0;'><strong>Descripción:</strong> {descripcion[:200]}</p>"
        f"<p style='margin:5px 0;'><strong>Fecha:</strong> "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>"
        "</div>"
        "<p>Un <strong>abogado especializado</strong> se pondrá en contacto "
        "con usted en las próximas horas para comenzar con su proceso.</p>"
        "<p style='color:#666;font-size:13px;'>"
        "Si tiene alguna duda, comuníquese al 300 667 1674.</p>"
        "</div>"
        "<div style='background:#f8f9fa;padding:15px;text-align:center;"
        "border-radius:0 0 12px 12px;border-top:1px solid #eee;'>"
        "<p style='color:#999;font-size:11px;margin:0;'>"
        f"© {datetime.now().year} TusAbogados.com - Todos los derechos reservados</p>"
        "</div></div>"
    )

    asunto = f"✅ Caso autorizado - TusAbogados.com | {categoria}"
    return enviar_correo(email, asunto, html)


def enviar_correo_seguimiento_rechazo(datos):
    """
    Envía correo de seguimiento cuando el usuario rechazó llevar su caso.
    datos: dict con nombre, email, categoria, descripcion_caso
    """
    nombre = datos.get("nombre", "")
    email = datos.get("email", "")
    categoria = datos.get("categoria", "")
    descripcion = datos.get("descripcion_caso", "")

    if not email:
        logger.warning("No se puede enviar correo de seguimiento: email vacío")
        return False

    html = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;'>"
        "<div style='background:linear-gradient(135deg,#1a73e8,#0d47a1);"
        "padding:30px;text-align:center;border-radius:12px 12px 0 0;'>"
        "<h1 style='color:#fff;margin:0;'>TusAbogados.com</h1>"
        "<p style='color:#bbdefb;margin:8px 0 0;'>Seguimiento de su caso</p>"
        "</div>"
        "<div style='padding:30px;background:#fff;border:1px solid #eee;'>"
        f"<p>Hola <strong style='color:#1a73e8;'>{nombre}</strong>,</p>"
        "<p>Esperamos que se encuentre bien. Queríamos recordarle que en "
        "<strong>TusAbogados.com</strong> contamos con un equipo de abogados "
        "especializados listos para atender su caso.</p>"
        "<div style='background:#fff3cd;padding:15px;border-radius:8px;"
        "border-left:4px solid #ffc107;margin:15px 0;'>"
        "<p style='margin:5px 0;font-weight:bold;'>⚠️ Importante:</p>"
        "<p style='margin:5px 0;'>En materia legal, el tiempo es un factor "
        "determinante. Los plazos legales corren y actuar a tiempo puede "
        "marcar la diferencia en el resultado de su caso.</p>"
        "</div>"
        "<div style='background:#f8f9fa;padding:15px;border-radius:8px;"
        "margin:15px 0;'>"
        f"<p style='margin:5px 0;'><strong>Categoría:</strong> {categoria}</p>"
        f"<p style='margin:5px 0;'><strong>Descripción:</strong> {descripcion[:200]}</p>"
        "</div>"
        "<p>No dude en contactarnos cuando esté listo. Estamos para servirle.</p>"
        "<p style='margin-top:20px;'>"
        f"<a href='https://tusabogados.com' style='background:#1a73e8;color:#fff;"
        "padding:12px 30px;text-decoration:none;border-radius:8px;"
        "font-weight:bold;'>Contactar ahora</a></p>"
        "<p style='color:#666;font-size:13px;margin-top:15px;'>"
        "También puede llamarnos al <strong>300 667 1674</strong></p>"
        "</div>"
        "<div style='background:#f8f9fa;padding:15px;text-align:center;"
        "border-radius:0 0 12px 12px;border-top:1px solid #eee;'>"
        "<p style='color:#999;font-size:11px;margin:0;'>"
        f"© {datetime.now().year} TusAbogados.com - Todos los derechos reservados</p>"
        "</div></div>"
    )

    asunto = f"📌 No olvide su caso - TusAbogados.com | {categoria}"
    return enviar_correo(email, asunto, html)
