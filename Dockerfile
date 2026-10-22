FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/app \
    YOLO_CONFIG_DIR=/home/app/.config/Ultralytics \
    GRADIO_ANALYTICS_ENABLED=False

WORKDIR /app

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl unixodbc libgssapi-krb5-2 \
    && curl -fsSLo /tmp/packages-microsoft-prod.deb \
       https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm /tmp/packages-microsoft-prod.deb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
# The official headless distribution preserves the ultralytics Python API and
# version while avoiding desktop OpenGL/LLVM dependencies in this web server.
RUN sed 's/^ultralytics==/ultralytics-opencv-headless==/' requirements.txt > /tmp/requirements-container.txt \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.14.1+cpu torchvision==0.29.1+cpu \
    && printf 'torch==2.14.1+cpu\ntorchvision==0.29.1+cpu\n' > /tmp/torch-constraints.txt \
    && python -m pip install --only-binary=pyodbc,opencv-python-headless -c /tmp/torch-constraints.txt -r /tmp/requirements-container.txt \
    && python -m pip check

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /app/uploads /home/app/.config/Ultralytics \
    && chown -R app:app /app/uploads /home/app

COPY app.py web_ui.py database.py security.py /app/
COPY services/*.py /app/services/
COPY weights/garbage_detect.pt /app/weights/garbage_detect.pt

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
