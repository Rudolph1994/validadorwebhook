from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import time

app = FastAPI(title="Validador de Webhooks Bsale")


# === Interfaz principal ===
@app.get("/", response_class=HTMLResponse)
async def home():
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Validador de Webhooks Bsale</title>
        <style>
            body { font-family: Arial, sans-serif; background:#f4f6f8; margin:0; padding:0; }
            .container { max-width:600px; background:#fff; margin:50px auto; padding:30px; border-radius:12px;
                        box-shadow:0 4px 12px rgba(0,0,0,0.1); }
            h1 { color:#1E88E5; text-align:center; }
            label { display:block; margin-top:15px; font-weight:600; }
            input, select { width:100%; padding:8px; margin-top:5px; border-radius:6px; border:1px solid #ccc; }
            button { margin-top:20px; width:100%; padding:12px; background:#1E88E5; color:white; border:none;
                     border-radius:8px; font-size:16px; cursor:pointer; transition:0.2s; }
            button:hover { background:#1565C0; }
            pre { background:#f5f5f5; padding:15px; border-radius:10px; white-space:pre-wrap; word-break:break-all; }
            .ok { color:green; font-weight:bold; }
            .error { color:red; font-weight:bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Validador de Webhooks Bsale</h1>
            <form id="form">
                <label>CPN del cliente:</label>
                <input type="number" id="cpn" required placeholder="Ej: 74244">

                <label>URL del Webhook:</label>
                <input type="url" id="url" required placeholder="https://ejemplo.com/webhook">

                <label>Tópico:</label>
                <select id="topic" required>
                    <option value="document">document</option>
                    <option value="stock">stock</option>
                </select>

                <button type="submit">Validar Webhook</button>
            </form>

            <div id="result"></div>
        </div>

        <script>
        document.getElementById("form").addEventListener("submit", async (e) => {
            e.preventDefault();
            document.getElementById("result").innerHTML = "<p>Enviando notificación...</p>";

            const data = {
                cpnId: document.getElementById("cpn").value,
                url: document.getElementById("url").value,
                topic: document.getElementById("topic").value
            };

            try {
                const res = await fetch("/validate-webhook", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data)
                });
                const json = await res.json();

                if (json.status === "ok") {
                    document.getElementById("result").innerHTML = `
                        <p class='ok'>✅ Notificación enviada correctamente</p>
                        <pre>${JSON.stringify(json, null, 2)}</pre>
                    `;
                } else {
                    document.getElementById("result").innerHTML = `
                        <p class='error'>❌ Error al enviar</p>
                        <pre>${JSON.stringify(json, null, 2)}</pre>
                    `;
                }
            } catch (err) {
                document.getElementById("result").innerHTML = `
                    <p class='error'>❌ Error inesperado</p>
                    <pre>${err}</pre>
                `;
            }
        });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# === Endpoint que valida el webhook ===
@app.post("/validate-webhook")
async def validate_webhook(request: Request):
    data = await request.json()
    cpn_id = data.get("cpnId")
    url = data.get("url")
    topic = data.get("topic")

    if not cpn_id or not url or not topic:
        return JSONResponse({"status": "error", "message": "Faltan datos (cpnId, url o topic)"}, status_code=400)

    # --- Determinar la ruta según el topic ---
    if topic == "stock":
        resource = "/v2/stocks.json?variant=0&office=1"
        resource_id = "0"
        action = "put"
        office_id = "1"
    elif topic == "document":
        resource = "/documents/0.json"
        resource_id = "0"
        action = "post"
        office_id = "1"
    else:
        return JSONResponse({"status": "error", "message": "Topic inválido"}, status_code=400)

    # --- Estructura JSON idéntica a Bsale ---
    payload = {
        "rq": {
            "cpnId": int(cpn_id),
            "resource": resource,
            "resourceId": resource_id,
            "topic": topic,
            "action": action,
            "officeId": office_id,
            "send": int(time.time())
        }
    }

    # --- Enviar POST al webhook del cliente ---
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(url, json=payload)
            return {
                "status": "URL Correcta",
                "sent_to": url,
                "cpnId": cpn_id,
                "topic": topic,
                "response_code": response.status_code,
                "response_text": response.text[:500],
                "payload_sent": payload
            }
    except Exception as e:
        return {"status": "error", "message": str(e), "payload_sent": payload}
