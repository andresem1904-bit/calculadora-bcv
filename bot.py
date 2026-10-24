import os
import requests
import asyncio
import json
import random
import string
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# === CONFIGURACIÓN ===
TOKEN = "8550226144:AAFlJ3-Twt_pVVmGC348fIVjp2XiUpzWE7c"
ADMIN_ID = 7060767981
ADMIN_USERNAME = "@Sjw0518"
DB_FILE = "datos.json"
# =====================

BANCOS = {
    "Banesco": {"code": "Banesco", "emoji": "🟢"},
    "Banco de Venezuela": {"code": "BancodeVenezuela", "emoji": "🔴"},
    "Mercantil": {"code": "Mercantil", "emoji": "🔵"},
    "Provincial": {"code": "Provincial", "emoji": "🟦"},
    "Bancamiga": {"code": "Bancamiga", "emoji": "🟣"},
    "Banco Digital de los Trabajadores": {"code": "BancoBicentenario", "emoji": "🟠"}
}

# --- BASE DE DATOS LOCAL ---
def cargar_db():
    if not os.path.exists(DB_FILE):
        return {"usuarios": {}, "keys": {}}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def guardar_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

def tiene_creditos(user_id):
    db = cargar_db()
    uid = str(user_id)
    if uid in db["usuarios"] and db["usuarios"][uid] > 0:
        return True
    return False

def descontar_credito(user_id):
    db = cargar_db()
    uid = str(user_id)
    if uid in db["usuarios"] and db["usuarios"][uid] > 0:
        db["usuarios"][uid] -= 1
        guardar_db(db)
        return db["usuarios"][uid]
    return 0

# --- SERVIDOR WEB ---
app_web = Flask(__name__)
@app_web.route('/')
def home():
    return "El bot del BCV y Binance (SaaS) está funcionando 24/7."

def iniciar_servidor():
    puerto = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=puerto, use_reloader=False)

def mantener_vivo():
    hilo = Thread(target=iniciar_servidor)
    hilo.daemon = True
    hilo.start()

# --- FUNCIONES DE BÚSQUEDA ---
def obtener_tasa_bcv():
    try:
        url = "https://rates.dolarvzla.com/bcv/current.json"
        respuesta = requests.get(url)
        return float(respuesta.json()['current']['usd'])
    except Exception:
        return None

def buscar_anuncio_binance(monto_fiat, tipo_operacion, pay_type=None):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    data = {
        "fiat": "VES", "page": 1, "rows": 1, "tradeType": tipo_operacion,
        "asset": "USDT", "countries": [], "payTypes": [pay_type] if pay_type else []
    }
    if monto_fiat:
        data["transAmount"] = str(monto_fiat)
    try:
        respuesta = requests.post(url, headers=headers, json=data)
        anuncios = respuesta.json().get('data', [])
        if not anuncios: return None
        mejor_anuncio = anuncios[0]
        return {"precio": float(mejor_anuncio['adv']['price']), "usuario": mejor_anuncio['advertiser']['nickName']}
    except Exception:
        return None

def formato_venezolano(numero, decimales=2):
    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- COMANDOS DE ADMINISTRADOR ---
async def comando_crearkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return # Ignora si no eres tú
    
    if not context.args:
        await update.message.reply_text("⚠️ Usa: /crearkey [cantidad_creditos]")
        return
        
    try:
        creditos = int(context.args[0])
        codigo = "KEY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        db = cargar_db()
        db["keys"][codigo] = {"creditos": creditos, "usada": False}
        guardar_db(db)
        
        await update.message.reply_text(f"✅ Llave creada con éxito.\n\n🔑 `{codigo}`\n🪙 Créditos: {creditos}\n\nEnvía esta llave a tu cliente para que la canjee.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ La cantidad debe ser un número entero.")

