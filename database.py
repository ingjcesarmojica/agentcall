"""
Módulo Supabase - Base de datos en la nube para TusAbogados.com
Almacena datos de usuarios, casos y citas.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase = None


def get_supabase():
    """Obtiene cliente Supabase (singleton)."""
    global _supabase
    if _supabase is not None:
        return _supabase

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("SUPABASE_URL/SUPABASE_KEY no configuradas - modo sin BD")
        return None

    try:
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase conectado correctamente")
        return _supabase
    except Exception as e:
        logger.error(f"Error conectando Supabase: {e}")
        return None


def guardar_usuario(datos):
    """
    Guarda o actualiza un usuario en la tabla 'usuarios'.
    datos: dict con campos del usuario.
    Retorna (True, id) o (False, error).
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        registro = {
            "nombre": datos.get("nombre", ""),
            "email": datos.get("email", ""),
            "telefono": datos.get("telefono", ""),
            "rol": datos.get("rol", ""),
            "categoria": datos.get("categoria", ""),
            "descripcion_caso": datos.get("descripcion_caso", ""),
            "tiene_pruebas": datos.get("tiene_pruebas", False),
            "paso_actual": datos.get("paso_actual", ""),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = sb.table("usuarios").upsert(registro, on_conflict="email").execute()

        user_id = None
        if hasattr(result, "data") and result.data:
            user_id = result.data[0].get("id")

        logger.info(f"Usuario guardado: {registro['nombre']} ({registro['email']})")
        return True, user_id

    except Exception as e:
        logger.error(f"Error guardando usuario: {e}")
        return False, str(e)


def guardar_cita(datos):
    """
    Guarda una cita en la tabla 'citas'.
    datos: dict con campos de la cita.
    Retorna (True, id) o (False, error).
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        registro = {
            "usuario_email": datos.get("email", ""),
            "usuario_nombre": datos.get("nombre", ""),
            "usuario_telefono": datos.get("telefono", ""),
            "categoria": datos.get("categoria", ""),
            "descripcion_caso": datos.get("descripcion_caso", ""),
            "fecha_cita": datos.get("fecha_cita", ""),
            "hora_cita": datos.get("hora_cita", ""),
            "estado": datos.get("estado", "confirmada"),
            "created_at": datetime.utcnow().isoformat(),
        }

        result = sb.table("citas").insert(registro).execute()

        cita_id = None
        if hasattr(result, "data") and result.data:
            cita_id = result.data[0].get("id")

        logger.info(
            f"Cita guardada: {registro['fecha_cita']} {registro['hora_cita']} - {registro['usuario_nombre']}"
        )
        return True, cita_id

    except Exception as e:
        logger.error(f"Error guardando cita: {e}")
        return False, str(e)


def guardar_conversacion(datos):
    """
    Guarda registro de la conversación en 'conversaciones'.
    datos: dict con campos de la conversación.
    Retorna (True, id) o (False, error).
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        registro = {
            "usuario_email": datos.get("email", ""),
            "usuario_nombre": datos.get("nombre", ""),
            "mensaje_usuario": datos.get("mensaje_usuario", ""),
            "respuesta_agente": datos.get("respuesta_agente", ""),
            "paso": datos.get("paso", ""),
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"guardar_conversacion: registro={registro}")
        result = sb.table("conversaciones").insert(registro).execute()
        logger.info(
            f"guardar_conversacion: result.data={result.data if hasattr(result, 'data') else 'no data attr'}"
        )

        conv_id = None
        if hasattr(result, "data") and result.data:
            conv_id = result.data[0].get("id")

        return True, conv_id

    except Exception as e:
        logger.error(f"Error guardando conversación: {e}")
        return False, str(e)


def guardar_consulta_adicional(datos):
    """
    Guarda una consulta adicional en 'consultas_adicionales'.
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        registro = {
            "usuario_email": datos.get("email", ""),
            "usuario_nombre": datos.get("nombre", ""),
            "consulta": datos.get("consulta", ""),
            "created_at": datetime.utcnow().isoformat(),
        }

        result = sb.table("consultas_adicionales").insert(registro).execute()

        consulta_id = None
        if hasattr(result, "data") and result.data:
            consulta_id = result.data[0].get("id")

        return True, consulta_id

    except Exception as e:
        logger.error(f"Error guardando consulta adicional: {e}")
        return False, str(e)


def obtener_usuario(email):
    """
    Obtiene un usuario por email.
    Retorna dict con datos o None.
    """
    sb = get_supabase()
    if sb is None:
        return None

    try:
        result = sb.table("usuarios").select("*").eq("email", email).execute()
        if hasattr(result, "data") and result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error obteniendo usuario: {e}")
        return None


def obtener_citas_usuario(email):
    """
    Obtiene todas las citas de un usuario por email.
    Retorna lista de dicts.
    """
    sb = get_supabase()
    if sb is None:
        return []

    try:
        result = (
            sb.table("citas")
            .select("*")
            .eq("usuario_email", email)
            .order("created_at", desc=True)
            .execute()
        )
        if hasattr(result, "data"):
            return result.data
        return []
    except Exception as e:
        logger.error(f"Error obteniendo citas: {e}")
        return []


def obtener_usuario_por_telefono(telefono):
    """
    Obtiene un usuario por numero de telefono.
    Retorna dict con datos o None.
    """
    sb = get_supabase()
    if sb is None:
        return None

    try:
        result = sb.table("usuarios").select("*").eq("telefono", telefono).execute()
        if hasattr(result, "data") and result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error obteniendo usuario por telefono: {e}")
        return None


def verificar_identidad_usuario(documento, email):
    """
    Verifica la identidad de un usuario comparando documento y email.
    Retorna dict con datos del usuario o None si no coincide.
    """
    sb = get_supabase()
    if sb is None:
        return None

    try:
        result = sb.table("usuarios").select("*").eq("documento", documento).execute()
        if hasattr(result, "data") and result.data:
            usuario = result.data[0]
            if usuario.get("email", "").lower() == email.lower():
                return usuario
        return None
    except Exception as e:
        logger.error(f"Error verificando identidad: {e}")
        return None

def guardar_llamada(datos):
    """
    Guarda un registro de llamada en la tabla 'llamadas'.
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        registro = {
            "usuario_email": datos.get("email", ""),
            "usuario_nombre": datos.get("nombre", ""),
            "documento": datos.get("documento", ""),
            "duracion_segundos": datos.get("duracion_segundos", 0),
            "paso_final": datos.get("paso_final", ""),
            "estado": datos.get("estado", "completada"),
            "created_at": datetime.utcnow().isoformat(),
        }

        result = sb.table("llamadas").insert(registro).execute()

        llamada_id = None
        if hasattr(result, "data") and result.data:
            llamada_id = result.data[0].get("id")

        logger.info(f"Llamada guardada: {registro['usuario_nombre']} ({registro['duracion_segundos']}s)")
        return True, llamada_id

    except Exception as e:
        logger.error(f"Error guardando llamada: {e}")
        return False, str(e)


def guardar_documento_usuario(email, documento):
    """
    Guarda o actualiza el número de documento de un usuario.
    """
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no disponible"

    try:
        result = sb.table("usuarios").update({
            "documento": documento,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("email", email).execute()
        
        if hasattr(result, "data") and result.data:
            return True, result.data[0].get("id")
        return True, None
    except Exception as e:
        logger.error(f"Error guardando documento: {e}")
        return False, str(e)
        return []
