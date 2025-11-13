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
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Validador de Webhooks Bsale</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f8f8f8;
      padding: 30px;
    }
    .container {
      max-width: 600px;
      background: #ffffff;
      padding: 25px;
      border-radius: 10px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.1);
      margin: auto;
      text-align: center;
    }
    h1 {
      color: #333;
      margin-bottom: 10px;
    }
    img.logo {
      width: 140px;
      margin-bottom: 15px;
    }
    label {
      font-weight: bold;
      margin-top: 10px;
      display: block;
      text-align: left;
    }
    input, select {
      width: 100%;
      padding: 10px;
      margin-top: 5px;
      border-radius: 6px;
      border: 1px solid #ccc;
      box-sizing: border-box;
    }
    button {
      background-color: #ff6600;
      color: white;
      border: none;
      padding: 12px;
      margin-top: 15px;
      border-radius: 6px;
      cursor: pointer;
      width: 100%;
      font-size: 16px;
      font-weight: bold;
    }
    button:hover {
      background-color: #e65c00;
    }
    #resultado {
      margin-top: 20px;
      padding: 15px;
      border-radius: 6px;
      display: none;
      font-size: 16px;
      font-weight: bold;
    }
    .ok { background-color: #d4edda; color: #155724; }
    .error { background-color: #f8d7da; color: #721c24; }
    .alerta { background-color: #fff3cd; color: #856404; }
  </style>
</head>
<body>
  <div class="container">
    <img src="https://bsale-io.s3.amazonaws.com/menu-v2/images/bsale-orange.svg" alt="Bsale Logo" class="logo">
    <h1>Validador de Webhooks Bsale</h1>
    <label for="cpn">ID de Cuenta (CPN)</label>
    <input type="number" id="cpn" placeholder="Ej: 74244">

    <label for="url">URL del Webhook</label>
    <input type="text" id="url" placeholder="https://tuservidor.com/webhook">

    <label for="topic">Tipo de evento</label>
    <select id="topic">
      <option value="stock">Stock</option>
      <option value="document">Documentos</option>
    </select>

    <button onclick="enviarWebhook()">Enviar prueba</button>

    <div id="resultado"></div>
  </div>

  <script>
    async function enviarWebhook() {
      const cpnId = document.getElementById('cpn').value.trim();
      const url = document.getElementById('url').value.trim();
      const topic = document.getElementById('topic').value;
      const resultado = document.getElementById('resultado');

      resultado.style.display = 'block';
      resultado.className = '';
      resultado.textContent = '⏳ Enviando notificación de prueba...';

      if (!cpnId || !url) {
        resultado.textContent = '⚠️ Debes ingresar el ID de cuenta y la URL del webhook.';
        resultado.className = 'alerta';
        return;
      }

      try {
        const res = await fetch("/test_webhook", {
          method: "POST",
          body: new URLSearchParams({ cpn: cpnId, topic: topic, url: url }),
        });

        const json = await res.json();
        resultado.textContent = json.mensaje;
        if (json.mensaje.startsWith("✅")) resultado.className = 'ok';
        else if (json.mensaje.startsWith("⚠️")) resultado.className = 'alerta';
        else resultado.className = 'error';
      } catch (error) {
        resultado.textContent = "❌ No se pudo contactar con el validador. Intenta nuevamente.";
        resultado.className = 'error';
      }
    }
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_FORM


@app.post("/test_webhook")
async def test_webhook(cpn: str = Form(...), topic: str = Form(...), url: str = Form(...)):
    # URLs de integradores frecuentes que siempre consideramos válidas
    integradores_frecuentes = [
        "https://app.jumpseller.com/bsale/notifications"
    ]

    # Si la URL es de un integrador frecuente, devolver OK automáticamente
    if url in integradores_frecuentes:
        return JSONResponse({"mensaje": f"✅ La URL {url} es de un integrador frecuente y se considera válida automáticamente."})
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

        # Rechazar si se demoró más de 3 segundos
        if duracion > 3.0:
            return JSONResponse({"mensaje": f"⏱ El webhook tardó más de 3 segundos en responder ({duracion}s). Bsale considera esto como una falla."})

        # Validar tipo de contenido
        content_type = respuesta.headers.get("content-type", "").lower()
        if "application/json" not in content_type and "text/json" not in content_type:
            return JSONResponse({"mensaje": f"⚠️ La URL respondió correctamente, pero no parece ser un webhook válido (tipo de respuesta: {content_type})."})

        # Validar código HTTP
        if not (200 <= respuesta.status_code < 300):
            if respuesta.status_code == 405:
                return JSONResponse({"mensaje": "❌ El webhook no acepta solicitudes de tipo POST. Verifica que esté configurado correctamente."})
            return JSONResponse({"mensaje": f"❌ El webhook respondió con un error (código {respuesta.status_code})."})

        # OK
        return JSONResponse({"mensaje": f"✅ El webhook respondió correctamente en {duracion} segundos (código {respuesta.status_code})."})

    except httpx.ReadTimeout:
        duracion = round(time.time() - inicio, 2)
        return JSONResponse({"mensaje": f"⏱ El webhook no respondió dentro del tiempo permitido (3 segundos). Bsale considera esto como una falla."})

    except httpx.RequestError as e:
        duracion = round(time.time() - inicio, 2)
        if isinstance(e.__cause__, socket.gaierror):
            return JSONResponse({"mensaje": f"❌ La dirección ingresada no existe o no se pudo conectar ({duracion}s)."})
        return JSONResponse({"mensaje": f"⚠️ No se pudo establecer conexión con la URL del webhook ({duracion}s). Verifica la dirección."})

    except Exception as e:
        duracion = round(time.time() - inicio, 2)
        return JSONResponse({"mensaje": f"⚠️ Error inesperado al intentar enviar la notificación: {str(e)} ({duracion}s)."})
