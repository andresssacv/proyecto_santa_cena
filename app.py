from flask import Flask, request, jsonify, send_from_directory, render_template
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

# 1. Cargar el Mapa
@app.route('/')
def index():
    return render_template('index.html')

# 2. Cargar el Tablero (Nuevo archivo separado)
@app.route('/tablero')
def tablero():
    registros = []
    if os.path.exists(EXCEL_FILE):
        # Leemos el Excel para mandárselo al nuevo archivo HTML
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        registros = df.to_dict(orient='records')
    
    # Esto le dice a Python: "Busca tablero.html en la carpeta templates"
    return render_template('tablero.html', registros=registros)
    
# 3. Guardar Registro (Lo que envía el botón azul del mapa)
@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        data = request.json
        # Extraemos los datos usando los nombres exactos que enviará el HTML
        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector', 'N/A') # Si no hay sector, ponemos N/A

        if not nombre or not fila:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        # Cargar o crear Excel
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        else:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')

        # Verificar si la fila ya está ocupada
        if fila in df['Fila'].astype(str).values:
            return jsonify({"status": "error", "message": "Esta fila ya está ocupada"}), 400

        # Guardar registro
        nuevo = pd.DataFrame([[nombre, fila, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

        # --- GENERAR MENSAJE DE WHATSAPP ---
        texto_wa = f"✅ *Asignación Santa Cena 2026*\n\nHola Hermano(a) *{nombre}*,\nTu fila asignada es la: *{fila}*\nSector: *{sector}*\n\n_Favor de llegar con 15 min de anticipación._"
        texto_codificado = urllib.parse.quote(texto_wa)
        url_wa = f"https://wa.me/?text={texto_codificado}"

        return jsonify({"status": "success", "url_whatsapp": url_wa})

    except Exception as e:
        print(f"Error en el servidor: {e}")
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

# 4. Eliminar Registro (Botón Liberar del tablero)
@app.route('/eliminar_registro/<fila>', methods=['DELETE'])
def eliminar_registro(fila):
    try:
        if os.path.exists(EXCEL_FILE):
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
            # Filtramos para quitar la fila que queremos borrar
            df = df[df['Fila'].astype(str) != str(fila)]
            df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
            return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error al borrar: {e}")
    return jsonify({"status": "error"}), 400

# 5. Reset Total
@app.route('/reset_total_sistema')
def reset_total():
    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
    return redirect('/tablero')

if __name__ == '__main__':
    app.run(debug=True)






