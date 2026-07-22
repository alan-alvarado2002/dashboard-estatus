"""
DeezerWeb — Buscador de música (Emsam Sound)
=============================================
Aplicación Flask que consume la API pública de Deezer y expone:
  - Una página web con buscador en /deezer
  - Endpoints JSON en /deezer/api/*

Se sirve detrás de nginx bajo el prefijo /deezer.
No requiere API key.
"""

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE = "https://api.deezer.com"
TIMEOUT = 8


# ─────────────────────────────────────────────────────────────
#  Capa de acceso a la API de Deezer
# ─────────────────────────────────────────────────────────────
def _get(ruta, params=None):
    """Petición GET centralizada con manejo de errores."""
    try:
        r = requests.get(f"{BASE}{ruta}", params=params, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        raise RuntimeError("La API tardó demasiado en responder (timeout).")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Sin conexión con la API de Deezer.")
    if r.status_code != 200:
        raise RuntimeError(f"La API respondió con código {r.status_code}.")
    datos = r.json()
    if isinstance(datos, dict) and "error" in datos:
        msg = datos["error"].get("message", "Error desconocido de la API.")
        raise RuntimeError(f"Error de Deezer: {msg}")
    return datos


def buscar_canciones(termino, limite=12):
    datos = _get("/search", params={"q": termino, "limit": limite})
    canciones = []
    for t in datos.get("data", []):
        canciones.append({
            "titulo":   t.get("title"),
            "artista":  t.get("artist", {}).get("name"),
            "album":    t.get("album", {}).get("title"),
            "portada":  t.get("album", {}).get("cover_medium"),
            "preview":  t.get("preview"),   # fragmento mp3 de 30s
            "duracion": t.get("duration"),
            "id":       t.get("id"),
        })
    return canciones


def buscar_artistas(nombre, limite=8):
    datos = _get("/search/artist", params={"q": nombre, "limit": limite})
    artistas = []
    for a in datos.get("data", []):
        artistas.append({
            "nombre":  a.get("name"),
            "foto":    a.get("picture_medium"),
            "fans":    a.get("nb_fan"),
            "albumes": a.get("nb_album"),
            "id":      a.get("id"),
        })
    return artistas


# ─────────────────────────────────────────────────────────────
#  Rutas web
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Página con el buscador. Bajo nginx se ve como /deezer/."""
    return render_template("index.html")


@app.route("/api/buscar")
def api_buscar():
    """Endpoint JSON: /deezer/api/buscar?q=...&tipo=canciones|artistas"""
    termino = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "canciones")
    if not termino:
        return jsonify({"error": "Falta el parámetro 'q'."}), 400
    try:
        if tipo == "artistas":
            resultados = buscar_artistas(termino)
        else:
            resultados = buscar_canciones(termino)
        return jsonify({
            "termino": termino,
            "tipo": tipo,
            "total": len(resultados),
            "resultados": resultados,
        })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