# --- COMANDOS DE CLIENTE (CUENTA) ---
async def comando_canjear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía la llave. Ejemplo: /canjear KEY-ABCD12")
        return
        
    codigo = context.args[0]
    user_id = str(update.message.from_user.id)
    db = cargar_db()
    
    if codigo not in db["keys"]:
        await update.message.reply_text("❌ Llave inválida o no existe.")
        return
        
    if db["keys"][codigo]["usada"]:
        await update.message.reply_text("❌ Esta llave ya fue utilizada.")
        return
        
    creditos_nuevos = db["keys"][codigo]["creditos"]
    
    if user_id not in db["usuarios"]:
        db["usuarios"][user_id] = 0
        
    db["usuarios"][user_id] += creditos_nuevos
    db["keys"][codigo]["usada"] = True
    guardar_db(db)
    
    await update.message.reply_text(f"✅ ¡Llave canjeada con éxito!\n🪙 Se añadieron {creditos_nuevos} créditos a tu cuenta.\nUsa /perfil para ver tu saldo.")

async def comando_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    db = cargar_db()
    saldo = db["usuarios"].get(user_id, 0)
    await update.message.reply_text(f"👤 Tu Perfil:\n🪙 Créditos disponibles: {saldo}\n\nCada consulta consume 1 crédito.")

# --- COMANDO START ---
async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 ¡Hola! Soy tu calculadora financiera VIP del BCV y Binance P2P.\n\n"
        "💳 **SISTEMA DE CRÉDITOS**\n"
        "🔹 /perfil - Ver tu saldo de consultas.\n"
        "🔹 /canjear [LLAVE] - Recargar créditos.\n\n"
        "📊 **HERRAMIENTAS** (Cuestan 1 crédito c/u)\n"
        "🔹 /calcular [monto]\n"
        "🔹 /bolivares [monto]\n"
        "🔹 /venta [monto]\n"
        "🔹 /compra [monto]"
    )
    await update.message.reply_text(mensaje)

# --- COMANDOS OPERATIVOS (Protegidos) ---
async def ejecutar_comando_protegido(update, operacion_func):
    user_id = update.message.from_user.id
    
    # Excepción para el administrador (consultas ilimitadas)
    if user_id != ADMIN_ID:
        if not tiene_creditos(user_id):
            await update.message.reply_text(f"⚠️ No tienes créditos suficientes.\n\nContacta a {ADMIN_USERNAME} para adquirir una nueva llave o usa /canjear [LLAVE] si ya tienes una.")
            return
    
    # Ejecuta el cálculo original
    exito = await operacion_func()
    
    # Descuenta el crédito solo si el cálculo fue exitoso y no eres el admin
    if exito and user_id != ADMIN_ID:
        saldo_restante = descontar_credito(user_id)
        await update.message.reply_text(f"*(Te quedan {saldo_restante} créditos)*", parse_mode="Markdown")

async def comando_calcular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def logica():
        if not context.args:
            await update.message.reply_text("⚠️ Envía el monto en $. Ejemplo: /calcular 500")
            return False
        try: monto_usd = float(context.args[0].replace(',', '.'))
        except ValueError: return False
        
        tasa_bcv = obtener_tasa_bcv()
        if tasa_bcv is None:
            await update.message.reply_text("❌ Error al consultar BCV.")
            return False
            
        tasa_aplicada = tasa_bcv * 1.005
        total_bs = monto_usd * tasa_aplicada
        mensaje = f"💵 Quieres comprar: {formato_venezolano(monto_usd, 2)} $\n🏛 Tasa BCV: {formato_venezolano(tasa_bcv, 4)} Bs\n📈 Tasa Intervención (+0,5%): {formato_venezolano(tasa_aplicada, 4)} Bs\n🇻🇪 Necesitas depositar: {formato_venezolano(total_bs, 2)} Bs"
        await update.message.reply_text(mensaje)
        return True
        
    await ejecutar_comando_protegido(update, logica)

