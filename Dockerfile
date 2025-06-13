FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y \
    git \
    cmake \
    g++ \
    make \
    python3 \
    python3-pip \
    libsdl2-dev \
    procps \
    htop \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install flask ggwave numpy psutil python-dotenv gunicorn

RUN git clone --recursive https://github.com/ggerganov/ggwave.git /ggwave

WORKDIR /ggwave
RUN mkdir build && cd build && cmake .. && make

RUN mkdir -p /app

COPY fskhttp.py /app/fskhttp.py

WORKDIR /app

RUN useradd -m -u 1001 fskuser && chown -R fskuser:fskuser /app
USER fskuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8080/health').raise_for_status()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--threads", "4", "--worker-class", "gthread", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "100", "--timeout", "60", "--keep-alive", "2", "--log-level", "info", "fskhttp:app"]
