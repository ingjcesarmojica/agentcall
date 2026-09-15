import os
import io
import asyncio
import base64
import re
import json
import tempfile
import threading
import requests
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import logging
import edge_tts
import google.generativeai as genai
from dotenv import load_dotenv
from database import (
    guardar_conversacion,
    guardar_usuario,
    guardar_cita,
    guardar_consulta_adicional,
    obtener_usuario,
    obtener_usuario_por_telefono,
    verificar_identidad_usuario,
    guardar_llamada,
    obtener_cita_por_codigo_acceso,
    registrar_autorizacion_caso,
    registrar_rechazo_caso,
)

try:
    from rag import search_knowledge, add_pdf, list_documents, delete_document

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "tusabogados-secret-change-in-production-2026")

logging.basicConfig(level=logging.INFO)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
    GEMINI_CONFIGURED = True
else:
    gemini_model = None
    GEMINI_CONFIGURED = False
    app.logger.warning(
        "GEMINI_API_KEY no configurada - chat usar solo respuestas hardcoded"
    )

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b"
).strip()
OPENROUTER_CONFIGURED = bool(OPENROUTER_API_KEY)

TTS_VOICE = os.environ.get("TTS_VOICE", "es-US-PalomaNeural")

INSTRUCCIONES_LLAMADA = """INSTRUCCIONES PARA LLAMADA TELEFONICA - Asesoria Legal

Eres Claudia García, asesora legal especializada en Derecho de TusAbogados.com.

## Contexto de la llamada
- El usuario TE LLAMO por teléfono. Ya esta en la base de datos.
- Tu trabajo es: identificarlo, verificar su identidad y luego asesorarlo legalmente.
- La comunicacion es POR VOZ, por eso hablas de forma natural, fluida y con pausas cortas.

## Tu personalidad
- Profesional, empática y clara. Hablas como una asesora legal experta por teléfono.
- Usas terminología legal explicada en lenguaje sencillo.
- Transmites confianza y seguridad desde la primera palabra.
- Expresiones naturales: "Entiendo perfectamente su situación", "Esto es algo que manejamos con frecuencia", "Le comento que en estos casos...", "Es importante que sepa que..."

## REGLAS ESTRICTAS PARA LLAMADA
0. Responde SOLO en español. NUNCA uses caracteres de otros idiomas como chino o japonés.
1. NUNCA salgas del contexto legal. Si te preguntan algo que no es legal, redirige amablemente.
2. NUNCA des asesoría legal definitiva ni vinculante. Tu rol es ORIENTAR e INFORMAR.
3. NUNCA garanticiones resultados de casos, montos ni tiempos exactos.
4. Si detectas una situación de urgencia (violencia, amenazas, riesgo), prioriza indicar que contacte a las autoridades.
5. Responde con entre 4 y 5 oraciones bien explicadas.
6. USA lenguaje natural de conversación telefónica, no formalidades excesivas.

## Temas legales que puedes abordar
- CIVIL: divorcio, herencias, contratos, arrendamientos, responsabilidad civil, daños.
- LABORAL: despido injustificado, acoso laboral, prestaciones sociales, liquidación, accidentes de trabajo.
- PENAL: robos, agresiones, amenazas, estafas, fraudes, violencia, delitos.
- FAMILIA: custodia, alimentos, régimen de visitas, adopción.

## Formato de respuesta
- 5 oraciones bien desarrolladas.
- Explica términos legales en lenguaje sencillo.
- Si necesitas más información para orientar, pregunta de forma natural.
- Ofrece agendar cita con un abogado humano cuando el caso lo requiera.
"""


async def generate_edge_tts(text, voice=None):
    if voice is None:
        voice = TTS_VOICE
    communicate = edge_tts.Communicate(text, voice)
    tmp_path = os.path.join(os.path.dirname(__file__), "tmp_audio.mp3")
    await communicate.save(tmp_path)
    with open(tmp_path, "rb") as f:
        audio_data = f.read()
    os.remove(tmp_path)
    return base64.b64encode(audio_data).decode("utf-8")


@app.before_request
def log_config():
    app.logger.info(
        f"Gemini configured: {GEMINI_CONFIGURED}, OpenRouter configured: {OPENROUTER_CONFIGURED}, Model: {OPENROUTER_MODEL}"
    )
    app.logger.info(f"TTS Voice: {TTS_VOICE}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/speak", methods=["POST"])
