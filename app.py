from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, Response
import sqlite3
import os
import json
import base64
import requests
import csv
from io import StringIO
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

app = Flask(__name__)
app.secret_key = 'erp_saas_ultra_secure_2026'

# ==========================================
# 🔑 ZONA DE CLAVES API
# ==========================================
OPENAI_API_KEY = "sk-TU_CLAVE_DE_OPENAI_AQUI"
# ==========================================

# Configuración para auto-backup en GitHub
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')

def sincronizar_con_github():
    if not GITHUB_TOKEN or not GITHUB_REPO: return 
    db_file = 'erp_gastronomico.db'
    if not os.path.exists(db_file): return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{db_file}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

    try:
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None
        with open(db_file, "rb") as f:
            content_encoded = base64.b64encode(f.read()).decode('utf-8')
        data = {
            "message": f"Auto-backup SaaS DB {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content_encoded,
            "branch": "main"
        }
        if sha: data["sha"] = sha
        requests.put(url, headers=headers, json=data)
    except Exception as e:
        print(f"Error en auto-backup: {e}")

def get_db_connection():
    conn = sqlite3.connect('erp_gastronomico.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Arquitectura Multi-Empresa (Marca Blanca)
    cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        iniciales TEXT NOT NULL
    )''')

    # 2. Sistema de Roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT NOT NULL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS caja (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        empresa_id INTEGER NOT NULL,
        fecha TEXT, tipo TEXT, descripcion TEXT, monto REAL, metodo TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        empresa_id INTEGER NOT NULL,
        insumo TEXT, cantidad REAL, unidad TEXT, minimo REAL
    )''')

    # 3. Escandallo Automático (Recetas conectadas a Insumos)
    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        empresa_id INTEGER NOT NULL,
        producto TEXT, 
        precio_venta REAL,
        insumo_id INTEGER,
        cantidad_descuento REAL
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= PLANTILLA HTML =================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ERP Gastronómico | {{ session.get('empresa_nombre', 'SaaS') }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        function toggleAuth() {
            document.getElementById('loginBox').classList.toggle('hidden');
            document.getElementById('registerBox').classList.toggle('hidden');
        }
    </script>
</head>
<body class="bg-[#F9F8F6] text-[#1C1C1E] font-sans min-h-screen flex flex-col justify-between">

    {% if not session.get('user_id') %}
    <!-- ================= PANTALLA DE AUTH / SAAS ================= -->
    <div class="flex items-center justify-center min-h-screen px-4">
        <div class="bg-white p-8 rounded-2xl border border-[#E5E5EA] shadow-sm w-full max-w-md">
            <div class="text-center mb-6">
                <div class="w-12 h-12 bg-[#1C1C1E] text-white rounded-xl font-bold flex items-center justify-center text-lg mx-auto mb-3 shadow">ERP</div>
                <h1 class="text-xl font-bold tracking-tight text-[#1C1C1E]">SISTEMA GESTIÓN SAAS</h1>
            </div>
            
            {% if error %}<div class="mb-4 bg-red-50 border border-red-200 text-red-600 text-xs p-3 rounded-lg text-center font-medium">{{ error }}</div>{% endif %}
            {% if success %}<div class="mb-4 bg-green-50 border border-green-200 text-green-700 text-xs p-3 rounded-lg text-center font-medium">{{ success }}</div>{% endif %}

            <div id="loginBox">
                <form action="/login" method="POST" class="space-y-4">
                    <input type="text" name="username" placeholder="Usuario" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs outline-none">
                    <input type="password" name="password" placeholder="Contraseña" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs outline-none">
                    <button type="submit" class="w-full bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-3 rounded-lg text-xs shadow-sm transition">Iniciar Sesión</button>
                </form>
                <div class="mt-4 text-center">
                    <button onclick="toggleAuth()" class="text-xs text-blue-600 hover:underline">Registrar mi Empresa (Nueva Cuenta)</button>
                </div>
            </div>

            <div id="registerBox" class="hidden">
                <form action="/register" method="POST" class="space-y-4">
                    <input type="text" name="empresa_nombre" placeholder="Nombre de tu Empresa (Ej: Pan Canela)" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs outline-none">
                    <input type="text" name="username" placeholder="Usuario Admin" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs outline-none">
                    <input type="password" name="password" placeholder="Contraseña" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2.5 text-xs outline-none">
                    <button type="submit" class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-3 rounded-lg text-xs shadow-sm transition">Crear Empresa</button>
                </form>
                <div class="mt-4 text-center">
                    <button onclick="toggleAuth()" class="text-xs text-blue-600 hover:underline">Ya tengo cuenta. Volver al Login</button>
                </div>
            </div>
        </div>
    </div>

    {% else %}
    <!-- ================= SISTEMA PRINCIPAL (MULTI-TENANT) ================= -->
    <div>
        <nav class="bg-white border-b border-[#E5E5EA] px-8 py-4 sticky top-0 z-50 shadow-sm">
            <div class="container mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-[#1C1C1E] text-white rounded font-bold flex items-center justify-center text-sm shadow-sm">{{ session.get('empresa_iniciales') }}</div>
                    <div>
                        <h1 class="text-base font-bold tracking-tight text-[#1C1C1E] uppercase">{{ session.get('empresa_nombre') }}</h1>
                        <p class="text-[10px] font-medium text-[#636366]">Operador: {{ session.get('username') }} | Rol: <span class="uppercase text-[#1C1C1E]">{{ session.get('rol') }}</span></p>
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex flex-wrap gap-1 bg-[#F2F1EC] p-1 rounded-lg border border-[#E5E5EA]">
                        {% if session.rol == 'admin' %}
                        <a href="/?tab=dashboard" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'dashboard' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Dashboard</a>
                        {% endif %}
                        <a href="/?tab=finanzas" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'finanzas' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Caja Rápida</a>
                        {% if session.rol == 'admin' %}
                        <a href="/?tab=stock" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'stock' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Recetas & Stock</a>
                        <a href="/?tab=config" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'config' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Configuración</a>
                        {% endif %}
                    </div>
                    <a href="/logout" class="bg-red-50 hover:bg-red-100 text-red-600 font-semibold px-3 py-1.5 rounded-lg text-xs transition border border-red-200">Salir</a>
                </div>
            </div>
        </nav>

        <main class="container mx-auto px-8 py-10">
            
            <!-- ====== PESTAÑA: DASHBOARD (Solo Admin) ====== -->
            {% if tab == 'dashboard' and session.rol == 'admin' %}
            <div class="mb-8 flex justify-between items-center">
                <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Rendimiento General</h2>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold text-[#636366] uppercase">Ingresos Históricos</p>
                    <p class="text-3xl font-extrabold text-[#1C1C1E] mt-2">${{ total_ingresos }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold text-[#636366] uppercase">Gastos Históricos</p>
                    <p class="text-3xl font-extrabold text-[#1C1C1E] mt-2">${{ total_gastos }}</p>
                </div>
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <p class="text-xs font-semibold text-[#636366] uppercase">Balance Neto</p>
                    <p class="text-3xl font-extrabold text-[#1C1C1E] mt-2">${{ balance }}</p>
                </div>
            </div>

            <!-- ====== PESTAÑA: FINANZAS (Acceso Admin y Cajero) ====== -->
            {% elif tab == 'finanzas' %}
            <div class="mb-8 flex justify-between items-center">
                <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Terminal de Caja</h2>
                {% if session.rol == 'admin' %}
                <!-- 4. Botón de Exportación Contable -->
                <a href="/exportar_caja" class="bg-green-600 hover:bg-green-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition shadow-sm">📄 Exportar a Excel (CSV)</a>
                {% endif %}
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                <div class="space-y-6">
                    <!-- Registro Manual -->
                    <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                        <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase">Movimiento Manual</h3>
                        <form action="/agregar_caja" method="POST" class="space-y-4">
                            <input type="date" name="fecha" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-full">
                            <div class="flex gap-2">
                                <select name="tipo" class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/2"><option value="Ingreso">Ingreso</option><option value="Gasto">Gasto</option></select>
                                <select name="metodo" class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/2"><option value="Efectivo">Efectivo</option><option value="Transferencia">Transferencia</option></select>
                            </div>
                            <input type="text" name="descripcion" placeholder="Descripción" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-full">
                            <input type="number" step="any" name="monto" placeholder="Monto Total" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-full">
                            <button type="submit" class="w-full bg-[#1C1C1E] text-white font-medium py-2.5 rounded-lg text-xs">Guardar Movimiento</button>
                        </form>
                    </div>

                    <!-- 3. Escandallo: Venta de Producto Automatizada -->
                    <div class="bg-[#F2F1EC] p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                        <h3 class="text-sm font-bold text-[#1C1C1E] mb-1 uppercase">Venta Rápida (Escandallo)</h3>
                        <p class="text-[10px] text-[#636366] mb-4">Ingresa ventas de productos. Descuenta el stock automáticamente.</p>
                        <form action="/vender_producto" method="POST" class="space-y-4">
                            <input type="date" name="fecha" required class="bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-full">
                            <select name="receta_id" required class="bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-full">
                                <option value="">Selecciona un Producto...</option>
                                {% for r in lista_recetas %}
                                <option value="{{ r['id'] }}">{{ r['producto'] }} - ${{ r['precio_venta'] }}</option>
                                {% endfor %}
                            </select>
                            <div class="flex gap-2">
                                <input type="number" step="1" name="cantidad" placeholder="Cant." required class="bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/3">
                                <select name="metodo" class="bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-2/3"><option value="Efectivo">Efectivo</option><option value="Transferencia">Transferencia</option></select>
                            </div>
                            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg text-xs transition">Registrar Venta Automática</button>
                        </form>
                    </div>
                </div>

                <div class="lg:col-span-2 bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase">Historial de Caja</h3>
                    <div class="overflow-x-auto max-h-[550px] overflow-y-auto">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-[#F9F8F6] text-[#636366] uppercase text-[10px] sticky top-0">
                                <tr>
                                    <th class="p-2">Fecha</th>
                                    <th class="p-2">Tipo</th>
                                    <th class="p-2">Descripción</th>
                                    <th class="p-2 text-right">Monto</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-[#E5E5EA]">
                                {% for m in lista_caja %}
                                <tr class="hover:bg-[#F9F8F6]">
                                    <td class="p-2 text-[#636366]">{{ m['fecha'] }}</td>
                                    <td class="p-2 font-semibold {{ 'text-green-600' if m['tipo'] == 'Ingreso' else 'text-red-600' }}">{{ m['tipo'] }} ({{ m['metodo'] }})</td>
                                    <td class="p-2 text-[#1C1C1E]">{{ m['descripcion'] }}</td>
                                    <td class="p-2 text-right font-bold text-[#1C1C1E]">${{ m['monto'] }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ====== PESTAÑA: STOCK & RECETAS (Solo Admin) ====== -->
            {% elif tab == 'stock' and session.rol == 'admin' %}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                <!-- Inventario -->
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase">Cargar Materia Prima</h3>
                    <form action="/agregar_stock" method="POST" class="space-y-4 mb-6">
                        <div class="flex gap-2">
                            <input type="text" name="insumo" placeholder="Nombre Insumo" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-2/3">
                            <input type="number" step="any" name="cantidad" placeholder="Cant." required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/3">
                        </div>
                        <div class="flex gap-2">
                            <input type="text" name="unidad" placeholder="Unidad (kg, u)" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/2">
                            <input type="number" step="any" name="minimo" placeholder="Mínimo" required class="bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs w-1/2">
                        </div>
                        <button type="submit" class="w-full bg-[#1C1C1E] text-white py-2 rounded-lg text-xs">Guardar Insumo</button>
                    </form>
                    <div class="overflow-x-auto max-h-64 overflow-y-auto">
                        <table class="w-full text-left text-xs border-t border-[#E5E5EA] pt-2">
                            {% for s in lista_stock %}
                            <tr class="border-b border-[#F2F1EC]">
                                <td class="py-2 font-bold">{{ s['insumo'] }}</td>
                                <td class="py-2 {{ 'text-red-600 font-bold' if s['cantidad'] <= s['minimo'] else '' }}">{{ s['cantidad'] }}{{ s['unidad'] }}</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                </div>

                <!-- Recetas y Escandallo -->
                <div class="bg-[#F2F1EC] p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-1 uppercase">Fichas de Productos (Escandallo)</h3>
                    <p class="text-[10px] text-[#636366] mb-4">Vincula productos al stock para descontarlos en cada venta.</p>
                    <form action="/agregar_receta" method="POST" class="space-y-4 mb-6">
                        <input type="text" name="producto" placeholder="Nombre (Ej: Docena Medialunas)" required class="w-full bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs">
                        <input type="number" step="any" name="precio_venta" placeholder="Precio de Venta ($)" required class="w-full bg-white border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs">
                        <div class="p-3 border border-blue-200 bg-blue-50 rounded-lg space-y-2">
                            <label class="text-[10px] font-bold text-blue-800 uppercase block">Configuración de Descuento Automático</label>
                            <select name="insumo_id" required class="w-full bg-white border border-blue-300 rounded-lg px-3 py-2 text-xs">
                                <option value="">Selecciona materia prima a descontar...</option>
                                {% for s in lista_stock %}
                                <option value="{{ s['id'] }}">{{ s['insumo'] }}</option>
                                {% endfor %}
                            </select>
                            <input type="number" step="any" name="cantidad_descuento" placeholder="Cantidad que gasta 1 unidad de este producto" required class="w-full bg-white border border-blue-300 rounded-lg px-3 py-2 text-xs">
                        </div>
                        <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-lg text-xs">Guardar Receta</button>
                    </form>
                    <div class="overflow-x-auto max-h-64 overflow-y-auto">
                        <table class="w-full text-left text-[10px] border-t border-[#E5E5EA] pt-2">
                            {% for r in lista_recetas %}
                            <tr class="border-b border-[#D1D1D6]">
                                <td class="py-2 font-bold">{{ r['producto'] }} (${{ r['precio_venta'] }})</td>
                                <td class="py-2 text-[#636366]">Descuenta: {{ r['cantidad_descuento'] }} del ID: {{ r['insumo_id'] }}</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                </div>
            </div>

            <!-- ====== PESTAÑA: CONFIGURACIÓN / MARCA BLANCA (Solo Admin) ====== -->
            {% elif tab == 'config' and session.rol == 'admin' %}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                <!-- 5. Marca Blanca -->
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase">Personalización (Marca Blanca)</h3>
                    <form action="/update_empresa" method="POST" class="space-y-4">
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Nombre de la Empresa</label>
                            <input type="text" name="nombre" value="{{ session.get('empresa_nombre') }}" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs">
                        </div>
                        <button type="submit" class="w-full bg-[#1C1C1E] text-white py-2 rounded-lg text-xs">Actualizar Nombre</button>
                    </form>
                </div>
                
                <!-- 2. Roles: Agregar Empleado -->
                <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase">Crear Usuario Cajero</h3>
                    <p class="text-[10px] text-[#636366] mb-4">Los cajeros solo pueden registrar ventas y ver stock.</p>
                    <form action="/crear_cajero" method="POST" class="space-y-4">
                        <input type="text" name="username" placeholder="Nuevo Usuario Empleado" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs">
                        <input type="password" name="password" placeholder="Contraseña Empleado" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs">
                        <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-lg text-xs">Registrar Empleado</button>
                    </form>
                </div>
            </div>
            {% endif %}

        </main>
    </div>
    {% endif %}
</body>
</html>
'''

# ================= RUTAS DE AUTENTICACIÓN (SAAS) =================

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Hacemos JOIN para traer los datos de la empresa matriz (Multi-tenant)
    cursor.execute('''
        SELECT u.id, u.username, u.password, u.rol, u.empresa_id, e.nombre as empresa_nombre, e.iniciales 
        FROM usuarios u
        JOIN empresas e ON u.empresa_id = e.id
        WHERE u.username = ?
    ''', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['rol'] = user['rol']
        session['empresa_id'] = user['empresa_id']
        session['empresa_nombre'] = user['empresa_nombre']
        session['empresa_iniciales'] = user['iniciales']
        return redirect('/?tab=finanzas' if user['rol'] == 'cajero' else '/?tab=dashboard')
    else:
        return render_template_string(HTML_TEMPLATE, error="Usuario o contraseña incorrectos.")

@app.route('/register', methods=['POST'])
def register():
    empresa_nombre = request.form['empresa_nombre']
    iniciales = empresa_nombre[:2].upper()
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return render_template_string(HTML_TEMPLATE, error="El usuario ya está en uso.")
    
    # Crea empresa y usuario admin (SaaS flow)
    cursor.execute("INSERT INTO empresas (nombre, iniciales) VALUES (?, ?)", (empresa_nombre, iniciales))
    empresa_id = cursor.lastrowid
    hashed_pw = generate_password_hash(password)
    cursor.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (?, ?, ?, 'admin')", (empresa_id, username, hashed_pw))
    
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return render_template_string(HTML_TEMPLATE, success="Empresa registrada con éxito. Inicia sesión.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ================= RUTAS DEL PANEL =================

@app.route('/')
def index():
    if 'user_id' not in session: return render_template_string(HTML_TEMPLATE)

    tab = request.args.get('tab', 'dashboard')
    empresa_id = session['empresa_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Dashboard Metrics
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND empresa_id=?", (empresa_id,))
    total_ingresos = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Gasto' AND empresa_id=?", (empresa_id,))
    total_gastos = cursor.fetchone()[0] or 0.0
    balance = total_ingresos - total_gastos

    hoy_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Efectivo' AND empresa_id=?", (hoy_str, empresa_id))
    ventas_hoy_efectivo = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Transferencia' AND empresa_id=?", (hoy_str, empresa_id))
    ventas_hoy_transferencia = cursor.fetchone()[0] or 0.0
    ventas_hoy_total = ventas_hoy_efectivo + ventas_hoy_transferencia

    # Data lists
    cursor.execute("SELECT * FROM caja WHERE empresa_id=? ORDER BY id DESC", (empresa_id,))
    lista_caja = cursor.fetchall()

    cursor.execute("SELECT * FROM stock WHERE empresa_id=?", (empresa_id,))
    lista_stock = cursor.fetchall()

    cursor.execute("SELECT * FROM recetas WHERE empresa_id=?", (empresa_id,))
    lista_recetas = cursor.fetchall()
    
    conn.close()

    return render_template_string(HTML_TEMPLATE, tab=tab, 
                                  total_ingresos=total_ingresos, total_gastos=total_gastos, balance=balance,
                                  ventas_hoy_total=ventas_hoy_total, ventas_hoy_efectivo=ventas_hoy_efectivo, ventas_hoy_transferencia=ventas_hoy_transferencia,
                                  lista_caja=lista_caja, lista_stock=lista_stock, lista_recetas=lista_recetas)

@app.route('/agregar_caja', methods=['POST'])
def agregar_caja():
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO caja (empresa_id, fecha, tipo, descripcion, monto, metodo) VALUES (?, ?, ?, ?, ?, ?)", 
                   (session['empresa_id'], request.form['fecha'], request.form['tipo'], request.form['descripcion'], float(request.form['monto']), request.form['metodo']))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

# 3. Escandallo Automático: Ruta para descontar stock al vender
@app.route('/vender_producto', methods=['POST'])
def vender_producto():
    if 'user_id' not in session: return redirect('/')
    fecha = request.form['fecha']
    receta_id = int(request.form['receta_id'])
    cantidad_vendida = float(request.form['cantidad'])
    metodo = request.form['metodo']
    empresa_id = session['empresa_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtenemos los detalles de la receta y qué insumo descuenta
    cursor.execute("SELECT producto, precio_venta, insumo_id, cantidad_descuento FROM recetas WHERE id=? AND empresa_id=?", (receta_id, empresa_id))
    receta = cursor.fetchone()
    
    if receta:
        total_ingreso = receta['precio_venta'] * cantidad_vendida
        descripcion = f"Venta automatizada: {int(cantidad_vendida)}x {receta['producto']}"
        
        # Agregamos ingreso a caja
        cursor.execute("INSERT INTO caja (empresa_id, fecha, tipo, descripcion, monto, metodo) VALUES (?, ?, 'Ingreso', ?, ?, ?)", 
                       (empresa_id, fecha, descripcion, total_ingreso, metodo))
        
        # Descontamos el stock de manera automática (Escandallo)
        total_descuento = receta['cantidad_descuento'] * cantidad_vendida
        cursor.execute("UPDATE stock SET cantidad = cantidad - ? WHERE id = ? AND empresa_id=?", (total_descuento, receta['insumo_id'], empresa_id))
        
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=finanzas')

@app.route('/agregar_stock', methods=['POST'])
def agregar_stock():
    if session.get('rol') != 'admin': return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stock (empresa_id, insumo, cantidad, unidad, minimo) VALUES (?, ?, ?, ?, ?)", 
                   (session['empresa_id'], request.form['insumo'], float(request.form['cantidad']), request.form['unidad'], float(request.form['minimo'])))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=stock')

@app.route('/agregar_receta', methods=['POST'])
def agregar_receta():
    if session.get('rol') != 'admin': return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO recetas (empresa_id, producto, precio_venta, insumo_id, cantidad_descuento) VALUES (?, ?, ?, ?, ?)", 
                   (session['empresa_id'], request.form['producto'], float(request.form['precio_venta']), int(request.form['insumo_id']), float(request.form['cantidad_descuento'])))
    conn.commit()
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=stock')

@app.route('/crear_cajero', methods=['POST'])
def crear_cajero():
    if session.get('rol') != 'admin': return redirect('/')
    hashed_pw = generate_password_hash(request.form['password'])
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (?, ?, ?, 'cajero')", 
                       (session['empresa_id'], request.form['username'], hashed_pw))
        conn.commit()
    except: pass
    conn.close()
    sincronizar_con_github()
    return redirect('/?tab=config')

@app.route('/update_empresa', methods=['POST'])
def update_empresa():
    if session.get('rol') != 'admin': return redirect('/')
    nuevo_nombre = request.form['nombre']
    iniciales = nuevo_nombre[:2].upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE empresas SET nombre=?, iniciales=? WHERE id=?", (nuevo_nombre, iniciales, session['empresa_id']))
    conn.commit()
    conn.close()
    session['empresa_nombre'] = nuevo_nombre
    session['empresa_iniciales'] = iniciales
    sincronizar_con_github()
    return redirect('/?tab=config')

# 4. Función Exclusiva de Exportación para Contadores
@app.route('/exportar_caja')
def exportar_caja():
    if session.get('rol') != 'admin': return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fecha, tipo, metodo, descripcion, monto FROM caja WHERE empresa_id=? ORDER BY fecha DESC", (session['empresa_id'],))
    data = cursor.fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Fecha', 'Tipo', 'Medio de Pago', 'Descripcion', 'Monto ($)'])
    for row in data:
        cw.writerow([row['fecha'], row['tipo'], row['metodo'] or 'Efectivo', row['descripcion'], row['monto']])
    
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=resumen_contable_{session['empresa_nombre']}.csv"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
