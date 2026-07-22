# Imagen base — Python 3.11 versión ligera
FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar primero requirements para aprovechar el caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY app.py .
COPY templates/ ./templates/

# Puerto que expone el contenedor internamente
EXPOSE 5000

# Comando para arrancar la app con gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
