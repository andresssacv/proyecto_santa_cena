from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import os
import urllib.parse

app = Flask(__name__)
CORS(app)

JSON_FILE = 'datos_servidores.json'
EXCEL_FILE = 'registros_santa_cena.xlsx'

@app.route('/')
def index():
    # Flask buscará 'index.html' dentro de la carpeta 'templates'
    return render_template('index.html')

def obtener_telefono(nombre):
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try:
                datos = json.load(f)
                # Buscamos ignorando mayúsculas/minúsculas
                return datos.get(nombre.strip().upper())
            except: return None
    return None

def guardar_telefono(nombre, telefono):
    datos = {}
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try: datos = json.load(f)
            except: datos = {}
    
    datos[nombre.strip().upper()] = telefono
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector')
        telefono_enviado = data.get('telefono') # Teléfono que viene del formulario si es nuevo

        if not nombre or not fila:
            return jsonify({"status": "error", "message": "Nombre y Fila son requeridos"}), 400

        # --- LÓGICA DE TELÉFONO ---
        telefono_destino = obtener_telefono(nombre)

        if not telefono_destino:
            if not telefono_enviado:
                # Si no está en el JSON y no enviaron uno nuevo, avisamos al HTML
                return jsonify({"status": "need_phone", "message": "Hermano no encontrado. Por favor ingrese su teléfono."})
            else:
                # Si enviaron un teléfono nuevo, lo guardamos
                guardar_telefono(nombre, telefono_enviado)
                telefono_destino = telefono_enviado

        # --- GUARDAR EN EXCEL (Tu lógica existente) ---
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        else:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')

        if fila in df['Fila'].astype(str).values:
            return jsonify({"status": "error", "message": "Fila ya ocupada"}), 400

        nuevo = pd.DataFrame([[nombre, fila, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

        # --- LINK DE WHATSAPP DIRECTO ---
        mensaje = f"✅ *Registro Santa Cena 2026*\n\nHola Hermano(a) *{nombre}*,\nSu lugar asignado es:\n📍 *Sector {sector}*\n🪑 *Fila {fila}*"
        # Usamos el teléfono encontrado para que el mensaje le llegue directamente a él/ella
        url_wa = f"https://wa.me/{telefono_destino}?text={urllib.parse.quote(mensaje)}"
        
        return jsonify({"status": "success", "url_whatsapp": url_wa})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


