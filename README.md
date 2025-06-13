# README.md

## Introduction

Welcome to **FSKHTTP**, your virtual FSK modem accessible via simple HTTP calls. Imagine two autonomous bots at a "GibberLink" hackathon. Bot A initiates a session, Bot B answers, and they negotiate a high‑efficiency FSK channel. Instead of handling raw audio streams, each bot posts JSON payloads—inclusive of encrypted data—to FSKHTTP’s `/encode` endpoint and receives back a WAV file filled with FSK tones. That same WAV file, when posted to `/decode`, returns the original byte stream as JSON.

Under the hood, the battle‑tested **ggwave** library manages modulation, framing, sample rates, and error detection; FSKHTTP simply wraps it in a REST interface. Upper layers handle encryption, compression, and routing—FSKHTTP remains laser‑focused on byte‑to‑tone and tone‑to‑byte translation.

Want to see it in action? Check out these quick demos:


* <a href="https://github.com/absginc/fskhttp/raw/main/example_vids/fskhttp-curl.mp4">
  <img width="25%" src="https://github.com/absginc/fskhttp/raw/main/example_vids/fkxhttp-curl-preview.gif" alt="cURL → WAV demo preview">
</a>
* [▶️ cURL → WAV demo](./example_vids/fskhttp-curl.mp4)

* <a href="https://github.com/absginc/fskhttp/raw/main/example_vids/fskhttp-postman.mp4">
  <img width="25%" src="https://github.com/absginc/fskhttp/raw/main/example_vids/fkxhttp-postman-preview.gif" alt="Postman decode demo preview">
</a>
* [▶️ WAV → JSON demo](./example_vids/fskhttp-postman.mp4)


## Try the online demo

### Text → FSK → WAV

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"ROBOTS talking to ROBOTS bots will speak to bots"}' \
  https://fskhttps.sipsaker.com/encode \
  -o encoded.wav
```
RESPONSE
```bash
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  340k  100  340k  100    59   705k    122 --:--:-- --:--:-- --:--:--  704k
```
You can play encoded.wav, and also ship it back to be DECODED


### WAV → DECODE FSK → JSON TEXT

```bash
curl -X POST \
  -F "file=@encoded.wav" \
  https://fskhttps.sipsaker.com/decode
```

RESPONSE
```json
{
  "audio_info": {
    "bps": 16,
    "channels": 1,
    "sample_rate": 48000,
    "total_samples": 174080
  },
  "decoded_text": "ROBOTS talking to ROBOTS bots will speak to bots",
  "message_length": 48,
  "processing_thread": "ThreadPoolExecutor-0_0",
  "processing_time_seconds": 0.055,
  "success": true
}
```
## Quick Start

Get a single-instance service up in seconds:

### Option A: Pull from Docker Hub

```bash
# Replace <your-namespace> with your Docker Hub repo once published
docker run -d \
  --name fskhttp \
  -p 8080:8080 \
  <your-namespace>/fskhttp:latest
```

### Option B: Build and Run Locally

```bash
git clone https://github.com/your-org/fskhttp.git
cd fskhttp
# Build image
docker build -t fskhttp:latest .

# Run container
docker run -d \
  --name fskhttp \
  -p 8080:8080 \
  -e MAX_WORKERS=16 \
  -e MAX_CONCURRENT_REQUESTS=50 \
  fskhttp:latest
```

Verify the service:

```bash
curl http://localhost:8080/health
```

## Example Usage

### Encode Text → WAV

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"Service online: sending encrypted payload via FSK tones."}' \
  http://localhost:8080/encode \
  -o encoded.wav
```

### Decode WAV → Text

```bash
curl -X POST \
  -F "file=@encoded.wav" \
  http://localhost:8080/decode
```

[▶️ Watch Postman demo](./example_vids/fskhttp-postman.mp4)

[▶️ Watch cURL demo](./example_vids/fskhttp-curl.mp4)

## Production Deployment

For high availability, load‑balancing, health checks, and metrics, use Docker Compose:

```bash
git clone https://github.com/your-org/fskhttp.git
cd fskhttp
docker-compose up --build -d
```

This stack includes:

* **nginx**: HTTP load balancer on host port 8080, proxies `/encode`, `/decode`, `/health`, `/metrics`
* **fskhttp-1**, **fskhttp-2**: Two FSKHTTP replicas for throughput and redundancy
* **Prometheus**: Scrapes service metrics and health endpoints
* **Grafana**: Optional dashboard & alerting (admin/admin123)

Check status:

```bash
docker-compose ps
```

View metrics:

* Prometheus → [http://localhost:9090](http://localhost:9090)
* Grafana    → [http://localhost:3000](http://localhost:3000)

## Scaling & Kubernetes

A full scaling guide—covering tuning, HPA, security contexts, ingress TLS, resource quotas, and more—is available in **scaling\_guide.MD**. See [Scaling Guide →](./scaling_guide.MD)

## Why FSKHTTP?

* **Modular**: Drop‑in HTTP API for any system needing tone‑based data exchange.
* **Efficient**: Offloads audio encoding/decoding, letting bots focus on logic and encryption.
* **Extensible**: Layers above handle encryption, framing, and routing—FSKHTTP just handles the telecom layer.

Use FSKHTTP as your microservice for reliable, tone‑based signaling between machines, bots, or any application requiring an FSK channel over HTTP.