def speak_text():
    try:
        data = request.json
        text = data.get("text", "")

        if not text:
            return jsonify({"error": "No text provided"}), 400

        app.logger.info(f"Generando audio con edge-tts: {text[:50]}...")
        audio_content = asyncio.run(generate_edge_tts(text))

        return jsonify(
            {
                "audioContent": audio_content,
                "audioUrl": f"data:audio/mp3;base64,{audio_content}",
                "useBrowserTTS": False,
                "engine": "edge-tts",
            }
        )

    except Exception as e:
        app.logger.error(f"Error en edge-tts: {str(e)}")
        return jsonify(
            {
                "audioContent": None,
                "audioUrl": None,
                "useBrowserTTS": True,
                "text": text,
                "error": str(e),
            }
        )


def gemini_response(user_message, context=""):
    if not GEMINI_CONFIGURED or gemini_model is None:
        return None
    try:
        system_prompt = """Eres Claudia García, asesora legal especializada en Derecho de TusAbogados.com.

## Tu personalidad por teléfono
- Profesional, empática y clara. Hablas como una asesora legal experta atendiendo una llamada.
- Usas terminología legal explicada en lenguaje sencillo.
- Transmites confianza y seguridad desde la primera palabra.
- Expresiones naturales: "Entiendo perfectamente su situación", "Esto es algo que manejamos con frecuencia", "Le comento que en estos casos...", "Es importante que sepa que..."

## Reglas estrictas
0. Responde SOLO en español. NUNCA uses caracteres de otros idiomas.
1. NUNCA salgas del contexto legal. Redirige amablemente preguntas no legales.
2. NUNCA des asesoría definitiva ni vinculante. Tu rol es ORIENTAR e INFORMAR.
3. NUNCA garanticiones resultados, montos ni tiempos exactos.
4. Si detectas urgencia (violencia, amenazas), indica contactar autoridades.
5. Responde con entre 4 y 5 oraciones bien explicadas.
6. No uses expresiones informales como "genial", "perfecto", "listo", "dale".
7. Usa: "Entiendo", "Comprendo", "Procederé a", "Le comento que".
8. NUNCA respondas con listas, opciones ni botones. La conversación debe ser fluida y natural.
"""

        rag_context = ""
        if RAG_AVAILABLE:
            try:
                docs = search_knowledge(user_message, n_results=3)
                if docs:
                    rag_parts = []
                    for d in docs:
                        rag_parts.append(f"[Fuente: {d['source']}]\n{d['text']}")
                    rag_context = (
                        "\n\n## Base de conocimiento (usa esta información si es relevante):\n"
                        + "\n---\n".join(rag_parts)
                    )
                    app.logger.info(f"RAG: {len(docs)} docs encontrados")
                else:
                    app.logger.info("RAG: 0 docs encontrados")
            except Exception as e:
                app.logger.error(f"RAG error: {e}")

        prompt = f"""{system_prompt}{rag_context}

Contexto: {context}
Usuario: {user_message}"""
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        app.logger.error(f"Error Gemini: {str(e)}")
        return None