async def comando_bolivares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def logica():
        if not context.args:
            await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /bolivares 40000")
            return False
        try: monto_bs = float(context.args[0].replace(',', '.'))
        except ValueError: return False
        
        tasa_bcv = obtener_tasa_bcv()
        if tasa_bcv is None:
            await update.message.reply_text("❌ Error al consultar BCV.")
            return False
            
        tasa_aplicada = tasa_bcv * 1.005
        total_usd = monto_bs / tasa_aplicada
        mensaje = f"🇻🇪 Tienes disponibles: {formato_venezolano(monto_bs, 2)} Bs\n🏛 Tasa BCV: {formato_venezolano(tasa_bcv, 4)} Bs\n📈 Tasa Intervención (+0,5%): {formato_venezolano(tasa_aplicada, 4)} Bs\n💵 Te alcanza para: {formato_venezolano(total_usd, 2)} $"
        await update.message.reply_text(mensaje)
        return True
        
    await ejecutar_comando_protegido(update, logica)

async def comando_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def logica():
        if not context.args:
            await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /venta 2000000")
            return False
        try: monto_bs = float(context.args[0].replace(',', '.'))
        except ValueError: return False

        resultados = []
        for nombre_banco, info in BANCOS.items():
            anuncio = buscar_anuncio_binance(monto_bs, "SELL", info["code"])
            if anuncio:
                resultados.append({"banco": nombre_banco, "emoji": info["emoji"], "precio": anuncio["precio"], "usuario": anuncio["usuario"], "total_usdt": monto_bs / anuncio['precio']})

        if not resultados:
            await update.message.reply_text(f"❌ No hay anuncios para {formato_venezolano(monto_bs)} Bs.")
            return False

        resultados.sort(key=lambda x: x["precio"], reverse=True)
        mensaje_lineas = [f"🇻🇪 Quieres obtener: {formato_venezolano(monto_bs, 2)} Bs", "📊 Tasa Exacta Binance en:"]
        for res in resultados:
            mensaje_lineas.append(f"\n{res['emoji']} {res['banco']}: {formato_venezolano(res['precio'], 4)} Bs\n👤 {res['usuario']}\n🔴 Vendes: {formato_venezolano(res['total_usdt'], 2)} USDT")
        await update.message.reply_text("\n".join(mensaje_lineas))
        return True
        
    await ejecutar_comando_protegido(update, logica)

async def comando_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def logica():
        if not context.args:
            await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /compra 2000000")
            return False
        try: monto_bs = float(context.args[0].replace(',', '.'))
        except ValueError: return False

        resultados = []
        for nombre_banco, info in BANCOS.items():
            anuncio = buscar_anuncio_binance(monto_bs, "BUY", info["code"])
            if anuncio:
                resultados.append({"banco": nombre_banco, "emoji": info["emoji"], "precio": anuncio["precio"], "usuario": anuncio["usuario"], "total_usdt": monto_bs / anuncio['precio']})

        if not resultados:
            await update.message.reply_text(f"❌ No hay anuncios para {formato_venezolano(monto_bs)} Bs.")
            return False

        resultados.sort(key=lambda x: x["precio"], reverse=False)
        mensaje_lineas = [f"🇻🇪 Inviertes: {formato_venezolano(monto_bs, 2)} Bs", "📊 Tasa Exacta Binance en:"]
        for res in resultados:
            mensaje_lineas.append(f"\n{res['emoji']} {res['banco']}: {formato_venezolano(res['precio'], 4)} Bs\n👤 {res['usuario']}\n🟢 Recibes: {formato_venezolano(res['total_usdt'], 2)} USDT")
        await update.message.reply_text("\n".join(mensaje_lineas))
        return True
        
    await ejecutar_comando_protegido(update, logica)

def main():
    mantener_vivo()
    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler("crearkey", comando_crearkey))
    app.add_handler(CommandHandler("canjear", comando_canjear))
    app.add_handler(CommandHandler("perfil", comando_perfil))
    app.add_handler(CommandHandler("calcular", comando_calcular))
    app.add_handler(CommandHandler("bolivares", comando_bolivares))
    app.add_handler(CommandHandler("venta", comando_venta))
    app.add_handler(CommandHandler("compra", comando_compra))
    
    app.run_polling()

if __name__ == "__main__":
    main()
