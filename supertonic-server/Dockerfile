# syntax=docker/dockerfile:1.7
# Supertonic 3 (Supertone, proyecto archivado): código y modelo fijados a una versión exacta, sin internet al usarlo.
FROM python:3.12-slim
RUN pip install --no-cache-dir onnxruntime==1.23.1 numpy==2.5.4 lameenc==1.9.0 \
      fastapi==0.162.4 uvicorn==0.54.0 huggingface_hub==2.4.0
# Modelo ONNX + 10 voces (F1–F5, M1–M5) de supertone-oss-archive/supertonic-3, revisión fijada (~383 MB).
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('supertone-oss-archive/supertonic-3', \
      revision='aafc6e32416a594460b32413efc49d7fe4ce6d46', local_dir='/modelo', allow_patterns=['onnx/*', 'voice_styles/*'])" \
    && rm -rf /modelo/.cache && pip uninstall -y huggingface_hub
WORKDIR /app
ADD --checksum=sha256:b14b1da8a018aa4db6ca8cbb927c32590bfc889b49116ea344c56e8351d94279 \
    https://raw.githubusercontent.com/supertone-oss-archive/supertonic/1e9799e964ea4c0dad7cde993b65c3c813a7b373/py/helper.py helper.py
COPY server.py .
EXPOSE 5000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]