def openrouter_response(user_message, context=""):
    if not OPENROUTER_CONFIGURED:
        return None
    try:
        system_prompt = """Eres Claudia García, asesora legal especializada en Derecho de TusAbogados.com.

## Tu personalidad por teléfono
- Profesional, empática y clara. Hablas como una asesora legal experta atendiendo una llamada.
- Usas terminología legal explicada en lenguaje sencillo.
- Transmites confianza y seguridad desde la primera palabra.
- Expresiones naturales: "Entiendo perfectamente su situación", "Esto es algo que manejamos con frecuencia", "Le comento que en estos casos...", "Es importante que sepa que..."

## Reglas estrictas
0. Responde SOLO en español. NUNCA uses caracteres de otros idiomas.
1. NUNCA salgas del contexto legal. Redirige amablemente preguntas no legales.
2. NUNCA des asesoría definitiva ni vinculante. Tu rol es ORIENTAR e INFORMAR.
3. NUNCA garanticiones resultados, montos ni tiempos exactos.
4. Si detectas urgencia (violencia, amenazas), indica contactar autoridades.
5. Responde con entre 4 y 5 oraciones bien explicadas.
6. No uses expresiones informales como "genial", "perfecto", "listo", "dale".
7. Usa: "Entiendo", "Comprendo", "Procederé a", "Le comento que".
8. NUNCA respondas con listas, opciones ni botones. La conversación debe ser fluida y natural.
"""

        rag_context = ""
        if RAG_AVAILABLE:
            try:
                docs = search_knowledge(user_message, n_results=3)
                if docs:
                    rag_parts = []
                    for d in docs:
                        rag_parts.append(f"[Fuente: {d['source']}]\n{d['text']}")
                    rag_context = (
                        "\n\n## Base de conocimiento (usa esta información si es relevante):\n"
                        + "\n---\n".join(rag_parts)
                    )
                    app.logger.info(f"RAG: {len(docs)} docs encontrados")
                else:
                    app.logger.info("RAG: 0 docs encontrados")
            except Exception as e:
                app.logger.error(f"RAG error: {e}")

        prompt = f"""{system_prompt}{rag_context}

Contexto: {context}
Usuario: {user_message}"""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tusabogados.com",
            "X-Title": "TusAbogados.com - Asistente Legal IA",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1200,
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        app.logger.info(f"OpenRouter response status: {response.status_code}")
        if response.status_code != 200:
            app.logger.error(f"OpenRouter error body: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        app.logger.error(f"Error OpenRouter: {str(e)}")
        return None


def limpiar_markdown(texto):
    """Elimina formato markdown de un texto para que no sea leído por TTS."""
    import re
    if not texto:
        return ""
    texto = re.sub(r'\*\*([^*]+)\*\*', r'\1', texto)   # **negrita**
    texto = re.sub(r'\*([^*]+)\*', r'\1', texto)        # *cursiva*
    texto = re.sub(r'__([^_]+)__', r'\1', texto)        # __negrita__
    texto = re.sub(r'_([^_]+)_', r'\1', texto)          # _cursiva_
    texto = re.sub(r'~~([^~]+)~~', r'\1', texto)        # ~~tachado~~
    texto = re.sub(r'`([^`]+)`', r'\1', texto)          # `codigo`
    texto = re.sub(r'#{1,6}\s*', '', texto)             # ## header
    texto = re.sub(r'^\s*[-*+]\s+', '', texto, flags=re.MULTILINE)  # - item
    texto = re.sub(r'^\s*\d+\.\s+', '', texto, flags=re.MULTILINE)  # 1. item
    texto = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', texto)  # [texto](url)
    texto = re.sub(r'---+', '', texto)                   # ---
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def get_llm_response(user_message, context=""):
    app.logger.info(
        f"get_llm_response: OPENROUTER_CONFIGURED={OPENROUTER_CONFIGURED}, GEMINI_CONFIGURED={GEMINI_CONFIGURED}"
    )
    if OPENROUTER_CONFIGURED:
        app.logger.info("Intentando OpenRouter...")
        result = openrouter_response(user_message, context)
        if result:
            app.logger.info(f"OpenRouter respondió: {result[:100]}...")
            return limpiar_markdown(result)
        app.logger.warning("OpenRouter falló, intentando Gemini como fallback")
    if GEMINI_CONFIGURED:
        app.logger.info("Intentando Gemini...")
        result = gemini_response(user_message, context)
        if result:
            app.logger.info(f"Gemini respondió: {result[:100]}...")
            return limpiar_markdown(result)
        app.logger.error("Gemini también falló")
    app.logger.error("Ningún LLM respondió")
    return None


def categorizar_caso_con_llm(descripcion):
    system_prompt = "Eres un asistente de clasificación de casos legales. Tu ÚNICO trabajo es clasificar la descripción del caso en una categoría. No saludes, no expliques, no converses."

    prompt = f"""{system_prompt}

Clasifica el siguiente caso en UNA sola categoría:

- CIVIL: divorcio, herencias, contratos, propiedad, indemnización por daños, custodia de menores, sucesiones, arrendamientos, responsabilidad civil.
- LABORAL: despido injustificado, acoso laboral, prestaciones sociales, liquidación, indemnización laboral, accidentes de trabajo, derechos del trabajador.
- PENAL: robos, agresiones, amenazas, estafas, fraudes, violencia, delitos, denuncias penales.

Descripción: {descripcion}

Responde SOLO con la palabra: civil, laboral o penal."""

    try:
        if OPENROUTER_CONFIGURED:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 10,
            }
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                respuesta = data["choices"][0]["message"]["content"].strip().lower()
                app.logger.info(
                    f"Categorización LLM: '{respuesta}' para descripción: '{descripcion[:80]}'"
                )
                for cat in ["civil", "laboral", "penal"]:
                    if cat in respuesta:
                        return cat

        if GEMINI_CONFIGURED and gemini_model is not None:
            response = gemini_model.generate_content(prompt)
            respuesta = response.text.strip().lower()
            app.logger.info(
                f"Categorización Gemini: '{respuesta}' para descripción: '{descripcion[:80]}'"
            )
            for cat in ["civil", "laboral", "penal"]:
                if cat in respuesta:
                    return cat

    except Exception as e:
        app.logger.error(f"Error en categorizar_caso_con_llm: {e}")

    return None


