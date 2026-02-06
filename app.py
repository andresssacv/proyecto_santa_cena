from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import urllib.parse
import pandas as pd
import os
import openpyxl

app = Flask(__name__)
CORS(app)

EXCEL_FILE = 'registros_santa_cena.xlsx'
JSON_FILE = 'datos_servidores.json'

def verificar_disponibilidad_y_registrar(nombre, fila, sector):
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    try:
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        fila_str = str(fila)
        if fila_str in df['Fila'].astype(str).values:
            return False, f"La fila {fila} ya está ocupada."

        nuevo_registro = pd.DataFrame([[nombre, fila_str, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo_registro], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
        return True, "Registro exitoso"
    except Exception as e:
        return False, str(e)

def buscar_hermano(nombre_buscado):
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            servidores = json.load(f)
            for s in servidores:
                if nombre_buscado.lower().strip() in s['nombre'].lower().strip():
                    return s
    except:
        return None
    return None

def guardar_nuevo_en_json(nombre, telefono):
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.append({"nombre": nombre, "telefono": telefono})
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    data = request.json
    nombre_input = data.get('nombre')
    fila = data.get('fila')
    sector = data.get('sector')
    telefono_nuevo = data.get('telefono')

    hermano = buscar_hermano(nombre_input)

    if not hermano and telefono_nuevo:
        if guardar_nuevo_en_json(nombre_input, telefono_nuevo):
            hermano = {"nombre": nombre_input, "telefono": telefono_nuevo}

    if not hermano:
        return jsonify({"status": "not_found", "message": "No existe"}), 404

    exito, mensaje = verificar_disponibilidad_y_registrar(hermano['nombre'], fila, sector)
    if not exito:
        return jsonify({"status": "error", "message": mensaje}), 400

# Generar WhatsApp
    # Usamos 127.0.0.1 que es más estable que localhost para rutas locales
    link_mapa = f"http://127.0.0.1:5500/fronted_santacena.html?fila={fila}&readOnly=true"    
    
    msj = f"Hola {hermano['nombre']}, tu ubicación para la Santa Cena es:\n📍 Fila: {fila}\nSector: {sector}\n\nMira tu mapa aquí: {link_mapa}"
    url_wsp = f"https://wa.me/{hermano['telefono']}?text={urllib.parse.quote(msj)}"
    
    return jsonify({"status": "success", "url_whatsapp": url_wsp})

if __name__ == '__main__':
    app.run(debug=True, port=5000)