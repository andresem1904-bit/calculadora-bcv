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
    return "El bot del BCV y Binance Avanzado está funcionando 24/7."

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
    """Busca directamente en Binance filtrando por monto"""
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

# --- CALCULADORA BCV ---
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

# --- COMANDO /usdt (Vendes tus USDT para obtener Bs -> Buscamos comerciantes BUY) ---
async def comando_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto. Ejemplo: /usdt 100")
        return
    
    try:
        monto_usdt = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    # Paso 1: Consultar sin monto para sacar un estimado
    tasa_base = buscar_anuncio_binance(None, "BUY")
    if not tasa_base:
        await update.message.reply_text("❌ Error al conectar con Binance P2P.")
        return
        
    monto_bs_estimado = monto_usdt * tasa_base['precio']
    
    # Paso 2: Consultar filtrando por los Bs exactos
    anuncio = buscar_anuncio_binance(monto_bs_estimado, "BUY")
    if not anuncio:
        await update.message.reply_text(f"❌ No hay comerciantes que acepten límites para {formato_venezolano(monto_bs_estimado)} Bs.")
        return

    total_bs = monto_usdt * anuncio['precio']

    mensaje = (
        f"🟡 Monto: {formato_venezolano(monto_usdt, 2)} USDT\n"
        f"📊 Tasa Exacta Binance: {formato_venezolano(anuncio['precio'], 4)} Bs\n"
        f"👤 Comerciante: {anuncio['usuario']}\n"
        f"🇻🇪 Recibes: {formato_venezolano(total_bs, 2)} Bs"
    )
    await update.message.reply_text(mensaje)

# --- COMANDO /bs (Entregas Bs para comprar USDT -> Buscamos comerciantes SELL) ---
async def comando_bs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Envía el monto. Ejemplo: /bs 2000000")
        return
    
    try:
        monto_bs = float(context.args[0].replace(',', '.'))
    except ValueError:
        return

    anuncio = buscar_anuncio_binance(monto_bs, "SELL")
    if not anuncio:
        await update.message.reply_text(f"❌ No hay comerciantes que acepten {formato_venezolano(monto_bs)} Bs en este momento.")
        return

    total_usdt = monto_bs / anuncio['precio']

    mensaje = (
        f"🇻🇪 Monto: {formato_venezolano(monto_bs, 2)} Bs\n"
        f"📊 Tasa Exacta Binance: {formato_venezolano(anuncio['precio'], 4)} Bs\n"
        f"👤 Comerciante: {anuncio['usuario']}\n"
        f"🟡 Recibes: {formato_venezolano(total_usdt, 2)} USDT"
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
    
    app.add_handler(CommandHandler("usdt", comando_usdt))
    app.add_handler(CommandHandler("bs", comando_bs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    
    app.run_polling()

if __name__ == "__main__":
    main()