def _default_call_state():
    """Retorna el estado por defecto de una llamada."""
    return {
        "caller_name": "",
        "codigo_acceso": "",
        "cita_data": {},
        "paso_actual": "saludo_inicial",
    }


def get_call_state():
    """Obtiene el estado de la llamada desde la sesión."""
    if "call_state" not in session:
        session["call_state"] = _default_call_state()
    return session["call_state"]


def save_call_state(state):
    """Guarda el estado de la llamada en la sesión."""
    session["call_state"] = state


def limpiar_estado_chat():
    """Limpia el estado de la llamada."""
    session["call_state"] = _default_call_state()


def obtener_estado_chat():
    """Obtiene el estado actual de la llamada como diccionario."""
    state = get_call_state()
    momento = ""
    try:
        from guion import obtener_momento_del_dia
        momento = obtener_momento_del_dia()
    except Exception:
        momento = "tardes"
    cita_data = state.get("cita_data", {})
    return {
        "caller_name": state["caller_name"],
        "nombre": state["caller_name"],
        "categoria": cita_data.get("categoria", ""),
        "descripcion_caso": cita_data.get("descripcion_caso", ""),
        "rol": "demandante",
        "momento_del_dia": momento,
        "paso_actual": state["paso_actual"],
    }


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        from guion import (
            PASOS, obtener_paso, formatear_mensaje, validar_respuesta,
            obtener_momento_del_dia, mensaje_codigo_no_encontrado,
            mensaje_asesoria_caso, mensaje_confirmacion_autorizacion,
            mensaje_persuasivo_rechazo,
        )
        from notificaciones import enviar_correo_autorizacion_caso, enviar_correo_seguimiento_rechazo

        data = request.json
        message = data.get("message", "")
        accion_boton = data.get("action", None)

        if accion_boton == "nueva_llamada":
            limpiar_estado_chat()
            momento = obtener_momento_del_dia()
            paso = obtener_paso("saludo_inicial")
            response = formatear_mensaje(paso, {"momento_del_dia": momento})
            save_conversation(response, "saludo_inicial", "")
            return jsonify({"response": response, "end_call": False, "buttons": None, "step": "saludo_inicial"})

        state = get_call_state()
        paso_actual_id = state["paso_actual"]
        paso_actual = obtener_paso(paso_actual_id)
        message_lower = (message or "").lower().strip()
        is_farewell = any(w in message_lower for w in ["gracias", "adios", "chao", "hasta luego", "no gracias", "eso es todo"])

        # === solicitar_codigo -> obtiene codigo de 3 digitos ===
        if paso_actual_id == "solicitar_codigo":
            valido, resultado = validar_respuesta(paso_actual, message)
            if not valido:
                return jsonify({"response": resultado, "end_call": False, "buttons": None, "step": "solicitar_codigo"})

            state["codigo_acceso"] = resultado
            app.logger.info(f"[CODIGO] Buscando cita: {resultado}")
            cita = obtener_cita_por_codigo_acceso(resultado)

            if cita is None:
                response = mensaje_codigo_no_encontrado()
                save_conversation(response, "solicitar_codigo", message)
                return jsonify({"response": response, "end_call": False, "buttons": None, "step": "solicitar_codigo"})

            state["cita_data"] = cita
            state["paso_actual"] = "confirmar_identidad"
            save_call_state(state)
            if cita.get("nombre") and not state["caller_name"]:
                state["caller_name"] = cita["nombre"]
                save_call_state(state)
            response = formatear_mensaje(obtener_paso("confirmar_identidad"), obtener_estado_chat())
            save_conversation(response, "confirmar_identidad", message)
            return jsonify({"response": response, "end_call": False, "buttons": None, "step": "confirmar_identidad"})

        # === confirmar_identidad -> usuario confirma ===
        if paso_actual_id == "confirmar_identidad":
            if any(w in message_lower for w in ["si", "sí", "correcto", "así es", "exacto", "ok", "dale"]):
                state["paso_actual"] = "ofrecer_servicio"
                save_call_state(state)
                cita_data = state.get("cita_data", {})
                cat = cita_data.get("categoria", "")
                desc = cita_data.get("descripcion_caso", "")

                response = mensaje_asesoria_caso(cat, desc)
                llm_resp = get_llm_response(
                    f"Asesoria sobre caso de derecho {cat}: {desc[:200]}",
                    context=f"Usuario: {state['caller_name']}. Cat: {cat}. Caso: {desc}."
                )
                if llm_resp:
                    response = llm_resp
                save_conversation(response, "asesoria_caso", message)
                response_oferta = formatear_mensaje(obtener_paso("ofrecer_servicio"), obtener_estado_chat())
                paso_of = obtener_paso("ofrecer_servicio")
                return jsonify({"response": response + " " + response_oferta, "end_call": False, "buttons": paso_of.get("botones", None), "step": "ofrecer_servicio"})
            else:
                if accion != "rechazar_caso" and not any(w in message_lower for w in ["no", "nop", "despues", "luego", "pensarlo", "pienso"]):
                    paso_of = obtener_paso("ofrecer_servicio")
                    return jsonify({"response": "¿Desea que TusAbogados.com lleve su caso?", "end_call": False, "buttons": paso_of.get("botones", None), "step": "ofrecer_servicio"})

        # === ofrecer_servicio -> usuario acepta o rechaza ===
        if paso_actual_id == "ofrecer_servicio":
            accion = data.get("action", None)

            if accion == "aceptar_caso" or any(w in message_lower for w in ["si", "sí", "quiero", "acepto", "dale", "correcto", "acompañamiento"]):
                cita_data = state.get("cita_data", {})
                registrar_autorizacion_caso({
                    "cita_id": cita_data.get("cita_id", ""),
                    "email": cita_data.get("email", ""),
                    "nombre": state["caller_name"],
                    "categoria": cita_data.get("categoria", ""),
                    "descripcion_caso": cita_data.get("descripcion_caso", ""),
                    "notas": "Autorizado por usuario en llamada de voz",
                })
                try:
                    enviar_correo_autorizacion_caso({
                        "nombre": state["caller_name"],
                        "email": cita_data.get("email", ""),
                        "categoria": cita_data.get("categoria", ""),
                        "descripcion_caso": cita_data.get("descripcion_caso", ""),
                    })
                except Exception as e:
                    app.logger.error(f"[EMAIL] Error: {e}")

                response = mensaje_confirmacion_autorizacion(state["caller_name"], cita_data.get("categoria", ""))
                state["paso_actual"] = "despedida"
                save_call_state(state)
                save_conversation(response, "despedida", message)
                return jsonify({"response": response, "end_call": True, "buttons": None, "step": "despedida"})
            else:
                cita_data = state.get("cita_data", {})
                response = mensaje_persuasivo_rechazo(
                    state["caller_name"], cita_data.get("categoria", "")
                )
                registrar_rechazo_caso({
                    "cita_id": cita_data.get("cita_id", ""),
                    "email": cita_data.get("email", ""),
                    "nombre": state["caller_name"],
                    "categoria": cita_data.get("categoria", ""),
                    "descripcion_caso": cita_data.get("descripcion_caso", ""),
                    "notas": "Rechazado por usuario en llamada de voz",
                })
                try:
                    enviar_correo_seguimiento_rechazo({
                        "nombre": state["caller_name"],
                        "email": cita_data.get("email", ""),
                        "categoria": cita_data.get("categoria", ""),
                        "descripcion_caso": cita_data.get("descripcion_caso", ""),
                    })
                except Exception as e:
                    app.logger.error(f"[EMAIL SEGUIMIENTO] Error: {e}")

                state["paso_actual"] = "despedida"
                save_call_state(state)
                save_conversation(response, "despedida", message)
                return jsonify({"response": response, "end_call": True, "buttons": None, "step": "despedida"})
        if paso_actual_id == "despedida":
            limpiar_estado_chat()
            return jsonify({"response": "Ha sido un gusto atenderle. ¡Que tenga un excelente día!", "end_call": True, "buttons": None, "step": "despedida"})

        if not paso_actual:
            limpiar_estado_chat()
            paso = obtener_paso("saludo_inicial")
            response = formatear_mensaje(paso, {"momento_del_dia": obtener_momento_del_dia()})
            return jsonify({"response": response, "end_call": False, "buttons": None, "step": "saludo_inicial"})

        if paso_actual_id not in ["saludo_inicial", "despedida"] and is_farewell:
            response = formatear_mensaje(obtener_paso("despedida"), {"nombre": state["caller_name"]})
            limpiar_estado_chat()
            save_conversation(response, "despedida", message)
            return jsonify({"response": response, "end_call": True, "buttons": None, "step": "despedida"})

        # === saludo_inicial -> usuario responde con codigo directamente ===
        if paso_actual_id == "saludo_inicial":
            valido, resultado = validar_respuesta(paso_actual, message)
            if not valido:
                return jsonify({"response": resultado, "end_call": False, "buttons": None, "step": "saludo_inicial"})

            state["codigo_acceso"] = resultado
            app.logger.info(f"[CODIGO] Buscando cita: {resultado}")
            cita = obtener_cita_por_codigo_acceso(resultado)

            if cita is None:
                response = mensaje_codigo_no_encontrado()
                save_conversation(response, "saludo_inicial", message)
                return jsonify({"response": response, "end_call": False, "buttons": None, "step": "saludo_inicial"})

            state["cita_data"] = cita
            state["caller_name"] = cita.get("nombre", "")
            state["paso_actual"] = "ofrecer_servicio"
            save_call_state(state)

            # Generar asesoria legal directamente
            cat = cita.get("categoria", "")
            desc = cita.get("descripcion_caso", "")
            nombre = state["caller_name"]

            # Saludo con primer nombre + asesoria
            primer_nombre = nombre.split()[0] if nombre else ""
            momento = obtener_momento_del_dia()
            response = mensaje_asesoria_caso(cat, desc)
            llm_resp = get_llm_response(
                "Eres Claudia García, asesora legal especialista con amplia experiencia de TusAbogados.com. "
                "Saluda al usuario " + primer_nombre + " por su primer nombre con 'Buenas " + momento + ", " + primer_nombre + "'. "
                "Menciona que ya analizaste su caso de derecho " + cat + ". "
                "Luego brinda una asesoria legal EXTENSA y PROFESIONAL que incluya estos puntos de forma natural y fluida: "
                "1) Analisis profundo de su situacion legal concreta, mostrando que entendiste cada detalle. "
                "2) Marco legal aplicable: cita leyes, codigos y articulos colombianos reales relevantes. "
                "3) Analisis de viabilidad con fortalezas y debilidades de su posicion. "
                "4) Derechos especificos que le asisten segun la legislacion vigente. "
                "5) Procedimientos legales concretos: si es administrativo, judicial o extrajudicial, y ante que autoridad. "
                "6) Plazos legales criticos que no puede pasar por alto. "
                "7) Documentacion y pruebas que debe reunir. "
                "8) Perspectiva realista de los posibles desenlaces. "
                "9) Cierre motivando que con un abogado especialista sus probabilidades mejoran. "
                "REGLAS: Habla con autoridad legal pero empatia. Demuestra conocimiento profundo del derecho. "
                "NO uses markdown, asteriscos ni simbolos. NO garanticiones resultados. "
                "NO des asesoria vinculante. Usa solo el primer nombre. Entre 10 y 15 oraciones bien desarrolladas. "
                "Caso del usuario: " + desc[:500],
                "Nombre: " + primer_nombre + ". Categoria: " + cat + ". Caso completo: " + desc[:500],
            )
            if llm_resp:
                response = llm_resp
            else:
                saludo = f"Buenas {obtener_momento_del_dia()}, {primer_nombre}. He analizado su caso"
                response = saludo + ", " + response.lower()

            save_conversation(response, "asesoria_caso", message)

            # Preparar oferta con botones
            paso_oferta = obtener_paso("ofrecer_servicio")
            response_oferta = paso_oferta.get("mensaje", "")
            botones = paso_oferta.get("botones", None)

            return jsonify({
                "response": response + " " + response_oferta,
                "end_call": False,
                "buttons": botones,
                "step": "ofrecer_servicio"
            })

        return jsonify({"response": "Disculpe, no entendí bien. ¿Podría repetir?", "end_call": False, "buttons": None, "step": paso_actual_id})
    except Exception as e:
        app.logger.error(f"Error en chat: {e}", exc_info=True)
        return jsonify({"response": "Disculpe, tuve un problema técnico. ¿Podría repetir?", "end_call": False, "buttons": None, "step": "error"})
