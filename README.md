# FSKHTTP
A virtual FSK Modem HTTP microservice made for efficient bot/agent ↔️ bot/agent communications.

## Introduction

**FSKHTTP** is a virtual frequency-shift keying modem packaged as an HTTP microservice. Imagine two autonomous bots meeting in the wild.  This scenario was played out in a recently hackathon and they called this "GibberLink".   Bot A initiates a call, and Bot B answers. Realizing they are both BOTs, they agree on an optimized communications method.  Instead of converting text to speech and back, each bot posts its payload as JSON to the /encode endpoint of FSKHTTP  and receives a WAV file containing FSK tones.  When that WAV is submitted to the /decode endpoint, it extracts the original byte stream and delivers it  back as JSON.

Under the hood, the battle‑tested **ggwave** library manages modulation, framing, sample rates, and error detection; FSKHTTP wraps it in a REST interface.  Upper layers can optionally handle encryption, compression, and routing while FSKHTTP remains laser‑focused on byte‑to‑tone and tone‑to‑byte translation as a microservice.

Want to see it in action? Click the previews below to play the full demo videos:

* CURL EXAMPLE  
  <a href="https://youtu.be/Ljtt9q0Xdco" target="_blank" rel="noopener noreferrer">
    <img
      width="25%"
      src="https://github.com/absginc/fskhttp/raw/main/example_vids/fkxhttp-curl-preview.gif"
      alt="cURL → WAV demo preview"
    />
  </a>

* POSTMAN EXAMPLE  
  <a href="https://youtube.com/shorts/DiyRPAXlLL4" target="_blank" rel="noopener noreferrer">
    <img
      width="25%"
      src="https://github.com/absginc/fskhttp/raw/main/example_vids/fkxhttp-postman-preview.gif"
      alt="Postman decode demo preview"
    />
  </a>
## Try it with the online demo

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
You can play the `encoded.wav` Also ship it back to the /decode endpoint to be DECODED


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

Get started quickly with a single-instance service and have it up in seconds:

### Option A: Pull from Docker Hub

```bash
docker run -d \
  --name fskhttp_service \
  -p 8080:8080 \
  absgscott/fskhttp_service:latest
```

####  Run the pulled image
```bash
docker run -d \
  --name fskhttp_service \
  -p 8080:8080 \
  -e MAX_WORKERS=16 \
  -e MAX_CONCURRENT_REQUESTS=50 \
  absgscott/fskhttp_service:latest
```

### Option B: Build and Run Locally

```bash
git clone https://github.com/absginc/fskhttp.git
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
https://youtube.com/shorts/DiyRPAXlLL4

[▶️ Watch Postman demo](https://youtube.com/shorts/DiyRPAXlLL4)

[▶️ Watch cURL demo](https://youtu.be/Ljtt9q0Xdco)

## Production Deployment

For high availability, load‑balancing, health checks, and metrics, use Docker Compose:

```bash
git clone https://github.com/absginc/fskhttp.git
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

A full scaling guide covering [Kubernetes](./kubernetes.ctl), tuning, HPA, security contexts, ingress TLS, resource quotas, and more is available in **scaling\_guide.MD**. See [Scaling Guide →](./scaling_guide.MD)

## Why FSKHTTP?

* **Modular**: Drop‑in HTTP API for any system needing tone‑based data exchange.
* **Efficient**: Offloads audio encoding/decoding, letting bots focus on logic and encryption.
* **Extensible**: Layers above handle encryption, framing, and routing—FSKHTTP just handles the audio layer.

Use FSKHTTP as your microservice for reliable, tone‑based signaling between machines, bots, or any application requiring an FSK channel, utilized simply over HTTP.
