from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import os
import urllib.parse

app = Flask(__name__)
CORS(app)

EXCEL_FILE = 'registros_santa_cena.xlsx'

@app.route('/')
def index():
    # Flask buscará 'index.html' dentro de la carpeta 'templates'
    return render_template('index.html')

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        # Esta línea es la que lee la "cajita" de datos que enviamos desde el HTML
        data = request.get_json() 
        
        if not data:
            return jsonify({"status": "error", "message": "No se recibieron datos"}), 400
        
        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector')
        
        # ... resto del código de guardado en Excel ...'N/A')

        if not nombre or not fila:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        if not os.path.exists(EXCEL_FILE):
            df = pd.DataFrame(columns=['Nombre', 'Fila', 'Sector'])
        else:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')

        if fila in df['Fila'].astype(str).values:
            return jsonify({"status": "error", "message": f"Fila {fila} ocupada"}), 400

        nuevo = pd.DataFrame([[nombre, fila, sector]], columns=['Nombre', 'Fila', 'Sector'])
        df = pd.concat([df, nuevo], ignore_index=True)
        df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

        # Link de WhatsApp corregido
        mensaje = f"✅ *Registro Santa Cena*\nHermano: *{nombre}*\nFila: *{fila}*\nSector: *{sector}*"
        url_wa = f"https://wa.me/?text={urllib.parse.quote(mensaje)}"
        
        return jsonify({"status": "success", "url_whatsapp": url_wa})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

