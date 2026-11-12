FROM python:3.12-slim
RUN pip install --no-cache-dir edge-tts==7.3.1 fastapi==0.162.4 uvicorn==0.54.0
WORKDIR /app
COPY server.py .
EXPOSE 5050
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5050"]
