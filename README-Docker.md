# Docker Deployment Guide

## Overview

This directory contains Docker and Kubernetes deployment configurations for the MCP OAuth setup with Okta authentication.

## File Structure

```
mcp-oauth-setup/
├── mcp-okta-server/
│   ├── Dockerfile              # Server container
│   └── ...
├── mcp-okta-client/
│   ├── Dockerfile              # Client container
│   └── ...
├── kubernetes/
│   ├── server-deployment.yaml  # K8s server deployment + service + secret
│   └── client-job.yaml         # K8s client job
├── docker-compose.yml          # Local development
└── README-Docker.md           # This file
```

## Docker Features

### Security
- ✅ **Non-root user**: Containers run as dedicated non-root users
- ✅ **Read-only filesystem**: Root filesystem is read-only
- ✅ **Dropped capabilities**: All Linux capabilities dropped
- ✅ **No privilege escalation**: Security context prevents privilege escalation

### Health Checks
- ✅ **Server health check**: Uses `.well-known/oauth-protected-resource` endpoint
- ✅ **Kubernetes probes**: Liveness and readiness probes configured
- ✅ **Resource limits**: Memory and CPU limits set

### uv Integration
- ✅ **Fast builds**: Uses uv for dependency management
- ✅ **Frozen dependencies**: `uv sync --frozen` for reproducible builds
- ✅ **Minimal image**: Based on python:3.12.9-slim

## Local Development

### Using Docker Compose

1. **Build and run server only**:
   ```bash
   docker-compose up mcp-server
   ```

2. **Build and run with client**:
   ```bash
   docker-compose --profile client up
   ```

3. **Background mode**:
   ```bash
   docker-compose up -d mcp-server
   ```

### Building Individual Images

1. **Build server**:
   ```bash
   cd mcp-okta-server
   docker build -t mcp-okta-server:latest .
   ```

2. **Build client**:
   ```bash
   cd mcp-okta-client
   docker build -t mcp-okta-client:latest .
   ```

### Running Containers

1. **Run server**:
   ```bash
   docker run -d \
     --name mcp-server \
     -p 8001:8001 \
     --env-file mcp-okta-server/.env \
     -e MCP_SERVER_HOST=0.0.0.0 \
     -e UV_CACHE_DIR=/tmp/uv-cache \
     mcp-okta-server:latest
   ```

2. **Run client** (interactive):
   ```bash
   docker run -it \
     --name mcp-client \
     --env-file mcp-okta-client/.env \
     -e MCP_SERVER_URL=http://host.docker.internal:8001/mcp \
     -e UV_CACHE_DIR=/tmp/uv-cache \
     mcp-okta-client:latest
   ```

## Kubernetes Deployment

### Prerequisites

1. **Kubernetes cluster** (minikube, kind, GKE, EKS, AKS, etc.)
2. **kubectl** configured
3. **Docker images** built and pushed to registry

### Deploy to Kubernetes

1. **Update secret values**:
   Edit `kubernetes/server-deployment.yaml` and replace placeholder values:
   ```yaml
   stringData:
     domain: "https://your-okta-domain.okta.com"
     client-id: "your-actual-client-id"
     client-secret: "your-actual-client-secret"
     audience: "api://mcp"
     issuer: "https://your-okta-domain.okta.com/oauth2/your-auth-server-id"
   ```

2. **Deploy server**:
   ```bash
   kubectl apply -f kubernetes/server-deployment.yaml
   ```

3. **Verify deployment**:
   ```bash
   kubectl get pods -l app=mcp-okta-server
   kubectl logs -l app=mcp-okta-server
   ```

4. **Port forward for testing**:
   ```bash
   kubectl port-forward service/mcp-okta-server 8001:8001
   ```

5. **Test server**:
   ```bash
   curl -H "MCP-Protocol-Version: 2025-06-18" \
        http://localhost:8001/.well-known/oauth-protected-resource
   ```

6. **Run client job**:
   ```bash
   kubectl apply -f kubernetes/client-job.yaml
   ```

7. **Check client logs**:
   ```bash
   kubectl logs job/mcp-okta-client
   ```

### Production Considerations

1. **External Secrets**: Use external secret management (AWS Secrets Manager, Azure Key Vault, etc.)
   ```yaml
   # Example with External Secrets Operator
   apiVersion: external-secrets.io/v1beta1
   kind: SecretStore
   metadata:
     name: aws-secrets-manager
   spec:
     provider:
       aws:
         service: SecretsManager
         region: us-west-2
   ```

2. **Ingress Configuration**:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: mcp-server-ingress
   spec:
     tls:
     - hosts:
       - mcp.yourdomain.com
       secretName: mcp-tls
     rules:
     - host: mcp.yourdomain.com
       http:
         paths:
         - path: /
           pathType: Prefix
           backend:
             service:
               name: mcp-okta-server
               port:
                 number: 8001
   ```

3. **Resource Requests/Limits**:
   ```yaml
   resources:
     requests:
       memory: "128Mi"
       cpu: "100m"
     limits:
       memory: "512Mi"
       cpu: "1000m"
   ```

4. **Horizontal Pod Autoscaler**:
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: mcp-server-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: mcp-okta-server
     minReplicas: 2
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
   ```

