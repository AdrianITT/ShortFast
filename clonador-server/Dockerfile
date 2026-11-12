# Clonación de voz: conversor de timbre de OpenVoice v2 (MIT) sobre la voz de Supertonic. Versiones fijadas.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.15.0+cpu
RUN pip install --no-cache-dir librosa==1.0.1 soundfile==0.14.0 numpy==2.5.4 fastapi==0.162.4 uvicorn==0.54.0 \
      huggingface_hub==2.4.0 \
      # OpenVoice las importa al arrancar (textos en inglés/chino), aunque aquí no se usan:
      inflect==7.6.0 unidecode==1.4.0 eng_to_ipa==0.0.2 pypinyin==0.55.0 jieba==0.42.1 cn2an==0.5.24
# Solo el paquete de OpenVoice, sin sus dependencias antiguas (numpy 1.22, gradio 3…).
RUN pip install --no-cache-dir --no-deps \
      https://github.com/myshell-ai/OpenVoice/archive/74a1d147b17a8c3092dd5430504bd83ef6c7eb23.tar.gz
# Conversor de timbre v2 (131 MB), revisión fijada: el servicio funciona sin internet.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('myshell-ai/OpenVoiceV2', \
      revision='f36e7edfe1684461a8343844af60babc2efbb727', local_dir='/modelo', allow_patterns=['converter/*'])" \
    && rm -rf /modelo/.cache && pip uninstall -y huggingface_hub
WORKDIR /app
COPY server.py .
EXPOSE 5000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]
