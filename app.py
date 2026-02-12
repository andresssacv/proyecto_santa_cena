from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from supabase import create_client
from itsdangerous import URLSafeSerializer, BadSignature
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
token_serializer = URLSafeSerializer(os.getenv("ASSIGNATION_LINK_SECRET", SUPABASE_KEY))


def obtener_mesa_label(sector):
    """Retorna el nombre de mesa/mesón en base al sector."""
    try:
        sector_id = int(sector)
    except (TypeError, ValueError):
        return "No definida"

    meson_norte = {1, 2, 5}
    meson_sur = {7, 9, 11, 12}
    meson_entrada = {3, 4, 6, 8, 10, 13, 14}

    if sector_id in meson_norte:
        return "Mesón Norte"
    if sector_id in meson_sur:
        return "Mesón Sur"
    if sector_id in meson_entrada:
        return "Mesón Entrada"
    return "No definida"

# ======================
# FRONTEND ROUTES
# ======================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/ver_asignacion/<token>')
def ver_asignacion(token):
    try:
        payload = token_serializer.loads(token)
    except BadSignature:
        return "Link inválido o expirado", 400

    fila = str(payload.get("fila", "")).strip()
    if not fila:
        return "Asignación inválida", 400

    return render_template('ver_asignacion.html', fila_asignada=fila)

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
        "telefono": str(telefono).strip()
    }).execute()

# ======================
# registro FUNCTIONS
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

        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector')
        telefono_enviado = data.get('telefono')

        if not nombre or not fila or not sector:
            return jsonify({"status": "error", "message": "Faltan datos requeridos"}), 400

        # --- BUSCAR TELÉFONO EN SUPABASE ---
        contacto = supabase.table("contactos").select("telefono").eq("nombre", nombre).execute()

        telefono_destino = None

        if contacto.data and len(contacto.data) > 0:
            telefono_destino = contacto.data[0]["telefono"]

        # --- SI NO EXISTE, PEDIR TELÉFONO ---
        if not telefono_destino:
            if not telefono_enviado:
                return jsonify({
                    "status": "need_phone",
                    "message": "Hermano no encontrado. Ingrese teléfono."
                })

            telefono_destino = str(telefono_enviado).strip()

            supabase.table("contactos").insert({
                "nombre": nombre.strip(),
                "telefono": telefono_destino
            }).execute()

        # --- VALIDAR FILA REPETIDA ---
        fila_existente = supabase.table("registros_santa_cena") \
            .select("id") \
            .eq("fila", fila) \
            .execute()

        if fila_existente.data:
            return jsonify({"status": "error", "message": "Fila ya ocupada"}), 400

        # --- GUARDAR REGISTRO ---
        supabase.table("registros_santa_cena").insert({
            "nombre": nombre.strip(),
            "fila": fila,
            "sector": sector
        }).execute()

        # --- LINK WHATSAPP ---
        mesa_label = obtener_mesa_label(sector)
        token = token_serializer.dumps({"fila": fila})
        link_visualizacion = f"{request.host_url.rstrip('/')}/ver_asignacion/{token}"

        mensaje = (
            f"✅ *Registro Santa Cena 2026*\n\n"
            f"Hola Hermano(a) *{nombre}*,\n"
            f"Su lugar asignado es:\n"
            f"📍 *Sector {sector}*\n"
            f"🧭 *Mesa: {mesa_label}*\n"
            f"🪑 *Fila {fila}*\n\n"
            f"🔎 Ver mapa interactivo (solo lectura):\n{link_visualizacion}"
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