## Environment Variables

### Server (Required)
- `OKTA_DOMAIN`: Your Okta domain URL
- `OKTA_CLIENT_ID`: Okta application client ID
- `OKTA_CLIENT_SECRET`: Okta application client secret
- `OKTA_AUDIENCE`: OAuth audience (e.g., "api://mcp")
- `OKTA_ISSUER`: Okta authorization server issuer URL
- `MCP_REQUIRED_SCOPES`: Required OAuth scopes (e.g., "mcp:access")

### Server (Optional)
- `MCP_SERVER_HOST`: Bind host (default: "localhost", use "0.0.0.0" in containers)
- `MCP_SERVER_PORT`: Server port (default: "8001")
- `MCP_SERVER_URL`: External server URL for metadata

### Client (Required)
- `OKTA_DOMAIN`: Your Okta domain URL
- `OKTA_CLIENT_ID`: Okta application client ID
- `OKTA_CLIENT_SECRET`: Okta application client secret
- `OKTA_ISSUER`: Okta authorization server issuer URL (must match server)
- `MCP_REQUIRED_SCOPES`: OAuth scopes to request (e.g., "openid profile mcp:access")
- `MCP_SERVER_URL`: MCP server URL (e.g., "http://mcp-server:8001/mcp")

### Client (Optional)
- `VERIFY_SSL`: Enable/disable SSL certificate verification (default: "true", set to "false" for self-signed certificates)
- `CA_BUNDLE_PATH`: Path to custom CA bundle file for self-signed certificates (e.g., "/etc/ssl/certs/ca-bundle.crt")

## Client Considerations

The current client implementation is designed for interactive use (opens browser for OAuth flow). For containerized environments, consider these alternatives:

1. **Service Account Flow**: Use client credentials grant instead of authorization code
2. **Pre-authorized Tokens**: Mount long-lived tokens from secrets
3. **Headless Client**: Modify client for API-based token exchange
4. **Scheduled Jobs**: Run client as CronJob with stored refresh tokens

## Troubleshooting

### Common Issues

1. **Health check failures**:
   ```bash
   kubectl describe pod <pod-name>
   kubectl logs <pod-name>
   ```

2. **Secret not found**:
   ```bash
   kubectl get secrets
   kubectl describe secret okta-credentials
   ```

3. **Network connectivity**:
   ```bash
   kubectl exec -it <pod-name> -- curl http://mcp-server:8001/.well-known/oauth-protected-resource
   ```

4. **OAuth errors**:
   - Check Okta configuration
   - Verify redirect URIs
   - Confirm client credentials

### Debug Commands

```bash
# Check pod status
kubectl get pods -o wide

# View logs
kubectl logs -f deployment/mcp-okta-server

# Execute into container
kubectl exec -it deployment/mcp-okta-server -- /bin/bash

# Port forward for local testing
kubectl port-forward service/mcp-okta-server 8001:8001

# Test endpoints
curl -H "MCP-Protocol-Version: 2025-06-18" http://localhost:8001/.well-known/oauth-protected-resource
```

## SSL Configuration

### Self-Signed Certificates

If your MCP server uses self-signed certificates, you can disable SSL verification in the client:

**Environment Variable:**
```bash
VERIFY_SSL=false
```

**Docker Run:**
```bash
docker run -it \
  --name mcp-client \
  --env-file mcp-okta-client/.env \
  -e VERIFY_SSL=false \
  mcp-okta-client:latest
```

**Kubernetes:**
```yaml
- name: VERIFY_SSL
  value: "false"
```

**Security Warning:** Disabling SSL verification removes protection against man-in-the-middle attacks and should only be used in testing environments or with self-signed certificates in controlled environments.

### Custom CA Bundle

For production environments with self-signed certificates, use a custom CA bundle:

**Environment Variable:**
```bash
CA_BUNDLE_PATH=/etc/ssl/certs/ca-bundle.crt
```

**Docker Run with Volume Mount:**
```bash
docker run -it \
  --name mcp-client \
  --env-file mcp-okta-client/.env \
  -e CA_BUNDLE_PATH=/etc/ssl/certs/ca-bundle.crt \
  -v /path/to/your/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt:ro \
  mcp-okta-client:latest
```

**Kubernetes with ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ca-bundle
data:
  ca-bundle.crt: |
    -----BEGIN CERTIFICATE-----
    # Your CA certificate content here
    -----END CERTIFICATE-----
---
# In deployment spec:
spec:
  template:
    spec:
      containers:
      - name: mcp-client
        env:
        - name: CA_BUNDLE_PATH
          value: "/etc/ssl/certs/ca-bundle.crt"
        volumeMounts:
        - name: ca-bundle
          mountPath: /etc/ssl/certs/ca-bundle.crt
          subPath: ca-bundle.crt
          readOnly: true
      volumes:
      - name: ca-bundle
        configMap:
          name: ca-bundle
```

### Production SSL

For production environments with self-signed certificates, consider:
1. Using a custom CA bundle (recommended, as implemented above)
2. Adding the certificate to the system trust store
3. Implementing certificate pinning

This setup provides a production-ready containerized deployment of the MCP OAuth system with proper security, monitoring, and scalability considerations.