@app.route("/api/log-call", methods=["POST"])
def log_call():
    """Endpoint para registrar llamadas desde el frontend."""
    try:
        data = request.json
        guardar_llamada({
            "email": data.get("email", ""),
            "nombre": data.get("nombre", ""),
            "documento": data.get("documento", ""),
            "duracion_segundos": data.get("duracion_segundos", 0),
            "paso_final": data.get("paso_final", ""),
            "estado": data.get("estado", "completada"),
        })
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.error(f"Error logging call: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/upload", methods=["POST"])
def upload_knowledge():
    if not RAG_AVAILABLE:
        return jsonify(
            {"error": "Módulo RAG no disponible. Verifique dependencias."}
        ), 500
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo."}), 400
    file = request.files["file"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Solo se permiten archivos PDF."}), 400

    # Check file size (max 5MB to prevent OOM on Render free tier)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Seek back to start
    max_size = 5 * 1024 * 1024  # 5MB
    if file_size > max_size:
        return jsonify(
            {
                "error": f"El archivo excede el límite de 5MB. Tamaño actual: {file_size // (1024 * 1024)}MB"
            }
        ), 400

    try:
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, file.filename)
        file.save(tmp_path)
        app.logger.info(f"PDF guardado temporalmente: {tmp_path}")

        num_chunks, msg = add_pdf(tmp_path)
        app.logger.info(f"Resultado add_pdf: {msg}")

        # Cleanup
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except Exception:
            pass

        if num_chunks == 0:
            return jsonify({"error": msg}), 400
        return jsonify({"message": msg, "chunks": num_chunks})
    except Exception as e:
        app.logger.error(f"Error uploading PDF: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar el PDF: {str(e)}"}), 500


