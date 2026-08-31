from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3
import os
import json
import base64
import requests
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

app = Flask(__name__)
app.secret_key = 'pancanela_secret_key_ultra_segura_2026'

# ==========================================
# 🔑 ZONA DE CLAVES API
# ==========================================
OPENAI_API_KEY = "sk-TU_CLAVE_DE_OPENAI_AQUI"
# ==========================================

# Configuración para auto-backup en GitHub
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO') # Ej: 'tuusuario/pancanela'

def sincronizar_con_github():
    """Sube automáticamente el archivo pancanela.db a GitHub para que no se pierdan los datos."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return # Si no están configuradas las variables en local, no hace nada
    
    db_file = 'pancanela.db'
    if not os.path.exists(db_file):
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{db_file}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    try:
        # 1. Obtener el sha actual del archivo en GitHub (necesario para actualizarlo)
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None

        # 2. Leer la base de datos local y codificarla en Base64
        with open(db_file, "rb") as f:
            content_encoded = base64.b64encode(f.read()).decode('utf-8')

        # 3. Preparar los datos para la API de GitHub
        data = {
            "message": f"Auto-backup base de datos {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content_encoded,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha

        # 4. Enviar la actualización a GitHub
        requests.put(url, headers=headers, json=data)
    except Exception as e:
        print(f"Error en auto-backup: {e}")

def get_db_connection():
    # Al iniciar o registrar, si no existe localmente pero está configurado GitHub, 
    # podríamos intentar descargarla, pero SQLite creará una fresca o usará la existente.
    conn = sqlite3.connect('pancanela.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS caja (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, 
        tipo TEXT, 
        descripcion TEXT, 
        monto REAL,
        metodo TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS jornadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        estado TEXT,
        efectivo_ventas REAL,
        transferencia_ventas REAL,
        total_gastos REAL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS redes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, plataforma TEXT, seguidores INTEGER, interaccion REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, insumo TEXT, cantidad REAL, unidad TEXT, minimo REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, costo_produccion REAL, precio_venta REAL)''')
    
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (username, password) VALUES ('admin', ?)", (hashed_pw,))

    cursor.execute("SELECT COUNT(*) FROM caja")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO caja (fecha, tipo, descripcion, monto, metodo) VALUES ('2026-08-20', 'Ingreso', 'Venta mostrador', 15000, 'Efectivo')")
        cursor.execute("INSERT INTO caja (fecha, tipo, descripcion, monto, metodo) VALUES ('2026-08-21', 'Ingreso', 'Pedidos WhatsApp', 22000, 'Transferencia')")
        cursor.execute("INSERT INTO caja (fecha, tipo, descripcion, monto, metodo) VALUES ('2026-08-22', 'Gasto', 'Harina y grasa', 8000, 'Efectivo')")
        cursor.execute("INSERT INTO redes (fecha, plataforma, seguidores, interaccion) VALUES ('2026-08-20', 'Instagram', 1200, 5.2)")
        cursor.execute("INSERT INTO redes (fecha, plataforma, seguidores, interaccion) VALUES ('2026-08-21', 'Instagram', 1250, 6.1)")
        cursor.execute("INSERT INTO stock (insumo, cantidad, unidad, minimo) VALUES ('Harina 000', 50, 'kg', 10)")
        cursor.execute("INSERT INTO stock (insumo, cantidad, unidad, minimo) VALUES ('Grasa bovina', 15, 'kg', 5)")
        cursor.execute("INSERT INTO recetas (producto, costo_produccion, precio_venta) VALUES ('Docena de Medialunas', 4500, 9500)")

    conn.commit()
    conn.close()

init_db()

# (Plantilla HTML y Rutas idénticas con llamadas a sincronizar_con_github() en cada modificación)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pan Canela | Panel Ejecutivo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-[#F9F8F6] text-[#1C1C1E] font-sans min-h-screen flex flex-col justify-between">

    {% if not session.get('user_id') %}
    <div class="flex items-center justify-center min-h-screen px-4">
        <div class="bg-white p-8 rounded-2xl border border-[#E5E5EA] shadow-sm w-full max-w-md">
            <div class="text-center mb-6">
                <div class="w-12 h-12 bg-[#1C1C1E] text-white rounded-xl font-bold flex items-center justify-center text-lg mx-auto mb-3 shadow">PC</div>
                <h1 class="text-xl font-bold tracking-tight text-[#1C1C1E]">PAN CANELA</h1>
                <p class="text-xs text-[#636366] mt-1">Ingrese sus credenciales para acceder al sistema</p>
            </div>
            
            {% if error %}
            <div class="mb-4 bg-red-50 border border-red-200 text-red-600 text-xs p-3 rounded-lg text-center font-medium">
                {{ error }}
            </div>
            {% endif %}

            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="text-xs text-[#636366] font-medium block mb-1">Usuario</label>
                    <input type="text" name="username" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs text-[#1C1C1E] outline-none">
                </div>
                <div>
                    <label class="text-xs text-[#636366] font-medium block mb-1">Contraseña</label>
                    <input type="password" name="password" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs text-[#1C1C1E] outline-none">
                </div>
                <button type="submit" class="w-full bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-3 rounded-lg text-xs transition shadow-sm">Iniciar Sesión</button>
            </form>
            <p class="text-[10px] text-center text-[#636366] mt-6">Usuario por defecto: <strong>admin</strong> / <strong>admin123</strong></p>
        </div>
    </div>

    {% else %}
    <div>
        <nav class="bg-white border-b border-[#E5E5EA] px-8 py-4 sticky top-0 z-50 shadow-sm">
            <div class="container mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-[#1C1C1E] text-white rounded font-bold flex items-center justify-center text-sm">PC</div>
                    <div>
                        <h1 class="text-base font-bold tracking-tight text-[#1C1C1E]">PAN CANELA <span class="text-[10px] font-medium text-[#636366] bg-[#E5E5EA] px-2 py-0.5 rounded ml-2">Sesión: {{ session.get('username') }}</span></h1>
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex flex-wrap gap-1 bg-[#F2F1EC] p-1 rounded-lg border border-[#E5E5EA]">
                        <a href="/?tab=dashboard" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'dashboard' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Dashboard Analítico</a>
                        <a href="/?tab=finanzas" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'finanzas' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Caja & Jornada</a>
                        <a href="/?tab=stock" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'stock' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Insumos & Stock</a>
                        <a href="/?tab=redes" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'redes' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Redes Ancladas</a>
                    </div>
                    <a href="/logout" class="bg-red-50 hover:bg-red-100 text-red-600 font-semibold px-3 py-1.5 rounded-lg text-xs transition border border-red-200">Cerrar Sesión</a>
                </div>
            </div>
        </nav>

        <main class="container mx-auto px-8 py-10">
            {% if tab == 'dashboard' %}
            <div class="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Panel de Rendimiento Global</h2>
                    <p class="text-sm text-[#636366] mt-1">Monitoreo en tiempo real de ventas, efectivo y transferencias.</p>
                </div>
                <div class="bg-white border border-[#E5E5EA] px-4 py-2 rounded-xl shadow-sm flex items-center gap-3">
                    <span class="w-3 h-3 rounded-full {{ 'bg-green-500 animate-pulse' if jornada_abierta else 'bg-red-400' }}"></span>
                    <span class="text-xs font-bold uppercase tracking-wider text-[#1C1C1E]">
                        Estado Día: {{ 'JORNADA ABIERTA' if jornada_abierta else 'JORNADA CERRADA' }}
                    </span>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Venta Total de Hoy</p>
                    <p class="text-3xl font-extrabold text-[#1C1C1E] mt-2">${{ ventas_hoy_total }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Hoy en Efectivo</p>
                    <p class="text-3xl font-extrabold text-green-600 mt-2">${{ ventas_hoy_efectivo }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Hoy en Transferencia</p>
                    <p class="text-3xl font-extrabold text-blue-600 mt-2">${{ ventas_hoy_transferencia }}</p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Acumulado Ingresos</p>
                    <p class="text-2xl font-extrabold text-[#1C1C1E] mt-2">${{ total_ingresos }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Acumulado Gastos</p>
                    <p class="text-2xl font-extrabold text-[#1C1C1E] mt-2">${{ total_gastos }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold tracking-wider text-[#636366] uppercase">Balance Neto</p>
                    <p class="text-2xl font-extrabold text-[#1C1C1E] mt-2">${{ balance }}</p>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm flex flex-col justify-between">
                    <div>
                        <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Evolución de Caja (Ingresos vs Gastos)</h3>
                        <div class="relative h-56 w-full mb-4">
                            <canvas id="cajaChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm flex flex-col justify-between">
                    <div>
                        <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Crecimiento de Comunidad en Redes</h3>
                        <div class="relative h-56 w-full mb-4">
                            <canvas id="redesChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                const fechasCaja = {{ fechas_caja | safe }}; 
                const ingresosCaja = {{ ingresos_caja | safe }}; 
                const gastosCaja = {{ gastos_caja | safe }};
                const fechasRedes = {{ fechas_redes | safe }}; 
                const igSeguidores = {{ ig_seguidores | safe }}; 
                const tkSeguidores = {{ tk_seguidores | safe }};

                new Chart(document.getElementById('cajaChart'), { 
                    type: 'bar', 
                    data: { 
                        labels: fechasCaja, 
                        datasets: [
                            { label: 'Ingresos', data: ingresosCaja, backgroundColor: 'rgba(34, 197, 94, 0.4)', borderColor: 'rgba(34, 197, 94, 0.8)', borderWidth: 1}, 
                            { label: 'Gastos', data: gastosCaja, backgroundColor: 'rgba(239, 68, 68, 0.4)', borderColor: 'rgba(239, 68, 68, 0.8)', borderWidth: 1}
                        ] 
                    }, 
                    options: { responsive: true, maintainAspectRatio: false} 
                });
                
                new Chart(document.getElementById('redesChart'), { 
                    type: 'line', 
                    data: { 
                        labels: fechasRedes, 
                        datasets: [
                            { label: 'Instagram', data: igSeguidores, borderColor: '#1C1C1E', tension: 0.3}, 
                            { label: 'TikTok', data: tkSeguidores, borderColor: '#8E8E93', tension: 0.3}
                        ] 
                    }, 
                    options: { responsive: true, maintainAspectRatio: false} 
                });
            </script>
            
            {% elif tab == 'finanzas' %}
            <div class="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Caja & Control de Jornada</h2>
                    <p class="text-sm text-[#636366] mt-1">Apertura y cierre de día, registro de ingresos/gastos por efectivo o transferencia.</p>
                </div>
                <div class="flex gap-2">
                    {% if not jornada_abierta %}
                    <a href="/abrir_jornada" class="bg-green-600 hover:bg-green-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition shadow-sm">🔓 Abrir el Día</a>
                    {% else %}
                    <a href="/cerrar_jornada" onclick="return confirm('¿Seguro que deseas cerrar el día?');" class="bg-red-600 hover:bg-red-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition shadow-sm">🔒 Cerrar el Día</a>
                    {% endif %}
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">
                        {{ 'Editar Movimiento' if edit_caja else 'Registrar Ingreso o Gasto' }}
                    </h3>
                    <form action="{{ url_for('editar_caja', id=edit_caja['id']) if edit_caja else '/agregar_caja' }}" method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs text-[#636366] font-medium block mb-1">Fecha</label>
                                <input type="date" name="fecha" value="{{ edit_caja['fecha'] if edit_caja else '' }}" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                            </div>
                            <div>
                                <label class="text-xs text-[#636366] font-medium block mb-1">Tipo</label>
                                <select name="tipo" class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                                    <option value="Ingreso" {{ 'selected' if edit_caja and edit_caja['tipo'] == 'Ingreso' else '' }}>Ingreso</option>
                                    <option value="Gasto" {{ 'selected' if edit_caja and edit_caja['tipo'] == 'Gasto' else '' }}>Gasto</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Método de Pago</label>
                            <select name="metodo" class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                                <option value="Efectivo" {{ 'selected' if edit_caja and edit_caja['metodo'] == 'Efectivo' else '' }}>Efectivo</option>
                                <option value="Transferencia" {{ 'selected' if edit_caja and edit_caja['metodo'] == 'Transferencia' else '' }}>Transferencia</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Descripción</label>
                            <input type="text" name="descripcion" value="{{ edit_caja['descripcion'] if edit_caja else '' }}" placeholder="Ej: Venta mostrador" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Monto ($)</label>
                            <input type="number" step="any" name="monto" value="{{ edit_caja['monto'] if edit_caja else '' }}" placeholder="0.00" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div class="flex gap-2">
                            <button type="submit" class="flex-1 bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-2.5 px-4 rounded-lg text-xs transition">Guardar</button>
                            {% if edit_caja %}
                            <a href="/?tab=finanzas" class="bg-[#E5E5EA] hover:bg-[#D1D1D6] text-[#1C1C1E] font-medium py-2.5 px-4 rounded-lg text-xs text-center transition">Cancelar</a>
                            {% endif %}
                        </div>
                    </form>
                </div>

                <div class="lg:col-span-2 bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Historial de Caja</h3>
                    <div class="overflow-x-auto max-h-96 overflow-y-auto">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-[#F9F8F6] text-[#636366] uppercase text-[10px]">
                                <tr>
                                    <th class="p-2">Fecha</th>
                                    <th class="p-2">Tipo</th>
                                    <th class="p-2">Método</th>
                                    <th class="p-2">Descripción</th>
                                    <th class="p-2 text-right">Monto</th>
                                    <th class="p-2 text-center">Acciones</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-[#E5E5EA]">
                                {% for m in lista_caja %}
                                <tr class="hover:bg-[#F9F8F6]">
                                    <td class="p-2 text-[#636366]">{{ m['fecha'] }}</td>
                                    <td class="p-2 font-semibold {{ 'text-green-600' if m['tipo'] == 'Ingreso' else 'text-red-600' }}">{{ m['tipo'] }}</td>
                                    <td class="p-2 font-medium text-blue-600">{{ m['metodo'] if m['metodo'] else 'Efectivo' }}</td>
                                    <td class="p-2 text-[#1C1C1E]">{{ m['descripcion'] }}</td>
                                    <td class="p-2 text-right font-bold text-[#1C1C1E]">${{ m['monto'] }}</td>
                                    <td class="p-2 text-center space-x-2">
                                        <a href="/?tab=finanzas&edit_caja={{ m['id'] }}" class="text-blue-600 font-medium hover:underline">Editar</a>
                                        <a href="/eliminar_caja/{{ m['id'] }}" onclick="return confirm('¿Seguro?');" class="text-red-600 font-medium hover:underline">Eliminar</a>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            {% elif tab == 'stock' %}
            <div class="mb-8">
                <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Control de Insumos & Stock</h2>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <form action="/agregar_stock" method="POST" class="space-y-4">
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Nombre Insumo</label>
                            <input type="text" name="insumo" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Cantidad</label>
                            <input type="number" step="any" name="cantidad" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs text-[#636366] font-medium block mb-1">Unidad</label>
                                <input type="text" name="unidad" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                            </div>
                            <div>
                                <label class="text-xs text-[#636366] font-medium block mb-1">Mínimo</label>
                                <input type="number" step="any" name="minimo" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                            </div>
                        </div>
                        <button type="submit" class="w-full bg-[#1C1C1E] text-white font-medium py-2.5 rounded-lg text-xs">Guardar</button>
                    </form>
                </div>
                <div class="lg:col-span-2 bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-[#F9F8F6] text-[#636366] uppercase text-[10px]">
                            <tr>
                                <th class="p-3">Insumo</th>
                                <th class="p-3">Cantidad</th>
                                <th class="p-3">Mínimo</th>
                                <th class="p-3 text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-[#E5E5EA]">
                            {% for s in lista_stock %}
                            <tr>
                                <td class="p-3 font-bold">{{ s['insumo'] }}</td>
                                <td class="p-3">{{ s['cantidad'] }} {{ s['unidad'] }}</td>
                                <td class="p-3">{{ s['minimo'] }} {{ s['unidad'] }}</td>
                                <td class="p-3 text-center"><a href="/eliminar_stock/{{ s['id'] }}" class="text-red-600 hover:underline">Eliminar</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            {% endif %}
        </main>
    </div>
    {% endif %}
</body>
</html>
'''

# ================= ROUTES CON AUTO-BACKUP =================

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        return redirect('/')
    else:
        return render_template_string(HTML_TEMPLATE, error="Usuario o contraseña incorrectos.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE)

    tab = request.args.get('tab', 'dashboard')
    edit_caja_id = request.args.get('edit_caja')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM jornadas WHERE estado='Abierta'")
    jornada_abierta = cursor.fetchone()[0] > 0

    hoy_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND (metodo='Efectivo' OR metodo IS NULL)", (hoy_str,))
    ventas_hoy_efectivo = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Transferencia'", (hoy_str,))
    ventas_hoy_transferencia = cursor.fetchone()[0] or 0.0
    ventas_hoy_total = ventas_hoy_efectivo + ventas_hoy_transferencia

    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso'")
    total_ingresos = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Gasto'")
    total_gastos = cursor.fetchone()[0] or 0.0
    balance = total_ingresos - total_gastos

    cursor.execute("SELECT fecha, SUM(monto) FROM caja WHERE tipo='Ingreso' GROUP BY fecha")
    ingresos_data = dict(cursor.fetchall())
    cursor.execute("SELECT fecha, SUM(monto) FROM caja WHERE tipo='Gasto' GROUP BY fecha")
    gastos_data = dict(cursor.fetchall())
    fechas_caja = sorted(list(set(ingresos_data.keys()).union(set(gastos_data.keys()))))
    ingresos_caja = [ingresos_data.get(f, 0) for f in fechas_caja]
    gastos_caja = [gastos_data.get(f, 0) for f in fechas_caja]

    cursor.execute("SELECT fecha, MAX(seguidores) FROM redes GROUP BY fecha")
    redes_data = dict(cursor.fetchall())
    fechas_redes = sorted(list(redes_data.keys()))
    ig_seguidores = [redes_data.get(f, 0) for f in fechas_redes]

    cursor.execute("SELECT id, fecha, tipo, descripcion, monto, metodo FROM caja ORDER BY id DESC")
    lista_caja = cursor.fetchall()

    cursor.execute("SELECT id, insumo, cantidad, unidad, minimo FROM stock")
    lista_stock = cursor.fetchall()

    edit_caja = None
    if edit_caja_id:
        cursor.execute("SELECT id, fecha, tipo, descripcion, monto, metodo FROM caja WHERE id=?", (edit_caja_id,))
        edit_caja = cursor.fetchone()

    conn.close()

    return render_template_string(HTML_TEMPLATE, tab=tab, 
                                  jornada_abierta=jornada_abierta,
                                  ventas_hoy_total=ventas_hoy_total, ventas_hoy_efectivo=ventas_hoy_efectivo, ventas_hoy_transferencia=ventas_hoy_transferencia,
                                  total_ingresos=total_ingresos, total_gastos=total_gastos, balance=balance,
                                  fechas_caja=json.dumps(fechas_caja), ingresos_caja=json.dumps(ingresos_caja), gastos_caja=json.dumps(gastos_caja),
                                  fechas_redes=json.dumps(fechas_redes), ig_seguidores=json.dumps(ig_seguidores), tk_seguidores=json.dumps([]),
                                  lista_caja=lista_caja, lista_stock=lista_stock, lista_redes=[],
                                  edit_caja=edit_caja, edit_stock=None, edit_redes=None)

@app.route('/abrir_jornada')
def abrir_jornada():
    if 'user_id' not in session: return redirect('/')
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jornadas (fecha, estado, efectivo_ventas, transferencia_ventas, total_gastos) VALUES (?, 'Abierta', 0, 0, 0)", (hoy_str,))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

@app.route('/cerrar_jornada')
def cerrar_jornada():
    if 'user_id' not in session: return redirect('/')
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND (metodo='Efectivo' OR metodo IS NULL)", (hoy_str,))
    efectivo = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Transferencia'", (hoy_str,))
    transferencia = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Gasto' AND fecha=?", (hoy_str,))
    gastos = cursor.fetchone()[0] or 0.0
    cursor.execute("UPDATE jornadas SET estado='Cerrada', efectivo_ventas=?, transferencia_ventas=?, total_gastos=? WHERE fecha=? AND estado='Abierta'", 
                   (efectivo, transferencia, gastos, hoy_str))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=dashboard')

@app.route('/agregar_caja', methods=['POST'])
def agregar_caja():
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO caja (fecha, tipo, descripcion, monto, metodo) VALUES (?, ?, ?, ?, ?)", 
                   (request.form['fecha'], request.form['tipo'], request.form['descripcion'], float(request.form['monto']), request.form['metodo']))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

@app.route('/editar_caja/<int:id>', methods=['POST'])
def editar_caja(id):
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE caja SET fecha=?, tipo=?, descripcion=?, monto=?, metodo=? WHERE id=?", 
                   (request.form['fecha'], request.form['tipo'], request.form['descripcion'], float(request.form['monto']), request.form['metodo'], id))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

@app.route('/eliminar_caja/<int:id>')
def eliminar_caja(id):
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM caja WHERE id=?", (id,))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

@app.route('/agregar_stock', methods=['POST'])
def agregar_stock():
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stock (insumo, cantidad, unidad, minimo) VALUES (?, ?, ?, ?)", 
                   (request.form['insumo'], float(request.form['cantidad']), request.form['unidad'], float(request.form['minimo'])))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=stock')

@app.route('/eliminar_stock/<int:id>')
def eliminar_stock(id):
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock WHERE id=?", (id,))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=stock')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
