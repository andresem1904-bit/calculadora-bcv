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

app_web = Flask(__name__)
@app_web.route('/')
def home():
    return "El bot del BCV y Binance (Compra/Venta) está funcionando 24/7."

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

def buscar_anuncio_binance(monto_fiat, tipo_operacion):
    """Busca directamente en Binance filtrando por el monto exacto de Bs"""
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    data = {
        "fiat": "VES",
        "page": 1,
        "rows": 1, # Solo queremos el primer anuncio (el mejor)
        "tradeType": tipo_operacion, # "BUY" o "SELL"
        "asset": "USDT",
        "countries": [],
        "payTypes": []
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

# --- CALCULADORA BCV (Mensajes normales sin comando) ---
async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(',', '.')
    try:
        monto_usd = float(texto)
    except ValueError:
        return

    tasa_bcv = obtener_tasa_bcv()
    if tasa_bcv is None:
        await update.message.reply_text("❌ Error al consultar la tasa del BCV.")
        return

    tasa_aplicada = tasa_bcv * 1.005
    total_bs = monto_usd * tasa_aplicada

    mensaje = (
        f"💵 Monto: {formato_venezolano(monto_usd, 2)} $\n"
        f"🏛 Tasa BCV: {formato_venezolano(tasa_bcv, 4)} Bs\n"
        f"📈 Tasa aplicada (+0,5%): {formato_venezolano(tasa_aplicada, 4)} Bs\n"
        f"🇻🇪 Total a pagar: {formato_venezolano(total_bs, 2)} Bs"
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /venta (Quieres obtener Bs -> Vendes tus USDT) ---
async def comando_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en Bs que deseas obtener. Ejemplo: /venta 2000000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    # Buscamos comerciantes BUY (ellos compran tus USDT a cambio de Bs)
    anuncio = buscar_anuncio_binance(monto_bs, "BUY")
    if not anuncio:
        await update.message.reply_text(f"❌ No hay comerciantes (Comprando) que acepten {formato_venezolano(monto_bs)} Bs en este momento.")
        return

    total_usdt = monto_bs / anuncio['precio']

    mensaje = (
        f"🇻🇪 Quieres obtener: {formato_venezolano(monto_bs, 2)} Bs\n"
        f"📊 Tasa Exacta Binance: {formato_venezolano(anuncio['precio'], 4)} Bs\n"
        f"👤 Comerciante: {anuncio['usuario']}\n"
        f"🔴 Vendes: {formato_venezolano(total_usdt, 2)} USDT"
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /compra (Quieres gastar Bs -> Compras USDT) ---
async def comando_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto en Bs que deseas gastar. Ejemplo: /compra 2000000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    # Buscamos comerciantes SELL (ellos te venden USDT a cambio de tus Bs)
    anuncio = buscar_anuncio_binance(monto_bs, "SELL")
    if not anuncio:
        await update.message.reply_text(f"❌ No hay comerciantes (Vendiendo) que acepten {formato_venezolano(monto_bs)} Bs en este momento.")
        return

    total_usdt = monto_bs / anuncio['precio']

    mensaje = (
        f"🇻🇪 Inviertes: {formato_venezolano(monto_bs, 2)} Bs\n"
        f"📊 Tasa Exacta Binance: {formato_venezolano(anuncio['precio'], 4)} Bs\n"
        f"👤 Comerciante: {anuncio['usuario']}\n"
        f"🟢 Recibes: {formato_venezolano(total_usdt, 2)} USDT"
    )
    await update.message.reply_text(mensaje)

def main():
    mantener_vivo()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TOKEN).build()
    
    # Registramos los nuevos comandos de compra y venta
    app.add_handler(CommandHandler("venta", comando_venta))
    app.add_handler(CommandHandler("compra", comando_compra))
    
    # Registramos los números sueltos para el BCV
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    
    app.run_polling()

if __name__ == "__main__":
    main()
