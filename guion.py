"""
Guion Conversacional - Agente IA Legal "Claudia Garcia"
Tusabogados.com

Flujo: usuario entra con codigo de acceso de 3 digitos,
se identifica, recibe asesoría y autoriza a TusAbogados.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_COLOMBIA = ZoneInfo("America/Bogota")

PASOS = {
    "saludo_inicial": {
        "id": "saludo_inicial",
        "siguiente": "solicitar_codigo",
        "mensaje": "Buenas {momento_del_dia}, le habla Claudia García, asesora legal de TusAbogados.com. Por favor ingresa el código de tres números que enviamos a tu dirección de correo, el día en que registraste la cita.",
        "validar": "codigo",
        "botones": None,
        "campo": "codigo_acceso",
    },
    "solicitar_codigo": {
        "id": "solicitar_codigo",
        "siguiente": "verificar_codigo",
        "mensaje": None,
        "validar": "codigo",
        "botones": None,
        "campo": "codigo_acceso",
    },
    "verificar_codigo": {
        "id": "verificar_codigo",
        "siguiente": "confirmar_identidad",
        "mensaje": None,
        "validar": None,
        "botones": None,
    },
    "confirmar_identidad": {
        "id": "confirmar_identidad",
        "siguiente": "asesoria_caso",
        "mensaje": "Perfecto, {nombre}. Veo que su caso corresponde a derecho {categoria}. ¿Es correcto?",
        "validar": None,
        "botones": None,
    },
    "asesoria_caso": {
        "id": "asesoria_caso",
        "siguiente": "ofrecer_servicio",
        "mensaje": None,
        "validar": None,
        "botones": None,
    },
    "ofrecer_servicio": {
        "id": "ofrecer_servicio",
        "siguiente": "confirmar_autorizacion",
        "mensaje": "Desea que en TusAbogados.com uno de nuestros especialistas lleve su caso, recuerde que solo si ganamos su caso le cobraremos un 10% del valor total.",
        "validar": None,
        "botones": [
            {"texto": "Sí, llevar mi caso (sin costo inicial)", "valor": "aceptar_caso"},
            {"texto": "Quiero más asesoría antes de decidir", "valor": "rechazar_caso"},
        ],
    },
    "confirmar_autorizacion": {
        "id": "confirmar_autorizacion",
        "siguiente": "despedida",
        "mensaje": None,
        "validar": None,
        "botones": None,
    },
    "despedida": {
        "id": "despedida",
        "siguiente": None,
        "mensaje": "Ha sido un gusto atenderle, {nombre}. Recibirá un correo con la confirmación. ¡Que tenga un excelente día!",
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
    """Retorna la parte variable del saludo."""
    hora = datetime.now(TZ_COLOMBIA).hour
    if 6 <= hora < 12:
        return "días"
    elif 12 <= hora < 18:
        return "tardes"
    else:
        return "noches"


def validar_codigo(respuesta):
    """Valida que el codigo sea de 3 digitos."""
    MENSAJE = (
        "No pude escuchar su código correctamente. "
        "¿Podría repetirlo por favor? Son tres dígitos."
    )
    if not respuesta:
        return False, MENSAJE
    digits = re.sub(r"[^0-9]", "", respuesta).strip()
    if len(digits) != 3:
        return False, MENSAJE
    return True, digits


def validar_nombre(respuesta):
    """Valida el nombre del usuario."""
    MENSAJE = (
        "No pude escuchar su nombre claramente. "
        "¿Podría repetirlo por favor?"
    )
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


def validar_respuesta(paso, respuesta):
    """Valida la respuesta del usuario segun el tipo de campo."""
    tipo = paso.get("validar")
    if tipo is None:
        return True, respuesta
    if tipo == "nombre":
        return validar_nombre(respuesta)
    if tipo == "codigo":
        return validar_codigo(respuesta)
    return True, respuesta


def mensaje_codigo_no_encontrado():
    """Mensaje cuando el código no se encuentra."""
    return (
        "No encontré una cita activa con ese código. "
        "¿Podría verificarlo y repetirlo por favor? "
        "Son tres dígitos."
    )


def mensaje_asesoria_caso(categoria, descripcion):
    """Genera mensaje de asesoría según la categoría."""
    desc_corta = (descripcion or "su situación")[:120]
    mensajes = {
        "laboral": (
            f"Entiendo perfectamente. En derecho laboral, su caso de "
            f"{desc_corta} es algo que manejamos con frecuencia. "
            f"La ley colombiana protege los derechos del trabajador de manera robusta. "
            f"En casos como el suyo, es fundamental que sepa que existen varios recursos legales "
            f"disponibles. Dependiendo de los detalles específicos de su situación, se pueden "
            f"reclamar prestaciones sociales, liquidación laboral, indemnización por despido "
            f"injustificado, y otros derechos consagrados en el Código Sustantivo del Trabajo. "
            f"Le recomiendo reunir todos los documentos relacionados con su vínculo laboral: "
            f"contrato, extractos de cesantías, nóminas, y cualquier comunicación con su empleador. "
            f"Es importante actuar dentro de los plazos legales, ya que muchas acciones laborales "
            f"tienen términos de prescripción. ¿Tiene alguna pregunta sobre esto o desea que le "
            f"profundice en algún aspecto particular de su caso?"
        ),
        "civil": (
            f"Entiendo perfectamente. En derecho civil, su caso de "
            f"{desc_corta} requiere atención especializada. "
            f"El derecho civil colombiano ofrece diversas herramientas para proteger sus intereses. "
            f"Según la naturaleza de su situación, pueden aplicar normas del Código Civil sobre "
            f"contratos, obligaciones, responsabilidad civil, y derechos reales. Es importante "
            f"que sepa que existen plazos legales para tomar acciones, como la prescripción de "
            f"derechos y la caducidad de acciones judiciales. Le recomiendo reunir toda la "
            f"documentación relevante: contratos, comprobantes de pago, comunicaciones escritas, "
            f"y cualquier evidencia que respalde su posición. Cada caso tiene sus particularidades "
            f"y es fundamental analizar los detalles concretos para determinar la mejor estrategia. "
            f"¿Tiene alguna pregunta sobre esto o desea que le explique algún aspecto particular?"
        ),
        "penal": (
            f"Entiendo perfectamente. En derecho penal, su caso de "
            f"{desc_corta} es algo que debemos analizar con cuidado. "
            f"Es importante actuar rápido, ya que en materia penal los tiempos son cruciales. "
            f"La Constitución Nacional y la Ley 906 de 2004 garantizan sus derechos como "
            f"víctima o imputado. En estos casos, es fundamental que sepa que tiene derecho "
            f"a presentar denuncia, a la asistencia jurídica, y a ser tratado con dignidad. "
            f"Le recomiendo preservar todas las pruebas posibles: fotografías, mensajes, "
            f"testimonios, informes médicos, y cualquier elemento que respalde los hechos. "
            f"Los plazos para interponer acciones son muy importantes, y cada día cuenta. "
            f"También es relevante que sepa que existen mecanismos de protección como la "
            f"acción de tutela para situaciones de urgencia. "
            f"Tenemos especialistas penales con amplia experiencia que pueden defender sus derechos. "
            f"¿Tiene alguna pregunta o desea que profundice en algún aspecto?"
        ),
    }
    return mensajes.get(categoria, mensajes.get("civil"))


def mensaje_confirmacion_autorizacion(nombre, categoria):
    """Mensaje al confirmar la autorización."""
    return (
        f"Excelente decisión, {nombre}. He registrado su autorización. "
        f"Un especialista en en derecho {categoria} se encargará "
        f"de su caso. Recibirá un correo con la confirmación. "
        f"En TusAbogados.com trabajamos para usted."
    )


def mensaje_persuasivo_rechazo(nombre, categoria):
    """Mensaje persuasivo cuando el usuario dice NO a llevar el caso."""
    return (
        f"Entiendo perfectamente, {nombre}. Le comento que en materia legal, "
        f"el tiempo es un factor determinante. Muchas situaciones tienen plazos "
        f"legales que corren, y cuanto antes cuente con un especialista de su lado, "
        f"mejores opciones hay de proteger sus derechos e intereses. "
        f"Su caso de derecho {categoria} merece la atención de un especialista "
        f"que conozca cada detalle y pueda defenderle con firmeza. "
        f"Le recomiendo que lo piense con calma. Cuando esté listo, "
        f"puede contactarnos nuevamente al 300 667 1674 y con gusto le atendemos. "
        f"En TusAbogados.com siempre estamos aquí para usted. "
        f"¡Que tenga un excelente día!"
    )