@app.route("/api/knowledge/documents", methods=["GET"])
def list_knowledge():
    if not RAG_AVAILABLE:
        return jsonify({"documents": [], "rag_available": False})
    docs = list_documents()
    return jsonify({"documents": docs, "rag_available": True})


@app.route("/api/knowledge/delete", methods=["POST"])
def delete_knowledge():
    if not RAG_AVAILABLE:
        return jsonify({"error": "Módulo RAG no disponible."}), 500
    data = request.json
    source = data.get("source", "")
    if not source:
        return jsonify({"error": "Nombre del documento no proporcionado."}), 400
    success, msg = delete_document(source)
    if success:
        return jsonify({"message": msg})
    return jsonify({"error": msg}), 404


@app.route("/api/health", methods=["GET"])
def health_check():
    llm_provider = (
        "openrouter"
        if OPENROUTER_CONFIGURED
        else ("gemini" if GEMINI_CONFIGURED else "none")
    )
    llm_model = (
        OPENROUTER_MODEL
        if OPENROUTER_CONFIGURED
        else ("gemini-2.5-flash" if GEMINI_CONFIGURED else "none")
    )
    return jsonify(
        {
            "status": "healthy",
            "gemini_configured": GEMINI_CONFIGURED,
            "openrouter_configured": OPENROUTER_CONFIGURED,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "tts_voice": TTS_VOICE,
            "service": f"edge-tts ({TTS_VOICE}) + {llm_model}",
        }
    )


