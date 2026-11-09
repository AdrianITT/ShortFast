FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn
WORKDIR /app
COPY main.py render.py guia_ia.py generar_guia.py render_largo.py ./
COPY largo/ ./largo/
ENV PROYECTOS=/data/proyectos SALIDA=/data/salida PLANTILLA=/data/plantilla \
    PROYECTOS_LARGOS=/data/proyectos_largos SALIDA_LARGOS=/data/salida_largos
EXPOSE 8123
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8123"]
