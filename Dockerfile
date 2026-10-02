FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install fastapi uvicorn
WORKDIR /app
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8123"]
