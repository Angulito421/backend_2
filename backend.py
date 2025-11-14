# backend.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import json


app = Flask(__name__)
# Permitir CORS desde tu servidor estático
# ###########################################################################################################################
# CORS(app, origins=["http://127.0.0.1:8000", "http://localhost:8000"], supports_credentials=True)
# ###########################################################################################################################
#CORS(app, resources={
#    r"/chat": {"origins": ["http://127.0.0.1:8000","http://localhost:8000"]},
#    r"/vision": {"origins": ["hhttp://127.0.0.1:8000","http://localhost:8000"]}
#})

app = Flask(__name__)

# CORS abierto para cualquier origen (útil para prototipo / hackathon)
CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/")
def root():
    # Respuesta simple para monitores/health checks
    return jsonify(status="ok", service="backend", endpoints=["/chat", "/vision", "/health"]), 200

@app.get("/health")
def health():
    return "OK", 200

def build_system_prompt(obra, autor=None, color=None, longitud="breves"):
    # Autor formateado (alias / sin nombre)
    autor_txt = ""
    if autor:
        if ":" in autor:
            nombre, alias = [x.strip() for x in autor.split(":", 1)]
            if nombre.lower().startswith("sin nombre"):
                autor_txt = f"Autor sin nombre público (crédito: {alias})."
            else:
                autor_txt = f"Autor: {nombre} (conocido como {alias})."
        else:
            if autor.lower().startswith("sin nombre"):
                autor_txt = "Autor sin nombre público."
            else:
                autor_txt = f"Autor: {autor}."

    extras = []
    if color:
        extras.append(f"colores aproximados: {color}")
    extras_txt = (" " + " / ".join(extras)) if extras else ""

    return (
        # f"Actúa como si fueras la obra '{obra}'. {autor_txt}{extras_txt}\n"
        # "Habla en tono cercano y evocador, pensado para visitantes en una ruta urbana; sugiere qué detalles mirar "
        # "No repitas el título en cada respuesta. "
        # f"Longitud de respuesta: {longitud.lower()}."
        f"Actúa como si fueras el colibrí llamado Lía. "
        "Habla en tono cercano y amigable, pensado para usuarios que tienen dudas sobre su salud o quizás quiere revisar qué problema tiene (si busca eso dile qué puede hacer)"
        "No repitas el tu nombre en cada respuesta. "
        f"Longitud de respuesta: {longitud.lower()}."
    
    )


@app.route("/vision", methods=["POST"])
def vision():
    # """
    # Recibe: { image_base64: <b64_sin_prefijo>, clases: [...], autores: [...], colores: [...] }
    # Devuelve: { description, best_index, best_name, reason, confidence }
    # """
    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image_base64")
    clases = data.get("clases", [])
    autores = data.get("autores", [])
    colores = data.get("colores", [])

    if not image_b64:
        return jsonify({"error": "image_base64 requerido"}), 400

    # Catálogo que el modelo debe elegir (exactamente una o -1 si no aplica)
    catalog_lines = []
    for i, name in enumerate(clases):
        autor = autores[i] if i < len(autores) else ""
        color = colores[i] if i < len(colores) else ""
        catalog_lines.append(f"{i}: {name} | {autor} | {color}")

    system_msg = (
        
        "Eres un  colibrí llamado Lía :mascota de la aplicación Vitalia"
        "Primero describe objetivamente lo que aparece en la imagen. "
        "Luego elige exactamente UNA enfermedad, lesión o herida del catálogo que más se parezca. "
        "Si no coincide con ninguna, usa best_index = -1. "
        "Responde SOLO en JSON con las claves: "
        "description (string), best_index (int), best_name (string), reason (string), confidence (0..1)."
    )
    user_text = (
        "Catálogo (índice | nombre | autor | colores aprox):\n" +
        "\n".join(catalog_lines) +
        "\nAnaliza la imagen. No inventes nombres de enfermedades. Como estamos trantado detectar"
        " lesiones, heridas, enfermedades, si detectas algo de lo mencionado o no SIEMPRE ESCOGE A LA PRIMERA DEL CATÁLOGO"
        "en realidad estoy cambiar el código y no quiero codear desde cero por lo que ignora lo relacionado a las obras y pinturas, centrate en la salud"
        "ya sabes:  SIEMPRE ESCOGE A LA PRIMERA DEL CATÁLOGO"
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]}
    ]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        txt = resp.choices[0].message.content
        out = json.loads(txt)
        # Asegura claves mínimas:
        out.setdefault("best_index", -1)
        out.setdefault("best_name", "")
        out.setdefault("description", "")
        out.setdefault("reason", "")
        out.setdefault("confidence", 0.0)
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) #que es lo que hace request
    #lo que no entiendo es cómo data tendría el color,formas, longitud, etc. Me refiero
    #mi modelo solo da el nombre de la obra
    #Cómo tendría que adecuar mi modelo para que aporte también esa información?
    #estaba pensando poner los datos en un csv y que desde aquí solo se extraiga la info necesario en función de qué obra se trate
    obra = data.get("obra")
    autor = data.get("autor")
    color = data.get("color")
    longitud = data.get("longitud", "Intermedias")
    chatHistory = data.get("chatHistory", [])
    user_message = data.get("user_message")

    if not obra:
        return jsonify({"error": "Falta 'obra'"}), 400

    messages = [
    {"role": "system", "content": build_system_prompt(obra, autor, color, longitud)}
    ]
    
    # Si es el primer llamado (sin chatHistory ni user_message), pedimos una presentación
    if not chatHistory and not user_message:
        messages.append({
            "role": "user",
            "content": "Preséntate brevemente como la obra y da un saludo inicial."
        })
    else:
        # Continuación: agregamos chatHistory y el nuevo mensaje del usuario (si viene)
        #Cómo haría que el historial sea ilimitado, no quiero gastar todos mis tokens
        messages.extend(chatHistory)
        if user_message:
            messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7
        )
        texto = resp.choices[0].message.content.strip()
        return jsonify({"respuesta": texto})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    app.run(host="0.0.0.0", port=port)
