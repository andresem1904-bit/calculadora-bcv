import os
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# === CONFIGURACIÓN ===
TOKEN = "8550226144:AAFlJ3-Twt_pVVmGC348fIVjp2XiUpzWE7c"
# =====================

# Lista de bancos con sus emojis y códigos internos de Binance
BANCOS = {
    "Banesco": {"code": "Banesco", "emoji": "🟢"},
    "Banco de Venezuela": {"code": "BancodeVenezuela", "emoji": "🔴"},
    "Mercantil": {"code": "Mercantil", "emoji": "🔵"},
    "Provincial": {"code": "Provincial", "emoji": "🟦"},
    "Bancamiga": {"code": "Bancamiga", "emoji": "🟣"},
    "Banco Digital de los Trabajadores": {"code": "BancoBicentenario", "emoji": "🟠"}
}

app_web = Flask(__name__)
@app_web.route('/')
def home():
    return "El bot del BCV y Binance (Con Menú) está funcionando 24/7."

def iniciar_servidor():
    puerto = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=puerto, use_reloader=False)

def mantener_vivo():
    hilo = Thread(target=iniciar_servidor)
    hilo.daemon = True
    hilo.start()

def obtener_tasa_bcv():
    try:
        url = "https://rates.dolarvzla.com/bcv/current.json"
        respuesta = requests.get(url)
        return float(respuesta.json()['current']['usd'])
    except Exception:
        return None

def buscar_anuncio_binance(monto_fiat, tipo_operacion, pay_type=None):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    data = {
        "fiat": "VES",
        "page": 1,
        "rows": 1,
        "tradeType": tipo_operacion,
        "asset": "USDT",
        "countries": [],
        "payTypes": [pay_type] if pay_type else []
    }
    
    if monto_fiat:
        data["transAmount"] = str(monto_fiat)

    try:
        respuesta = requests.post(url, headers=headers, json=data)
        anuncios = respuesta.json().get('data', [])
        if not anuncios:
            return None
        
        mejor_anuncio = anuncios[0]
        return {
            "precio": float(mejor_anuncio['adv']['price']),
            "usuario": mejor_anuncio['advertiser']['nickName']
        }
    except Exception:
        return None

def formato_venezolano(numero, decimales=2):
    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- COMANDO /start (Bienvenida y Guía) ---
