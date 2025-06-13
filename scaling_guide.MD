# FSK HTTP Service Scaling Guide

## Overview
This guide covers scaling strategies for the FSK HTTP service from single container to Kubernetes cluster deployment.

## Architecture Overview

```
Internet → Load Balancer → Multiple FSK HTTP Instances → Monitoring
```

## Quick Start (Single Container)

### 1. Basic Single Container
```bash
# Build the image
docker build -t fskhttp:v2.0.0 .

# Run single container with multi-threading
docker run -d \
  --name fskhttp \
  -p 8080:8080 \
  -e MAX_WORKERS=16 \
  -e MAX_CONCURRENT_REQUESTS=50 \
  fskhttp:v2.0.0
```

### 2. Test the Service
```bash
# Health check
curl http://localhost:8080/health

# Encode test
curl -X POST -H "Content-Type: application/json" \
  -d '{"text":"Hello World"}' \
  http://localhost:8080/encode \
  -o test.wav

# Decode test
curl -X POST -F "file=@test.wav" http://localhost:8080/decode
```

## Multi-Container Scaling

### 1. Docker Compose Deployment
```bash
# Start with load balancer
docker-compose up -d

# Scale to more instances
docker-compose up -d --scale fskhttp-1=3 --scale fskhttp-2=3

# Check status
docker-compose ps
```

### 2. Configuration Tuning
Edit `.env` file for different environments:

```bash
# Development
MAX_WORKERS=8
MAX_CONCURRENT_REQUESTS=25
LOG_LEVEL=DEBUG

# Production
MAX_WORKERS=32
MAX_CONCURRENT_REQUESTS=100
LOG_LEVEL=WARNING
REQUEST_TIMEOUT=60
```

## Kubernetes Deployment

### 1. Deploy to Kubernetes
```bash
# Apply all configurations
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get pods -n fskhttp
kubectl get svc -n fskhttp
kubectl get ingress -n fskhttp

# Check HPA status
kubectl get hpa -n fskhttp
```

### 2. Scaling Commands
```bash
# Manual scaling
kubectl scale deployment fskhttp-deployment --replicas=10 -n fskhttp

# Check auto-scaling
kubectl describe hpa fskhttp-hpa -n fskhttp

# Force scaling test
kubectl run -i --tty load-generator --rm --image=busybox --restart=Never -- /bin/sh
# Then run load tests from within the pod
```

### 3. Monitoring
```bash
# Check metrics
kubectl port-forward svc/prometheus 9090:9090 -n fskhttp
# Visit http://localhost:9090

# Check Grafana
kubectl port-forward svc/grafana 3000:3000 -n fskhttp
# Visit http://localhost:3000 (admin/admin123)
```

## Performance Tuning

### Container-Level Optimizations

1. **CPU and Memory Limits**
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

2. **Thread Pool Sizing**
```bash
# Rule of thumb: CPU cores * 2-4
MAX_WORKERS=$(nproc --all)
# For I/O intensive: CPU cores * 4-8
MAX_WORKERS=$(($(nproc --all) * 4))
```

3. **Gunicorn Configuration**
```bash
# In Dockerfile CMD:
--workers 4 \
--threads 4 \
--worker-connections 1000 \
--max-requests 1000 \
--timeout 60
```

### Load Balancer Optimizations

1. **Nginx Configuration**
```nginx
# Connection pooling
upstream fskhttp_backend {
    least_conn;
    keepalive 32;
    # Add more servers as needed
}

# Rate limiting per endpoint
location /decode {
    limit_req zone=upload burst=5 nodelay;
}
```

2. **Health Check Tuning**
```nginx
# Frequent health checks
server fskhttp-1:8080 max_fails=3 fail_timeout=30s;
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Request Metrics**
   - `fskhttp_requests_total` - Total requests
   - `fskhttp_requests_active` - Current active requests
   - `fskhttp_requests_per_second` - Request rate

2. **Performance Metrics**
   - Response time percentiles
   - Error rates
   - CPU/Memory usage

3. **System Metrics**
   - Container/Pod restarts
   - Network I/O
   - Disk usage (temp files)

### Alerting Rules

Critical alerts:
- Service down (>1 minute)
- High error rate (>10% for 2 minutes)
- High latency (>10s 95th percentile)
- Memory usage >85%

## Scaling Strategies

### 1. Vertical Scaling (Scale Up)
```bash
# Increase container resources
docker run -d \
  --memory=2g \
  --cpus=2 \
  -e MAX_WORKERS=32 \
  fskhttp:v2.0.0
```

### 2. Horizontal Scaling (Scale Out)

#### Docker Compose
```bash
# Add more service instances
docker-compose up -d --scale fskhttp-1=5
```

#### Kubernetes
```bash
# Auto-scaling based on CPU/Memory
kubectl autoscale deployment fskhttp-deployment \
  --cpu-percent=70 \
  --memory-percent=80 \
  --min=2 \
  --max=20
```

### 3. Geographic Scaling
```yaml
# Multi-region Kubernetes clusters
apiVersion: v1
kind: Service
metadata:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
```

## Load Testing

### 1. Basic Load Test
```bash
# Install tools
pip install locust requests

# Simple load test
locust -f load_test.py --host=http://localhost:8080
```

### 2. Load Test Script
```python
from locust import HttpUser, task, between
import random
import io

class FSKUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def encode_text(self):
        payload = {"text": f"Test message {random.randint(1000, 9999)}"}
        self.client.post("/encode", json=payload)
    
    @task(1)
    def health_check(self):
        self.client.get("/health")
```

### 3. Stress Testing
```bash
# High load test
locust -f load_test.py \
  --host=http://localhost:80 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=300s
```

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Check temp file cleanup
   - Adjust `TEMP_FILE_CLEANUP_INTERVAL`
   - Monitor for memory leaks

2. **Request Timeouts**
   - Increase `REQUEST_TIMEOUT`
   - Check ggwave binary performance
   - Monitor disk I/O

3. **Rate Limiting Issues**
   - Adjust nginx rate limits
   - Increase `MAX_CONCURRENT_REQUESTS`
   - Check load balancer configuration

### Debug Commands
```bash
# Container logs
docker logs -f fskhttp

# Kubernetes logs
kubectl logs -f deployment/fskhttp-deployment -n fskhttp

# Resource usage
docker stats
kubectl top pods -n fskhttp

# Health checks
curl -s http://localhost:8080/health | jq .
```

## Production Checklist

- [ ] SSL/TLS certificates configured
- [ ] Rate limiting properly configured
- [ ] Monitoring and alerting set up
- [ ] Log aggregation configured
- [ ] Backup strategy for configurations
- [ ] Security scanning completed
- [ ] Load testing completed
- [ ] Disaster recovery plan documented
- [ ] Auto-scaling configured and tested
- [ ] Health checks configured
- [ ] Resource limits set appropriately

## Cost Optimization

1. **Right-sizing containers**
   - Monitor actual resource usage
   - Adjust CPU/memory limits
   - Use spot instances where possible

2. **Efficient auto-scaling**
   - Configure appropriate scaling metrics
   - Set reasonable min/max replicas
   - Use predictive scaling if available

3. **Resource scheduling**
   - Use node affinity for efficient placement
   - Consider preemptible instances for non-critical workloads
