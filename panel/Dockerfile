# Panel web en Docker. Se construye desde la raíz del repo: docker build -f panel/Dockerfile .
FROM python:3.12-slim
# ffmpeg/ffprobe: el cortador de grabaciones (panel/cortador.py) los usa.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi==0.162.2 "uvicorn[standard]==0.54.0" jinja2==3.1.6 python-multipart==0.0.33
WORKDIR /app
COPY panel.json ./
COPY panel/ ./panel/
EXPOSE 8090
CMD ["python", "-m", "panel"]