async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 ¡Hola! Soy tu calculadora financiera del BCV y Binance P2P.\n\n"
        "👇 Estos son los comandos que puedes utilizar:\n\n"
        "🏛 BCV (Tasa Oficial + 0,5%)\n"
        "🔹 /calcular [monto] - Saber cuántos Bs necesitas para comprar $.\n"
        "🔹 /bolivares [monto] - Saber cuántos $ te alcanzan con tus Bs disponibles.\n\n"
        "💱 BINANCE P2P (Mejor tasa Multibanco)\n"
        "🔹 /venta [monto] - Busco quién te da más Bs por tus USDT.\n"
        "🔹 /compra [monto] - Busco quién te pide menos Bs por darte USDT."
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /calcular ---
async def comando_calcular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en $. Ejemplo: /calcular 500")
        return
    
    try:
        monto_usd = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    tasa_bcv = obtener_tasa_bcv()
    if tasa_bcv is None:
        await update.message.reply_text("❌ Error al consultar la tasa del BCV.")
        return

    tasa_aplicada = tasa_bcv * 1.005
    total_bs = monto_usd * tasa_aplicada

    mensaje = (
        f"💵 Quieres comprar: {formato_venezolano(monto_usd, 2)} $\n"
        f"🏛 Tasa BCV: {formato_venezolano(tasa_bcv, 4)} Bs\n"
        f"📈 Tasa Intervención (+0,5%): {formato_venezolano(tasa_aplicada, 4)} Bs\n"
        f"🇻🇪 Necesitas depositar: {formato_venezolano(total_bs, 2)} Bs"
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /bolivares ---
async def comando_bolivares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /bolivares 40000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    tasa_bcv = obtener_tasa_bcv()
    if tasa_bcv is None:
        await update.message.reply_text("❌ Error al consultar la tasa del BCV.")
        return

    tasa_aplicada = tasa_bcv * 1.005
    total_usd = monto_bs / tasa_aplicada

    mensaje = (
        f"🇻🇪 Tienes disponibles: {formato_venezolano(monto_bs, 2)} Bs\n"
        f"🏛 Tasa BCV: {formato_venezolano(tasa_bcv, 4)} Bs\n"
        f"📈 Tasa Intervención (+0,5%): {formato_venezolano(tasa_aplicada, 4)} Bs\n"
        f"💵 Te alcanza para: {formato_venezolano(total_usd, 2)} $"
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /venta ---
async def comando_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /venta 2000000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    resultados = []
    for nombre_banco, info in BANCOS.items():
        anuncio = buscar_anuncio_binance(monto_bs, "SELL", info["code"])
        if anuncio:
            total_usdt = monto_bs / anuncio['precio']
            resultados.append({
                "banco": nombre_banco,
                "emoji": info["emoji"],
                "precio": anuncio["precio"],
                "usuario": anuncio["usuario"],
                "total_usdt": total_usdt
            })

    if not resultados:
        await update.message.reply_text(f"❌ No hay anuncios disponibles para {formato_venezolano(monto_bs)} Bs en estos bancos.")
        return

    resultados.sort(key=lambda x: x["precio"], reverse=True)

    mensaje_lineas = [
        f"🇻🇪 Quieres obtener: {formato_venezolano(monto_bs, 2)} Bs",
        "📊 Tasa Exacta Binance en:"
    ]

    for res in resultados:
        bloque = (
            f"\n{res['emoji']} {res['banco']}: {formato_venezolano(res['precio'], 4)} Bs\n"
            f"👤 {res['usuario']}\n"
            f"🔴 Vendes: {formato_venezolano(res['total_usdt'], 2)} USDT"
        )
        mensaje_lineas.append(bloque)

    await update.message.reply_text("\n".join(mensaje_lineas))

# --- COMANDO /compra ---
async def comando_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en Bs. Ejemplo: /compra 2000000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    resultados = []
    for nombre_banco, info in BANCOS.items():
        anuncio = buscar_anuncio_binance(monto_bs, "BUY", info["code"])
        if anuncio:
            total_usdt = monto_bs / anuncio['precio']
            resultados.append({
                "banco": nombre_banco,
                "emoji": info["emoji"],
                "precio": anuncio["precio"],
                "usuario": anuncio["usuario"],
                "total_usdt": total_usdt
            })

    if not resultados:
        await update.message.reply_text(f"❌ No hay anuncios disponibles para {formato_venezolano(monto_bs)} Bs en estos bancos.")
        return

    resultados.sort(key=lambda x: x["precio"], reverse=False)

    mensaje_lineas = [
        f"🇻🇪 Inviertes: {formato_venezolano(monto_bs, 2)} Bs",
        "📊 Tasa Exacta Binance en:"
    ]

    for res in resultados:
        bloque = (
            f"\n{res['emoji']} {res['banco']}: {formato_venezolano(res['precio'], 4)} Bs\n"
            f"👤 {res['usuario']}\n"
            f"🟢 Recibes: {formato_venezolano(res['total_usdt'], 2)} USDT"
        )
        mensaje_lineas.append(bloque)

    await update.message.reply_text("\n".join(mensaje_lineas))

def main():
    mantener_vivo()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TOKEN).build()
    
    # Registramos el nuevo comando start
    app.add_handler(CommandHandler("start", comando_start))
    
    # Comandos operativos
    app.add_handler(CommandHandler("calcular", comando_calcular))
    app.add_handler(CommandHandler("bolivares", comando_bolivares))
    app.add_handler(CommandHandler("venta", comando_venta))
    app.add_handler(CommandHandler("compra", comando_compra))
    
    app.run_polling()

if __name__ == "__main__":
    main()
