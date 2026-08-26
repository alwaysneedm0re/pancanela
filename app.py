from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import sqlite3
import json
from datetime import datetime
from openai import OpenAI 

app = Flask(__name__)

# ==========================================
# 🔑 ZONA DE CLAVES API
# ==========================================
OPENAI_API_KEY = "sk-TU_CLAVE_DE_OPENAI_AQUI"
# ==========================================

def init_db():
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    
    # Tabla caja con campo 'metodo' (Efectivo / Transferencia)
    cursor.execute('''CREATE TABLE IF NOT EXISTS caja (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, 
        tipo TEXT, 
        descripcion TEXT, 
        monto REAL,
        metodo TEXT
    )''')
    
    # Tabla para control de jornadas (Abrir / Cerrar día)
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
<body class="bg-[#F9F8F6] text-[#1C1C1E] font-sans min-h-screen">

    <nav class="bg-white border-b border-[#E5E5EA] px-8 py-4 sticky top-0 z-50 shadow-sm">
        <div class="container mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 bg-[#1C1C1E] text-white rounded font-bold flex items-center justify-center text-sm">PC</div>
                <div>
                    <h1 class="text-base font-bold tracking-tight text-[#1C1C1E]">PAN CANELA <span class="text-[10px] font-medium text-[#636366] bg-[#E5E5EA] px-2 py-0.5 rounded ml-2">Sistema Activo</span></h1>
                </div>
            </div>
            <div class="flex flex-wrap gap-1 bg-[#F2F1EC] p-1 rounded-lg border border-[#E5E5EA]">
                <a href="/?tab=dashboard" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'dashboard' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Dashboard Analítico</a>
                <a href="/?tab=finanzas" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'finanzas' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Caja & Jornada</a>
                <a href="/?tab=stock" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'stock' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Insumos & Stock</a>
                <a href="/?tab=redes" class="px-4 py-1.5 rounded-md text-xs font-semibold transition {{ 'bg-white text-[#1C1C1E] shadow-sm' if tab == 'redes' else 'text-[#636366] hover:text-[#1C1C1E]' }}">Redes Ancladas</a>
            </div>
        </div>
    </nav>

    <main class="container mx-auto px-8 py-10">
        
        <!-- ================= PESTAÑA: DASHBOARD ================= -->
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

        <!-- Métricas del Día en Tiempo Real -->
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
                <div class="border-t border-[#E5E5EA] pt-4">
                    <label class="text-xs text-[#636366] font-medium mb-2 block">Consultas sobre finanzas:</label>
                    <div class="flex gap-2">
                        <input type="text" id="inputFinanzas" placeholder="Ej: ¿Cómo optimizo mis costos?" class="flex-1 bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        <button onclick="preguntarIA('inputFinanzas', 'respuestaFinanzas')" class="bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-2 px-4 rounded-lg text-xs transition">Consultar</button>
                    </div>
                    <div id="respuestaFinanzas" class="mt-3 text-xs text-[#3A3A3C] bg-[#F9F8F6] p-4 rounded-lg hidden border border-[#E5E5EA]"></div>
                </div>
            </div>

            <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm flex flex-col justify-between">
                <div>
                    <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Crecimiento de Comunidad en Redes</h3>
                    <div class="relative h-56 w-full mb-4">
                        <canvas id="redesChart"></canvas>
                    </div>
                </div>
                <div class="border-t border-[#E5E5EA] pt-4">
                    <label class="text-xs text-[#636366] font-medium mb-2 block">Consultas sobre marketing digital:</label>
                    <div class="flex gap-2">
                        <input type="text" id="inputRedes" placeholder="Ej: Ideas de contenido para Instagram" class="flex-1 bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        <button onclick="preguntarIA('inputRedes', 'respuestaRedes')" class="bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-2 px-4 rounded-lg text-xs transition">Consultar</button>
                    </div>
                    <div id="respuestaRedes" class="mt-3 text-xs text-[#3A3A3C] bg-[#F9F8F6] p-4 rounded-lg hidden border border-[#E5E5EA]"></div>
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

            async function preguntarIA(inputId, respuestaId) {
                const pregunta = document.getElementById(inputId).value;
                const cajaRespuesta = document.getElementById(respuestaId);
                if(!pregunta) return;
                cajaRespuesta.style.display = 'block';
                cajaRespuesta.innerHTML = '<span class="text-[#636366]">Procesando consulta...</span>';
                try {
                    const response = await fetch('/consultar_ia', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ pregunta: pregunta })
                    });
                    const data = await response.json();
                    cajaRespuesta.innerHTML = `<strong class="text-[#1C1C1E]">Respuesta del Analista:</strong> <br><br> ${data.respuesta}`;
                } catch (error) {
                    cajaRespuesta.innerHTML = '<span class="text-red-600">Error al conectar con el sistema.</span>';
                }
            }
        </script>
        
        <!-- ================= PESTAÑA: FINANZAS & JORNADA ================= -->
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
                <a href="/cerrar_jornada" onclick="return confirm('¿Seguro que deseas cerrar el día? Se guardará el consolidado de la jornada.');" class="bg-red-600 hover:bg-red-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg transition shadow-sm">🔒 Cerrar el Día</a>
                {% endif %}
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">
                    {{ 'Editar Movimiento' if edit_caja else 'Registrar Ingreso o Gasto' }}
                </h3>
                <form action="{{ url_for('editar_caja', id=edit_caja[0]) if edit_caja else '/agregar_caja' }}" method="POST" class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Fecha</label>
                            <input type="date" name="fecha" value="{{ edit_caja[1] if edit_caja else '' }}" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Tipo</label>
                            <select name="tipo" class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                                <option value="Ingreso" {{ 'selected' if edit_caja and edit_caja[2] == 'Ingreso' else '' }}>Ingreso</option>
                                <option value="Gasto" {{ 'selected' if edit_caja and edit_caja[2] == 'Gasto' else '' }}>Gasto</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Método de Pago</label>
                        <select name="metodo" class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                            <option value="Efectivo" {{ 'selected' if edit_caja and edit_caja[5] == 'Efectivo' else '' }}>Efectivo</option>
                            <option value="Transferencia" {{ 'selected' if edit_caja and edit_caja[5] == 'Transferencia' else '' }}>Transferencia</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Descripción</label>
                        <input type="text" name="descripcion" value="{{ edit_caja[3] if edit_caja else '' }}" placeholder="Ej: Venta mostrador" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Monto ($)</label>
                        <input type="number" step="any" name="monto" value="{{ edit_caja[4] if edit_caja else '' }}" placeholder="0.00" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
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
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Historial de Caja & Medios de Pago</h3>
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
                                <td class="p-2 text-[#636366]">{{ m[1] }}</td>
                                <td class="p-2 font-semibold {{ 'text-green-600' if m[2] == 'Ingreso' else 'text-red-600' }}">{{ m[2] }}</td>
                                <td class="p-2 font-medium text-blue-600">{{ m[5] if m[5] else 'Efectivo' }}</td>
                                <td class="p-2 text-[#1C1C1E]">{{ m[3] }}</td>
                                <td class="p-2 text-right font-bold text-[#1C1C1E]">${{ m[4] }}</td>
                                <td class="p-2 text-center space-x-2">
                                    <a href="/?tab=finanzas&edit_caja={{ m[0] }}" class="text-blue-600 font-medium hover:underline">Editar</a>
                                    <a href="/eliminar_caja/{{ m[0] }}" onclick="return confirm('¿Seguro que deseas eliminar este movimiento?');" class="text-red-600 font-medium hover:underline">Eliminar</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= PESTAÑA: STOCK ================= -->
        {% elif tab == 'stock' %}
        <div class="mb-8">
            <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Control de Insumos & Stock</h2>
            <p class="text-sm text-[#636366] mt-1">Gestión de inventario de materias primas y control de niveles críticos.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">
                    {{ 'Editar Insumo' if edit_stock else 'Agregar / Actualizar Insumo' }}
                </h3>
                <form action="{{ url_for('editar_stock', id=edit_stock[0]) if edit_stock else '/agregar_stock' }}" method="POST" class="space-y-4">
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Nombre Insumo</label>
                        <input type="text" name="insumo" value="{{ edit_stock[1] if edit_stock else '' }}" placeholder="Ej: Harina 000" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Cantidad Actual</label>
                        <input type="number" step="any" name="cantidad" value="{{ edit_stock[2] if edit_stock else '' }}" placeholder="0" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Unidad</label>
                            <input type="text" name="unidad" value="{{ edit_stock[3] if edit_stock else '' }}" placeholder="kg / litros" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                        <div>
                            <label class="text-xs text-[#636366] font-medium block mb-1">Stock Mínimo</label>
                            <input type="number" step="any" name="minimo" value="{{ edit_stock[4] if edit_stock else '' }}" placeholder="0" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <button type="submit" class="flex-1 bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-2.5 px-4 rounded-lg text-xs transition">Guardar Insumo</button>
                        {% if edit_stock %}
                        <a href="/?tab=stock" class="bg-[#E5E5EA] hover:bg-[#D1D1D6] text-[#1C1C1E] font-medium py-2.5 px-4 rounded-lg text-xs text-center transition">Cancelar</a>
                        {% endif %}
                    </div>
                </form>
            </div>

            <div class="lg:col-span-2 bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Inventario de Materias Primas</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-[#F9F8F6] text-[#636366] uppercase text-[10px]">
                            <tr>
                                <th class="p-3">Insumo</th>
                                <th class="p-3">Cantidad Disponible</th>
                                <th class="p-3">Stock Mínimo</th>
                                <th class="p-3">Estado</th>
                                <th class="p-3 text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-[#E5E5EA]">
                            {% for s in lista_stock %}
                            <tr class="hover:bg-[#F9F8F6]">
                                <td class="p-3 font-bold text-[#1C1C1E]">{{ s[1] }}</td>
                                <td class="p-3 text-[#1C1C1E]">{{ s[2] }} {{ s[3] }}</td>
                                <td class="p-3 text-[#636366]">{{ s[4] }} {{ s[3] }}</td>
                                <td class="p-3">
                                    {% if s[2] <= s[4] %}
                                    <span class="bg-red-100 text-red-700 px-2 py-0.5 rounded text-[10px] font-semibold">Crítico</span>
                                    {% else %}
                                    <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-[10px] font-semibold">Óptimo</span>
                                    {% endif %}
                                </td>
                                <td class="p-3 text-center space-x-2">
                                    <a href="/?tab=stock&edit_stock={{ s[0] }}" class="text-blue-600 font-medium hover:underline">Editar</a>
                                    <a href="/eliminar_stock/{{ s[0] }}" onclick="return confirm('¿Seguro que deseas eliminar este insumo?');" class="text-red-600 font-medium hover:underline">Eliminar</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= PESTAÑA: REDES ANCLADAS ================= -->
        {% elif tab == 'redes' %}
        <div class="mb-8">
            <h2 class="text-2xl font-bold tracking-tight text-[#1C1C1E]">Redes Ancladas & Métricas</h2>
            <p class="text-sm text-[#636366] mt-1">Seguimiento del crecimiento de seguidores e interacción en @pancanela.arg y TikTok.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <div class="bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">
                    {{ 'Editar Métrica' if edit_redes else 'Registrar Métrica Diaria' }}
                </h3>
                <form action="{{ url_for('editar_redes', id=edit_redes[0]) if edit_redes else '/agregar_redes' }}" method="POST" class="space-y-4">
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Fecha</label>
                        <input type="date" name="fecha" value="{{ edit_redes[1] if edit_redes else '' }}" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Plataforma</label>
                        <select name="plataforma" class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                            <option value="Instagram" {{ 'selected' if edit_redes and edit_redes[2] == 'Instagram' else '' }}>Instagram (@pancanela.arg)</option>
                            <option value="TikTok" {{ 'selected' if edit_redes and edit_redes[2] == 'TikTok' else '' }}>TikTok</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Total Seguidores</label>
                        <input type="number" name="seguidores" value="{{ edit_redes[3] if edit_redes else '' }}" placeholder="1250" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-[#636366] font-medium block mb-1">Tasa de Interacción (%)</label>
                        <input type="number" step="any" name="interaccion" value="{{ edit_redes[4] if edit_redes else '' }}" placeholder="5.5" required class="w-full bg-[#F9F8F6] border border-[#D1D1D6] rounded-lg px-3 py-2 text-xs text-[#1C1C1E] outline-none">
                    </div>
                    <div class="flex gap-2">
                        <button type="submit" class="flex-1 bg-[#1C1C1E] hover:bg-[#3A3A3C] text-white font-medium py-2.5 px-4 rounded-lg text-xs transition">Guardar Métrica</button>
                        {% if edit_redes %}
                        <a href="/?tab=redes" class="bg-[#E5E5EA] hover:bg-[#D1D1D6] text-[#1C1C1E] font-medium py-2.5 px-4 rounded-lg text-xs text-center transition">Cancelar</a>
                        {% endif %}
                    </div>
                </form>
            </div>

            <div class="lg:col-span-2 bg-white p-6 rounded-xl border border-[#E5E5EA] shadow-sm">
                <h3 class="text-sm font-bold text-[#1C1C1E] mb-4 uppercase tracking-wider">Historial de Rendimiento en Redes</h3>
                <div class="overflow-x-auto max-h-96 overflow-y-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-[#F9F8F6] text-[#636366] uppercase text-[10px]">
                            <tr>
                                <th class="p-3">Fecha</th>
                                <th class="p-3">Plataforma</th>
                                <th class="p-3">Seguidores</th>
                                <th class="p-3">Interacción</th>
                                <th class="p-3 text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-[#E5E5EA]">
                            {% for r in lista_redes %}
                            <tr class="hover:bg-[#F9F8F6]">
                                <td class="p-3 text-[#636366]">{{ r[1] }}</td>
                                <td class="p-3 font-bold text-[#1C1C1E]">{{ r[2] }}</td>
                                <td class="p-3 text-[#1C1C1E]">{{ "{:,}".format(r[3]).replace(',', '.') }}</td>
                                <td class="p-3 text-green-600 font-semibold">{{ r[4] }}%</td>
                                <td class="p-3 text-center space-x-2">
                                    <a href="/?tab=redes&edit_redes={{ r[0] }}" class="text-blue-600 font-medium hover:underline">Editar</a>
                                    <a href="/eliminar_redes/{{ r[0] }}" onclick="return confirm('¿Seguro que deseas eliminar esta métrica?');" class="text-red-600 font-medium hover:underline">Eliminar</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}

    </main>
