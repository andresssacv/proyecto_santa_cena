from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from supabase import create_client
import urllib.parse
import os
import pandas as pd

app = Flask(__name__)
CORS(app)

# ======================
# ENVIRONMENT VARIABLES
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase credentials missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# FRONTEND ROUTES
# ======================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# ======================
# CONTACTS FUNCTIONS
# ======================

def obtener_telefono(nombre):
    res = supabase.table("contactos") \
        .select("telefono") \
        .eq("nombre", nombre.strip()) \
        .execute()

    return res.data[0]["telefono"] if res.data else None


def guardar_telefono(nombre, telefono):
    supabase.table("contactos").insert({
        "nombre": nombre.strip(),
        "telefono": telefono.strip()
    }).execute()

# ======================
# REGISTROS FUNCTIONS
# ======================

def fila_ocupada(fila):
    res = supabase.table("registros_santa_cena") \
        .select("id") \
        .eq("fila", fila.strip()) \
        .execute()

    return bool(res.data)


def guardar_registro(nombre, fila, sector):
    supabase.table("registros_santa_cena").insert({
        "nombre": nombre.strip(),
        "fila": fila.strip(),
        "sector": sector.strip()
    }).execute()

# ======================
# MAIN REGISTER ENDPOINT
# ======================

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        data = request.get_json()

        nombre = data.get("nombre")
        fila = str(data.get("fila"))
        sector = data.get("sector")
        telefono_enviado = data.get("telefono")

        if not nombre or not fila:
            return jsonify({"status": "error", "message": "Nombre y fila requeridos"}), 400

        telefono_destino = obtener_telefono(nombre)

        if not telefono_destino:
            if not telefono_enviado:
                return jsonify({"status": "need_phone"})
            guardar_telefono(nombre, telefono_enviado)
            telefono_destino = telefono_enviado

        if fila_ocupada(fila):
            return jsonify({"status": "error", "message": "Fila ya ocupada"}), 400

        guardar_registro(nombre, fila, sector)

        mensaje = (
            f"✅ *Registro Santa Cena 2026*\n\n"
            f"Hola Hermano(a) *{nombre}*,\n"
            f"📍 *Sector {sector}*\n"
            f"🪑 *Fila {fila}*"
        )

        url_wa = f"https://wa.me/{telefono_destino}?text={urllib.parse.quote(mensaje)}"

        return jsonify({"status": "success", "url_whatsapp": url_wa})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================
# ADMIN API
# ======================

@app.route('/admin/listar')
def admin_listar():
    res = supabase.table("registros_santa_cena") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute()

    return jsonify(res.data)


@app.route('/admin/borrar', methods=['POST'])
def admin_borrar():
    data = request.get_json()

    supabase.table("registros_santa_cena") \
        .delete() \
        .eq("id", data.get("id")) \
        .execute()

    return jsonify({"status": "ok"})


@app.route('/admin/reset', methods=['POST'])
def admin_reset():
    supabase.table("registros_santa_cena") \
        .delete() \
        .neq("id", 0) \
        .execute()

    return jsonify({"status": "ok"})


@app.route('/admin/export')
def admin_export():
    res = supabase.table("registros_santa_cena").select("*").execute()

    df = pd.DataFrame(res.data)
    path = "export.csv"
    df.to_csv(path, index=False)

    return send_file(path, as_attachment=True)

# ======================
# RUN FOR RENDER
# ======================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
