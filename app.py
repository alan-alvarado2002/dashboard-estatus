import requests
from flask import Flask, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

SERVICIOS = [
    {"nombre": "GitHub",          "url": "https://api.github.com"},
    {"nombre": "JSONPlaceholder", "url": "https://jsonplaceholder.typicode.com/posts/1"},
    {"nombre": "HTTPBin",         "url": "https://httpbin.org/status/200"},
    {"nombre": "ReqRes",          "url": "https://reqres.in/api/users/1"},
    {"nombre": "Mi API Local",    "url": "http://localhost:5001/dispositivos"},
]

def verificar_servicio(nombre, url):
    try:
        r = requests.get(url, timeout=5)
        activo = r.status_code < 400
        return {
            "nombre":   nombre,
            "url":      url,
            "activo":   activo,
            "status":   r.status_code,
            "latencia": round(r.elapsed.total_seconds() * 1000, 1),
            "error":    None,
        }
    except requests.exceptions.Timeout:
        return {"nombre": nombre, "url": url, "activo": False,
                "status": None, "latencia": None, "error": "Timeout"}
    except Exception as e:
        return {"nombre": nombre, "url": url, "activo": False,
                "status": None, "latencia": None, "error": str(e)[:80]}

@app.route("/api/estado")
def estado():
    resultados = [verificar_servicio(s["nombre"], s["url"]) for s in SERVICIOS]
    activos = sum(1 for r in resultados if r["activo"])
    return jsonify({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total":     len(resultados),
        "activos":   activos,
        "caidos":    len(resultados) - activos,
        "servicios": resultados,
    })

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
