from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import urllib.parse
import pandas as pd
import os
import openpyxl

# Configuración de carpetas para Render
app = Flask(__name__, static_folder='templates', static_url_path='')
CORS(app)

EXCEL_FILE = 'registros_santa_cena.xlsx'
JSON_FILE = 'datos_servidores.json'

# --- FUNCIONES DE LÓGICA DE DATOS ---

def verificar_disponibilidad_y_registrar(nombre, fila, sector):
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    try:
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        fila_str = str(fila)
        
        # Verificar si la fila ya está en el Excel
        if fila_str in df['Fila'].astype(str).values:
            return False, f"La fila {fila} ya está ocupada."

        # Agregar nuevo registro
        nuevo_registro = pd.DataFrame([[nombre, fila_str, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo_registro], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
        return True, "Registro exitoso"
    except Exception as e:
        return False, str(e)

def buscar_hermano(nombre_buscado):
    try:
        if not os.path.exists(JSON_FILE): return None
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            servidores = json.load(f)
            for s in servidores:
                if nombre_buscado.lower().strip() in s['nombre'].lower().strip():
                    return s
    except: return None
    return None

def guardar_nuevo_en_json(nombre, telefono):
    try:
        data = []
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        data.append({"nombre": nombre, "telefono": telefono})
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except: return False

# --- RUTAS DE LA PÁGINA ---
from flask import Flask, request, jsonify, render_template, redirect
import pandas as pd
import os

app = Flask(__name__)

EXCEL_FILE = 'registros_santa_cena.xlsx'

# 1. Cargar el Mapa
@app.route('/')
def index():
    return render_template('index.html')

# 2. Cargar el Tablero (Nuevo archivo separado)
@app.route('/tablero')
def tablero():
    registros = []
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        registros = df.to_dict(orient='records')
    return render_template('tablero.html', registros=registros)

# 3. Guardar Registro (Lo que envía el botón azul del mapa)
@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        data = request.json
        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector')

        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        else:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')

        # Verificar si la fila ya existe
        if fila in df['Fila'].astype(str).values:
            return jsonify({"status": "error", "message": "Fila ya ocupada"}), 400

        # Guardar
        nuevo = pd.DataFrame([[nombre, fila, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

        # Link de WhatsApp
        url_wa = f"https://wa.me/?text=Hola%20{nombre},%20tu%20fila%20es%20{fila}%20Sector%20{sector}"
        return jsonify({"status": "success", "url_whatsapp": url_wa})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. Eliminar Registro (Botón Liberar del tablero)
@app.route('/eliminar_registro/<fila>', methods=['DELETE'])
def eliminar_registro(fila):
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        df = df[df['Fila'].astype(str) != str(fila)]
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# 5. Reset Total
@app.route('/reset_total_sistema')
def reset_total():
    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
    return redirect('/tablero')

if __name__ == '__main__':
    app.run(debug=True)




