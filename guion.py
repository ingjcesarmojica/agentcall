"""
Guion Conversacional - Agente IA Legal "Claudia García"
Tusabogados.com

Flujo conversacional para LLAMADAS TELEFONICAS.
El usuario llama, suenan 3 tonos, Claudia contesta, verifica identidad y asesora.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Zona horaria de Colombia (UTC-5)
TZ_COLOMBIA = ZoneInfo("America/Bogota")

PASOS = {
    "saludo_inicial": {
        "id": "saludo_inicial",
        "siguiente": "identificar_llamador",
        "mensaje": "Buenas {momento_del_dia}, le habla Claudia García, asesora legal de TusAbogados.com. Con quién tengo el gusto de hablar.",
        "validar": None,
        "botones": None,
    },
    "identificar_llamador": {
        "id": "identificar_llamador",
        "siguiente": "verificacion_documento",
        "mensaje": "Mucho gusto, {nombre}. Para atender su consulta con confianza, necesito realizar unas breves preguntas de seguridad. ¿Me podría confirmar su número de cédula o documento de identidad.",
        "validar": "nombre",
        "botones": None,
        "campo": "caller_name",
    },
    "verificacion_documento": {
        "id": "verificacion_documento",
        "siguiente": "verificacion_correo",
        "mensaje": "Gracias, {nombre}. Ahora necesito confirmar el correo electrónico registrado en su cuenta. ¿Cuál es su correo.",
        "validar": "documento",
        "botones": None,
        "campo": "caller_documento",
    },
    "verificacion_correo": {
        "id": "verificacion_correo",
        "siguiente": "resultado_verificacion",
        "mensaje": None,
        "validar": "correo",
        "botones": None,
        "campo": "caller_email",
    },
    "resultado_verificacion": {
        "id": "resultado_verificacion",
        "siguiente": "consulta_legal",
        "mensaje": None,
        "validar": None,
        "botones": None,
    },
    "consulta_legal": {
        "id": "consulta_legal",
        "siguiente": "consulta_legal",
        "mensaje": "Entendido, {nombre}. Por favor, descríbame su situación legal y con gusto le oriento sobre los pasos a seguir.",
        "validar": None,
        "botones": None,
    },
    "despedida": {
        "id": "despedida",
        "siguiente": None,
        "mensaje": "Ha sido un gusto atenderle, {nombre}. En TusAbogados.com estamos disponibles 24 horas. Si necesita algo más, no dude en llamarnos. ¡Que tenga un excelente día!",
        "validar": None,
        "botones": None,
    },
}


def obtener_paso(paso_id):
    """Obtiene un paso del guion por su ID."""
    return PASOS.get(paso_id)


def formatear_mensaje(paso, datos):
    """Formatea el mensaje del paso con los datos del usuario."""
    mensaje = paso.get("mensaje", "")
    if mensaje is None:
        return ""
    try:
        return mensaje.format(**datos)
    except KeyError:
        return mensaje


def obtener_momento_del_dia():
    """Retorna la parte variable del saludo para usar con templates.
    Ejemplo: 'tardes' para usar en 'Buenas {momento_del_dia}'.
    """
    hora = datetime.now(TZ_COLOMBIA).hour
    if 6 <= hora < 12:
        return "días"
    elif 12 <= hora < 18:
        return "tardes"
    else:
        return "noches"


def validar_nombre(respuesta):
    """Valida el nombre del usuario."""
    MENSAJE = "No pude escuchar su nombre claramente. ¿Podría repetirlo por favor. Después de la señal, dígame su nombre completo."
    if not respuesta:
        return False, MENSAJE
    respuesta = respuesta.strip()
    respuesta = re.sub(r"[^\wáéíóúñüÁÉÍÓÚÑÜ\s]", "", respuesta).strip()
    if len(respuesta) < 2:
        return False, MENSAJE
    if not re.search(r"[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]", respuesta):
        return False, MENSAJE
    if respuesta.replace(" ", "").isdigit():
        return False, MENSAJE
    nombre_limpio = " ".join(p.capitalize() for p in respuesta.split())
    return True, nombre_limpio


def validar_documento(respuesta):
    """Valida el numero de documento."""
    MENSAJE = "No pude escuchar su número de documento claramente. ¿Podría repetirlo por favor. Después de la señal, dígame los números de su cédula."
    if not respuesta:
        return False, MENSAJE
    digits = re.sub(r"[^0-9\s]", "", respuesta).strip()
    digits = digits.replace(" ", "")
    if not digits:
        return False, MENSAJE
    if len(digits) < 6 or len(digits) > 11:
        return False, MENSAJE
    return True, digits


def validar_correo(respuesta):
    """Valida el correo electronico."""
    MENSAJE = "No pude escuchar su correo electrónico claramente. ¿Podría repetirlo por favor. Después de la señal, dígame su correo completo."
    if not respuesta:
        return False, MENSAJE
    respuesta = respuesta.strip().lower()
    respuesta = respuesta.replace(" arroba ", "@")
    respuesta = respuesta.replace(" punto ", ".")
    respuesta = respuesta.replace(" guion ", "-")
    respuesta = respuesta.replace(" guión ", "-")
    respuesta = respuesta.replace(" subrayado ", "_")
    if "@" not in respuesta or "." not in respuesta:
        return False, MENSAJE
    patron = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron, respuesta):
        return False, MENSAJE
    return True, respuesta


def validar_respuesta(paso, respuesta):
    """Valida la respuesta del usuario segun el tipo de campo."""
    tipo = paso.get("validar")
    if tipo is None:
        return True, respuesta
    if tipo == "nombre":
        return validar_nombre(respuesta)
    if tipo == "correo":
        return validar_correo(respuesta)
    if tipo == "documento":
        return validar_documento(respuesta)
    return True, respuesta
