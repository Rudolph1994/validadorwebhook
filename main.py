from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import time

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
    document.getElementById("resultado").innerText = "⏳ Enviando prueba...";
    try {
        const res = await fetch("/test_webhook", {
            method: "POST",
            body: new URLSearchParams(data),
        });
        const json = await res.json();
        document.getElementById("resultado").innerText = json.mensaje;
    } catch {
        document.getElementById("resultado").innerText = "⚠️ No se pudo contactar con el servidor";
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
    """
    Envía una notificación simulada al webhook indicado y mide el tiempo de respuesta.
    Si supera los 3 segundos (3000 ms), mostrará un mensaje de timeout.
    """
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

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            inicio = time.time()
            respuesta = await client.post(url, json=payload)
            duracion = round((time.time() - inicio) * 1000, 2)

        if duracion > 3000:
            return JSONResponse({"mensaje": f"❌ El webhook tardó demasiado en responder (timeout de {duracion} ms)"})

        return JSONResponse({"mensaje": f"✅ Webhook respondió correctamente ({respuesta.status_code}) en {duracion} ms"})

    except httpx.ReadTimeout:
        return JSONResponse({"mensaje": "❌ El webhook superó el tiempo máximo de respuesta (timeout de 3 segundos)"})
    except Exception as e:
        return JSONResponse({"mensaje": f"⚠️ Error al enviar el webhook: {str(e)}"})
