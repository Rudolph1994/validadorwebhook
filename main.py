from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import time
import socket

app = FastAPI()

HTML_FORM = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Validador de Webhooks Bsale</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f7f9fb;
            padding: 40px;
        }
        .container {
            max-width: 520px;
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: auto;
        }
        h2 {
            text-align: center;
            color: #333;
        }
        input, select, button {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            font-size: 16px;
        }
        button {
            background: #0078d4;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 6px;
        }
        button:hover {
            background: #005fa3;
        }
        .resultado {
            margin-top: 20px;
            font-weight: bold;
            font-size: 16px;
            text-align: center;
        }
    </style>
</head>
<body>
<div class="container">
    <h2>Validador de Webhooks Bsale</h2>
    <form id="webhookForm">
        <label>ID de cuenta (CPN):</label>
        <input type="number" name="cpn" required placeholder="Ej: 74244">

        <label>Tipo de evento a probar:</label>
        <select name="topic" required>
            <option value="document">Documentos</option>
            <option value="stock">Stock</option>
        </select>

        <label>URL del Webhook:</label>
        <input type="url" name="url" required placeholder="https://tuwebhook.com/endpoint">

        <button type="submit">Enviar prueba</button>
    </form>
    <div class="resultado" id="resultado"></div>
</div>

<script>
document.getElementById("webhookForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    const resultado = document.getElementById("resultado");
    resultado.style.color = "black";
    resultado.innerText = "⏳ Enviando prueba...";
    try {
        const res = await fetch("/test_webhook", {
            method: "POST",
            body: new URLSearchParams(data),
        });
        const json = await res.json();

        if (json.mensaje.startsWith("✅")) resultado.style.color = "green";
        else if (json.mensaje.startsWith("❌")) resultado.style.color = "red";
        else resultado.style.color = "orange";

        resultado.innerText = json.mensaje;
    } catch {
        resultado.style.color = "red";
        resultado.innerText = "⚠️ No se pudo contactar con el servidor.";
    }
});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_FORM


@app.post("/test_webhook")
async def test_webhook(cpn: str = Form(...), topic: str = Form(...), url: str = Form(...)):
    payload = {
        "rq": {
            "cpnId": cpn,
            "resource": "/documents/0.json" if topic == "document" else "/v2/stocks.json?variant=0&office=1",
            "resourceId": "0",
            "topic": topic,
            "action": "put",
            "officeId": "1",
            "send": int(time.time())
        }
    }

    inicio = time.time()

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            respuesta = await client.post(url, json=payload)
        duracion = round(time.time() - inicio, 2)

        if duracion > 3.0:
            return JSONResponse({"mensaje": f"❌ El webhook superó el tiempo máximo permitido ({duracion}s)"})

        status = respuesta.status_code
        content_type = respuesta.headers.get("content-type", "").lower()
        body = respuesta.text.strip().lower()

        # 1️⃣ Código HTTP válido
        if not (200 <= status < 300):
            return JSONResponse({"mensaje": f"❌ El webhook respondió con código {status}, debe ser 2xx."})

        # 2️⃣ Detectar páginas web (HTML)
        if "text/html" in content_type or "<html" in body or "<!doctype" in body:
            return JSONResponse({"mensaje": f"❌ La URL respondió {status}, pero parece una página web (Content-Type: {content_type})"})

        # 3️⃣ Webhook típico (aceptamos vacío, JSON o textos comunes)
        if (
            body == "" or
            "application/json" in content_type or
            "json" in content_type or
            "ok" in body or
            "success" in body or
            "ack" in body or
            "processing" in body or
            "received" in body
        ):
            return JSONResponse({"mensaje": f"✅ Webhook respondió correctamente ({status}) en {duracion}s"})

        # 4️⃣ Si pasa todo pero no se reconoce el cuerpo
        return JSONResponse({"mensaje": f"⚠️ La URL respondió {status}, pero el contenido no parece típico de un webhook (Content-Type: {content_type})"})

    except httpx.ReadTimeout:
        duracion = round(time.time() - inicio, 2)
        return JSONResponse({"mensaje": f"❌ El webhook no respondió dentro del tiempo permitido (timeout de {duracion}s)"})
    except httpx.RequestError as e:
        duracion = round(time.time() - inicio, 2)
        if isinstance(e.__cause__, socket.gaierror):
            return JSONResponse({"mensaje": f"❌ La URL indicada no es válida o no existe ({duracion}s)"})
        return JSONResponse({"mensaje": f"⚠️ No se pudo conectar con el webhook: {str(e)} ({duracion}s)"})
    except Exception as e:
        duracion = round(time.time() - inicio, 2)
        return JSONResponse({"mensaje": f"⚠️ Error inesperado: {str(e)} ({duracion}s)"})