</body>
</html>
'''

@app.route('/')
def index():
    tab = request.args.get('tab', 'dashboard')
    edit_caja_id = request.args.get('edit_caja')
    edit_stock_id = request.args.get('edit_stock')
    edit_redes_id = request.args.get('edit_redes')

    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    
    # Estado de Jornada
    cursor.execute("SELECT COUNT(*) FROM jornadas WHERE estado='Abierta'")
    jornada_abierta = cursor.fetchone()[0] > 0

    # Calcular ventas de hoy en tiempo real (Fecha actual del sistema)
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND (metodo='Efectivo' OR metodo IS NULL)", (hoy_str,))
    ventas_hoy_efectivo = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Transferencia'", (hoy_str,))
    ventas_hoy_transferencia = cursor.fetchone()[0] or 0.0

    ventas_hoy_total = ventas_hoy_efectivo + ventas_hoy_transferencia

    # Totales generales Dashboard
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

    cursor.execute("SELECT fecha, MAX(seguidores) FROM redes WHERE plataforma='Instagram' GROUP BY fecha")
    ig_data = dict(cursor.fetchall())
    cursor.execute("SELECT fecha, MAX(seguidores) FROM redes WHERE plataforma='TikTok' GROUP BY fecha")
    tk_data = dict(cursor.fetchall())
    fechas_redes = sorted(list(set(ig_data.keys()).union(set(tk_data.keys()))))
    ig_seguidores = [ig_data.get(f, 0) for f in fechas_redes]
    tk_seguidores = [tk_data.get(f, 0) for f in fechas_redes]

    # Listados
    cursor.execute("SELECT id, fecha, tipo, descripcion, monto, metodo FROM caja ORDER BY id DESC")
    lista_caja = cursor.fetchall()

    cursor.execute("SELECT id, insumo, cantidad, unidad, minimo FROM stock")
    lista_stock = cursor.fetchall()

    cursor.execute("SELECT id, fecha, plataforma, seguidores, interaccion FROM redes ORDER BY id DESC")
    lista_redes = cursor.fetchall()

    edit_caja = None
    if edit_caja_id:
        cursor.execute("SELECT id, fecha, tipo, descripcion, monto, metodo FROM caja WHERE id=?", (edit_caja_id,))
        edit_caja = cursor.fetchone()

    edit_stock = None
    if edit_stock_id:
        cursor.execute("SELECT id, insumo, cantidad, unidad, minimo FROM stock WHERE id=?", (edit_stock_id,))
        edit_stock = cursor.fetchone()

    edit_redes = None
    if edit_redes_id:
        cursor.execute("SELECT id, fecha, plataforma, seguidores, interaccion FROM redes WHERE id=?", (edit_redes_id,))
        edit_redes = cursor.fetchone()

    conn.close()

    return render_template_string(HTML_TEMPLATE, tab=tab, 
                                  jornada_abierta=jornada_abierta,
                                  ventas_hoy_total=ventas_hoy_total, ventas_hoy_efectivo=ventas_hoy_efectivo, ventas_hoy_transferencia=ventas_hoy_transferencia,
                                  total_ingresos=total_ingresos, total_gastos=total_gastos, balance=balance,
                                  fechas_caja=json.dumps(fechas_caja), ingresos_caja=json.dumps(ingresos_caja), gastos_caja=json.dumps(gastos_caja),
                                  fechas_redes=json.dumps(fechas_redes), ig_seguidores=json.dumps(ig_seguidores), tk_seguidores=json.dumps(tk_seguidores),
                                  lista_caja=lista_caja, lista_stock=lista_stock, lista_redes=lista_redes,
                                  edit_caja=edit_caja, edit_stock=edit_stock, edit_redes=edit_redes)

@app.route('/abrir_jornada')
def abrir_jornada():
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jornadas (fecha, estado, efectivo_ventas, transferencia_ventas, total_gastos) VALUES (?, 'Abierta', 0, 0, 0)", (hoy_str,))
    conn.commit()
    conn.close()
    return redirect('/?tab=finanzas')

@app.route('/cerrar_jornada')
def cerrar_jornada():
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    
    # Calcular totales del día de hoy
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND (metodo='Efectivo' OR metodo IS NULL)", (hoy_str,))
    efectivo = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Ingreso' AND fecha=? AND metodo='Transferencia'", (hoy_str,))
    transferencia = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(monto) FROM caja WHERE tipo='Gasto' AND fecha=?", (hoy_str,))
    gastos = cursor.fetchone()[0] or 0.0

    # Actualizar jornada a Cerrada con sus totales
    cursor.execute("UPDATE jornadas SET estado='Cerrada', efectivo_ventas=?, transferencia_ventas=?, total_gastos=? WHERE fecha=? AND estado='Abierta'", 
                   (efectivo, transferencia, gastos, hoy_str))
    conn.commit()
    conn.close()
    return redirect('/?tab=dashboard')

@app.route('/agregar_caja', methods=['POST'])
def agregar_caja():
    fecha = request.form['fecha']
    tipo = request.form['tipo']
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    metodo = request.form['metodo']
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO caja (fecha, tipo, descripcion, monto, metodo) VALUES (?, ?, ?, ?, ?)", (fecha, tipo, descripcion, monto, metodo))
    conn.commit()
    conn.close()
    return redirect('/?tab=finanzas')

@app.route('/editar_caja/<int:id>', methods=['POST'])
def editar_caja(id):
    fecha = request.form['fecha']
    tipo = request.form['tipo']
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    metodo = request.form['metodo']
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE caja SET fecha=?, tipo=?, descripcion=?, monto=?, metodo=? WHERE id=?", (fecha, tipo, descripcion, monto, metodo, id))
    conn.commit()
    conn.close()
    return redirect('/?tab=finanzas')

@app.route('/eliminar_caja/<int:id>')
def eliminar_caja(id):
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM caja WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/?tab=finanzas')

@app.route('/agregar_stock', methods=['POST'])
def agregar_stock():
    insumo = request.form['insumo']
    cantidad = float(request.form['cantidad'])
    unidad = request.form['unidad']
    minimo = float(request.form['minimo'])
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stock (insumo, cantidad, unidad, minimo) VALUES (?, ?, ?, ?)", (insumo, cantidad, unidad, minimo))
    conn.commit()
    conn.close()
    return redirect('/?tab=stock')

@app.route('/editar_stock/<int:id>', methods=['POST'])
def editar_stock(id):
    insumo = request.form['insumo']
    cantidad = float(request.form['cantidad'])
    unidad = request.form['unidad']
    minimo = float(request.form['minimo'])
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE stock SET insumo=?, cantidad=?, unidad=?, minimo=? WHERE id=?", (insumo, cantidad, unidad, minimo, id))
    conn.commit()
    conn.close()
    return redirect('/?tab=stock')

@app.route('/eliminar_stock/<int:id>')
def eliminar_stock(id):
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/?tab=stock')

@app.route('/agregar_redes', methods=['POST'])
def agregar_redes():
    fecha = request.form['fecha']
    plataforma = request.form['plataforma']
    seguidores = int(request.form['seguidores'])
    interaccion = float(request.form['interaccion'])
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO redes (fecha, plataforma, seguidores, interaccion) VALUES (?, ?, ?, ?)", (fecha, plataforma, seguidores, interaccion))
    conn.commit()
    conn.close()
    return redirect('/?tab=redes')

@app.route('/editar_redes/<int:id>', methods=['POST'])
def editar_redes(id):
    fecha = request.form['fecha']
    plataforma = request.form['plataforma']
    seguidores = int(request.form['seguidores'])
    interaccion = float(request.form['interaccion'])
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE redes SET fecha=?, plataforma=?, seguidores=?, interaccion=? WHERE id=?", (fecha, plataforma, seguidores, interaccion, id))
    conn.commit()
    conn.close()
    return redirect('/?tab=redes')

@app.route('/eliminar_redes/<int:id>')
def eliminar_redes(id):
    conn = sqlite3.connect('pancanela.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM redes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/?tab=redes')

@app.route('/consultar_ia', methods=['POST'])
def consultar_ia():
    data = request.get_json()
    pregunta = data.get('pregunta', '')
    if not OPENAI_API_KEY.startswith("sk-"):
        return jsonify({"respuesta": "API Key de OpenAI no configurada."})
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un perito en negocios, experto en growth hacking y marketing gastronómico. Asesoras a 'Pan Canela' (@pancanela.arg), una panadería ubicada en Mendoza, Argentina. Da consejos prácticos, directos, cortos y aplicables a nivel local para aumentar las ventas y optimizar el patrimonio."},
                {"role": "user", "content": pregunta}
            ]
        )
        return jsonify({"respuesta": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"respuesta": f"Error de conexión con IA: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
