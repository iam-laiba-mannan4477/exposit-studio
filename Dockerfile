# Exposit Studio — container image for a server (for example AWS EC2). Not needed on your laptop.
# Status: written and reviewed, NOT yet built or run (the development sandbox could not reach Docker Hub).

# ---- 1. web interface
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 2. application
FROM python:3.13-slim
# libgl1/libegl1: required by the Skia wheel on Linux. FFmpeg comes from the imageio-ffmpeg wheel.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 exposit
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt
COPY exposit/ exposit/
COPY examples/ examples/
COPY --from=web /web/dist web/dist
# Model files are baked into the image (about 120 MB, checksums verified by the download command).
RUN python -m exposit.cli models && mkdir -p /data && chown -R exposit:exposit /app /data
USER exposit
ENV EXPOSIT_HOST=0.0.0.0 EXPOSIT_PORT=8600 EXPOSIT_DATA=/data PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8600
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8600/api/health',timeout=4)"
CMD ["python", "-m", "exposit.cli", "serve"]
