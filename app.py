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
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase credentials missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
token_serializer = URLSafeSerializer(os.getenv("ASSIGNATION_LINK_SECRET", SUPABASE_KEY))


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def get_current_user():
    token = get_bearer_token()
    if not token:
        return None, jsonify({"status": "error", "message": "No autorizado (token requerido)"}), 401

    try:
        user_resp = supabase.auth.get_user(token)
        user = user_resp.user
        if not user:
            return None, jsonify({"status": "error", "message": "Token inválido"}), 401
        return user, None, None
    except Exception:
        return None, jsonify({"status": "error", "message": "Token inválido"}), 401


def require_admin(user):
    email = (user.email or "").lower()
    return email in ADMIN_EMAILS


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


@app.route('/login')
def login():
    return render_template('login.html')


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



@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({"status": "error", "message": "Email y contraseña son obligatorios"}), 400

    try:
        auth_resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        session = auth_resp.session
        user = auth_resp.user
        if not session or not user:
            return jsonify({"status": "error", "message": "Credenciales inválidas"}), 401

        return jsonify({
            "status": "success",
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": {"id": user.id, "email": user.email}
        })
    except Exception:
        return jsonify({"status": "error", "message": "Credenciales inválidas"}), 401

# ======================
# MAIN REGISTER ENDPOINT
# ======================

@app.route('/enviar_asignacion', methods=['POST'])
def enviar_asignacion():
    try:
        user, err, code = get_current_user()
        if err:
            return err, code

        data = request.get_json()

        nombre = data.get('nombre')
        fila = str(data.get('fila'))
        sector = data.get('sector')
        telefono_enviado = data.get('telefono')

        if not nombre or not fila or not sector:
            return jsonify({"status": "error", "message": "Faltan datos requeridos"}), 400

        # --- BUSCAR TELÉFONO(S) EN SUPABASE ---
        contacto = supabase.table("contactos").select("id, telefono").ilike("nombre", nombre.strip()).execute()

        candidatos = contacto.data or []
        telefono_destino = None
        telefono_enviado = str(telefono_enviado).strip() if telefono_enviado else ""

        # Caso 1: hay varios con el mismo nombre -> pedir selección por teléfono
        if len(candidatos) > 1:
            telefonos_candidatos = [str(c.get("telefono", "")).strip() for c in candidatos if c.get("telefono")]

            if not telefono_enviado:
                return jsonify({
                    "status": "choose_phone",
                    "message": "Se encontraron varias personas con ese nombre. Seleccione el teléfono correcto.",
                    "options": telefonos_candidatos
                })

            if telefono_enviado not in telefonos_candidatos:
                return jsonify({
                    "status": "error",
                    "message": "El teléfono seleccionado no coincide con las opciones encontradas para ese nombre."
                }), 400

            telefono_destino = telefono_enviado

        # Caso 2: existe uno solo
        elif len(candidatos) == 1:
            telefono_destino = str(candidatos[0].get("telefono", "")).strip()

        # Caso 3: no existe en contactos -> pedir teléfono para crearlo
        if not telefono_destino:
            if not telefono_enviado:
                return jsonify({
                    "status": "need_phone",
                    "message": "Hermano no encontrado. Ingrese teléfono."
                })

            telefono_destino = telefono_enviado

            supabase.table("contactos").insert({
                "nombre": nombre.strip(),
                "telefono": telefono_destino
            }).execute()

        # --- VALIDAR NOMBRE REPETIDO ---
        nombre_existente = (
            supabase.table("registros_santa_cena")
            .select("id, fila")
            .ilike("nombre", nombre.strip())
            .execute()
        )

        if nombre_existente.data:
            fila_actual = nombre_existente.data[0].get("fila")
            return jsonify({
                "status": "error",
                "message": f"Este hermano ya está registrado en la fila {fila_actual}"
            }), 400

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
            "sector": sector,
            "registrador_id": user.id,
            "registrador_email": user.email
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


@app.route('/mis_registros')
def mis_registros():
    user, err, code = get_current_user()
    if err:
        return err, code

    res = supabase.table("registros_santa_cena") \
        .select("*") \
        .eq("registrador_id", user.id) \
        .order("created_at", desc=True) \
        .execute()

    return jsonify(res.data)

@app.route('/admin/listar')
def admin_listar():
    user, err, code = get_current_user()
    if err:
        return err, code
    if not require_admin(user):
        return jsonify({"status": "error", "message": "Acceso solo administrador"}), 403

    res = supabase.table("registros_santa_cena") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute()

    return jsonify(res.data)


@app.route('/admin/borrar', methods=['POST'])
def admin_borrar():
    user, err, code = get_current_user()
    if err:
        return err, code
    if not require_admin(user):
        return jsonify({"status": "error", "message": "Acceso solo administrador"}), 403

    data = request.get_json()

    supabase.table("registros_santa_cena") \
        .delete() \
        .eq("id", data.get("id")) \
        .execute()

    return jsonify({"status": "ok"})


@app.route('/admin/reset', methods=['POST'])
def admin_reset():
    user, err, code = get_current_user()
    if err:
        return err, code
    if not require_admin(user):
        return jsonify({"status": "error", "message": "Acceso solo administrador"}), 403

    supabase.table("registros_santa_cena") \
        .delete() \
        .neq("id", 0) \
        .execute()

    return jsonify({"status": "ok"})


@app.route('/admin/export')
def admin_export():
    user, err, code = get_current_user()
    if err:
        return err, code
    if not require_admin(user):
        return jsonify({"status": "error", "message": "Acceso solo administrador"}), 403

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
