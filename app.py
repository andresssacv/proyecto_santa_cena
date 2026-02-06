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

@app.route('/')
def home():
    # Entrega el HTML de forma estática para evitar conflictos de llaves {{ }}
    return send_from_directory('templates', 'index.html')

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    data = request.json
    nombre_input = data.get('nombre')
    fila = data.get('fila')
    sector = data.get('sector')
    telefono_nuevo = data.get('telefono')

    hermano = buscar_hermano(nombre_input)

    # Si no existe, lo creamos con el teléfono que envió el prompt del HTML
    if not hermano and telefono_nuevo:
        if guardar_nuevo_en_json(nombre_input, telefono_nuevo):
            hermano = {"nombre": nombre_input, "telefono": telefono_nuevo}

    if not hermano:
        return jsonify({"status": "not_found", "message": "No existe"}), 404

    exito, mensaje = verificar_disponibilidad_y_registrar(hermano['nombre'], fila, sector)
    if not exito:
        return jsonify({"status": "error", "message": mensaje}), 400

    # Generar link de WhatsApp
    base_url = request.host_url.rstrip('/')
    link_mapa = f"{base_url}/?fila={fila}&readOnly=true"
    msj = f"Hola {hermano['nombre']}, Fila: {fila}, Sector: {sector}. Mapa: {link_mapa}"
    url_whatsapp = f"https://wa.me/{hermano['telefono']}?text={urllib.parse.quote(msj)}"
    
    return jsonify({"status": "success", "url_whatsapp": url_whatsapp})

# --- PANEL DE ADMINISTRACIÓN Y CONTROL ---

@app.route('/tablero')
def tablero():
    if not os.path.exists(EXCEL_FILE):
        return "<h2 style='font-family:sans-serif; text-align:center;'>No hay registros aún.</h2>"
    
    df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
    filas_html = ""
    for index, row in df.iterrows():
        filas_html += f'''
        <tr>
            <td>{row['Nombre']}</td>
            <td><b>Fila {row['Fila']}</b></td>
            <td>{row['Sector']}</td>
            <td><button onclick="eliminar('{row['Fila']}')" style="background:red; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer;">Eliminar</button></td>
        </tr>
        '''

    return f'''
    <html>
        <head>
            <title>Admin - Santa Cena</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; background: #f1f5f9; padding: 20px; }}
                table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
                th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #edf2f7; }}
                th {{ background: #2563eb; color: white; }}
                .btn-reset {{ background: #ef4444; color: white; padding: 10px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 20px; font-weight: bold; }}
            </style>
            <script>
                async function eliminar(fila) {{
                    if(confirm("¿Liberar la fila " + fila + "?")) {{
                        const res = await fetch('/eliminar_registro/' + fila, {{ method: 'DELETE' }});
                        if(res.ok) location.reload();
                    }}
                }}
            </script>
        </head>
        <body>
            <h1>Registros en Vivo</h1>
            <table>
                <tr><th>Nombre</th><th>Fila</th><th>Sector</th><th>Acción</th></tr>
                {filas_html}
            </table>
            <a href="/reset_total_sistema" class="btn-reset" onclick="return confirm('¿BORRAR TODO EL MES?')">RESET TOTAL MENSUAL</a>
        </body>
    </html>
    '''

@app.route('/eliminar_registro/<fila>', methods=['DELETE'])
def eliminar_registro(fila):
    try:
        if os.path.exists(EXCEL_FILE):
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
            df = df[df['Fila'].astype(str) != str(fila)]
            df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
            return jsonify({"status": "success"})
    except: pass
    return jsonify({"status": "error"}), 400

@app.route('/reset_total_sistema')
def reset_total():
    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
    return "<h1>Sistema Limpiado.</h1><a href='/tablero'>Volver</a>"

# Ejecución
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
