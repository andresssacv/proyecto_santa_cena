from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import pandas as pd
import os
import urllib.parse

# Configuración básica
app = Flask(__name__)
CORS(app)

EXCEL_FILE = 'registros_santa_cena.xlsx'

# 1. RUTA PARA MOSTRAR EL MAPA
@app.route('/')
def index():
    # Como tienes el archivo en la carpeta 'templates', usamos render_template
    # Flask buscará automáticamente dentro de la carpeta 'templates'
    return render_template('index.html')

# 2. RUTA PARA RECIBIR EL REGISTRO
@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        data = request.json
        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector', 'N/A')

        if not nombre or not fila:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        # Manejo del Excel
        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        else:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')

        # Verificar si la fila está ocupada
        if fila in df['Fila'].astype(str).values:
            return jsonify({"status": "error", "message": f"La fila {fila} ya está ocupada"}), 400

        # Guardar nuevo registro
        nuevo = pd.DataFrame([[nombre, fila, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

        # Generar mensaje para WhatsApp
        mensaje_wa = f"✅ *Registro Exitoso*\n\nHermano(a): *{nombre}*\nFila: *{fila}*\nSector: *{sector}*"
        mensaje_url = urllib.parse.quote(mensaje_wa)
        url_whatsapp = f"https://wa.me/?text={mensaje_url}"

        return jsonify({
            "status": "success", 
            "url_whatsapp": url_whatsapp
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
