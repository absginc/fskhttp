# Kubernetes Deployment for FSK HTTP Service
apiVersion: v1
kind: Namespace
metadata:
  name: fskhttp
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: fskhttp-config
  namespace: fskhttp
data:
  FLASK_HOST: "0.0.0.0"
  FLASK_PORT: "8080"
  MAX_WORKERS: "16"
  MAX_CONCURRENT_REQUESTS: "50"
  REQUEST_TIMEOUT: "30"
  LOG_LEVEL: "INFO"
  HEALTH_CHECK_ENABLED: "true"
  TEMP_FILE_CLEANUP_INTERVAL: "300"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fskhttp-deployment
  namespace: fskhttp
  labels:
    app: fskhttp
    version: v2.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: fskhttp
  template:
    metadata:
      labels:
        app: fskhttp
        version: v2.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: fskhttp
        image: fskhttp:v2.0.0
        ports:
        - containerPort: 8080
          name: http
        envFrom:
        - configMapRef:
            name: fskhttp-config
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: INSTANCE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        volumeMounts:
        - name: tmp-volume
          mountPath: /tmp
      volumes:
      - name: tmp-volume
        emptyDir:
          sizeLimit: 1Gi
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        fsGroup: 1001
---
apiVersion: v1
kind: Service
metadata:
  name: fskhttp-service
  namespace: fskhttp
  labels:
    app: fskhttp
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
spec:
  selector:
    app: fskhttp
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fskhttp-ingress
  namespace: fskhttp
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/rate-limit-rps: "10"
    nginx.ingress.kubernetes.io/rate-limit-connections: "5"
spec:
  ingressClassName: nginx
  rules:
  - host: fskhttp.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: fskhttp-service
            port:
              number: 80
  # tls:
  # - hosts:
  #   - fskhttp.yourdomain.com
  #   secretName: fskhttp-tls
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fskhttp-hpa
  namespace: fskhttp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fskhttp-deployment
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: fskhttp-pdb
  namespace: fskhttp
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: fskhttp