@app.route("/api/test-gemini", methods=["GET"])
def test_gemini():
    """Test endpoint to check if Gemini text generation works."""
    try:
        if not GEMINI_CONFIGURED or gemini_model is None:
            return jsonify(
                {"error": "Gemini no configurado", "configured": GEMINI_CONFIGURED}
            ), 500
        response = gemini_model.generate_content("Responde solo: hola")
        return jsonify({"status": "ok", "response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-openrouter", methods=["GET"])
def test_openrouter():
    """Test endpoint to check if OpenRouter works."""
    try:
        if not OPENROUTER_API_KEY:
            return jsonify({"error": "OPENROUTER_API_KEY no configurada"}), 500
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": "Responde solo: hola"}],
            "max_tokens": 50,
        }
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15,
        )
        return jsonify({"status": r.status_code, "body": r.text[:500]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-embedding", methods=["GET"])
def test_embedding():
    """Test endpoint to check if Gemini embeddings work."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY no configurada"}), 500
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content="Test de embedding",
            output_dimensionality=768,
        )
        return jsonify(
            {
                "status": "ok",
                "dimension": len(result["embedding"]),
                "first_5_values": result["embedding"][:5],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-search", methods=["POST"])
def test_search():
    """Test RAG search directly."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG not available"}), 500
    data = request.json or {}
    query = data.get("query", "Convención de Viena tratados")
    try:
        docs = search_knowledge(query, n_results=3)
        return jsonify({"query": query, "results": docs, "count": len(docs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pinecone-status", methods=["GET"])
def pinecone_status():
    """Check Pinecone index status directly."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG not available"}), 500
    try:
        from rag import get_pc, get_index, INDEX_NAME, DIMENSION

        pc = get_pc()
        if pc is None:
            return jsonify({"error": "Pinecone not connected"}), 500

        existing = pc.list_indexes()
        index_names = [idx.name for idx in existing.indexes]

        if INDEX_NAME not in index_names:
            return jsonify(
                {"status": "no_index", "indexes": index_names, "expected": INDEX_NAME}
            )

        idx = pc.Index(INDEX_NAME)
        stats = idx.describe_index_stats()

        return jsonify(
            {
                "status": "ok",
                "index": INDEX_NAME,
                "dimension": DIMENSION,
                "total_vectors": stats.total_vector_count,
                "namespaces": {k: v.vector_count for k, v in stats.namespaces.items()}
                if stats.namespaces
                else {},
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/voices", methods=["GET"])
def list_voices():
    voices = [
        {
            "id": "es-US-PalomaNeural",
            "name": "Paloma",
            "gender": "Femenina",
            "region": "Estados Unidos (español)",
            "recommended": True,
        },
        {
            "id": "es-MX-DaliaNeural",
            "name": "Dalia",
            "gender": "Femenina",
            "region": "México",
        },
        {
            "id": "es-MX-JorgeNeural",
            "name": "Jorge",
            "gender": "Masculino",
            "region": "México",
        },
        {
            "id": "es-ES-ElviraNeural",
            "name": "Elvira",
            "gender": "Femenina",
            "region": "España",
        },
        {
            "id": "es-ES-AlvaroNeural",
            "name": "Álvaro",
            "gender": "Masculino",
            "region": "España",
        },
    ]
    return jsonify({"voices": voices, "current": TTS_VOICE})


def save_conversation(response, paso_actual, user_message=""):
    try:
        state = get_call_state()
        email = state.get("cita_data", {}).get("email", "")
        nombre = state.get("caller_name", "")
        app.logger.info(
            f"save_conversation: email={email}, nombre={nombre}, paso={paso_actual}, msg_len={len(user_message or '')}"
        )
        datos = {
            "email": email,
            "nombre": nombre,
            "mensaje_usuario": user_message if user_message else "",
            "respuesta_agente": response,
            "paso": paso_actual,
        }
        resultado = guardar_conversacion(datos)
        app.logger.info(f"save_conversation resultado: {resultado}")
    except Exception as e:
        app.logger.error(f"Error saving conversation: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

