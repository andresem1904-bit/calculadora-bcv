import os
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# === CONFIGURACIÓN ===
TOKEN = "8550226144:AAFlJ3-Twt_pVVmGC348fIVjp2XiUpzWE7c"
# =====================

app_web = Flask(__name__)
@app_web.route('/')
def home():
    return "El bot del BCV está funcionando 24/7."

def iniciar_servidor():
    puerto = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=puerto, use_reloader=False)

def mantener_vivo():
    hilo = Thread(target=iniciar_servidor)
    hilo.daemon = True
    hilo.start()

def obtener_tasa_bcv():
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar/page?page=bcv"
        respuesta = requests.get(url)
        return float(respuesta.json()['monedas']['usd']['price'])
    except Exception:
        return None

def formato_venezolano(numero, decimales=2):
    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")

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

def main():
    mantener_vivo()
    
    # --- Solución al error de Asyncio en Render ---
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    # ----------------------------------------------
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    app.run_polling()

if __name__ == "__main__":
    main()
