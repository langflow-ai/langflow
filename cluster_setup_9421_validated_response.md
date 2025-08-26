# Response for Issue #9421: Cluster Setup with Docker Compose

Hi @vishnu-facilio,

Excellent question! You're experiencing state inconsistency issues because each Langflow instance maintains its own local state. Here's how to properly set up a multi-node Langflow cluster:

## The Problem

Running separate Langflow instances without proper coordination causes the exact issues you're seeing - jobs created on one server can't be accessed from another. This happens because Langflow needs shared state management across nodes.

## Architecture Overview

Langflow **fully supports clustering** with proper configuration:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Frontend      │    │   Shared Storage│
│   (ALB/nginx)   │────│   (Static)      │    │   (EFS/S3)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
    ┌────┴────┬────────────┬────────────┐              │
    │         │            │            │              │
┌───▼───┐ ┌──▼────┐ ┌─────▼──┐ ┌──────▼──┐           │
│Node 1 │ │Node 2 │ │ Node 3 │ │         │◄──────────┘
│(API)  │ │(API)  │ │ (API)  │ │         │
└───┬───┘ └───┬───┘ └────┬───┘ │         │
    │         │          │     │         │
    └─────────┼──────────┼─────┤         │
              │          │     │         │
    ┌─────────▼──────────▼─────▼─────────▼┐
    │     Shared Services                 │
    │  ┌─────────┐ ┌─────────┐ ┌─────────┐│
    │  │PostgreSQL│ │  Redis  │ │RabbitMQ ││
    │  │   (RDS)  │ │(ElastiC)│ │(AmazonMQ)││
    │  └─────────┘ └─────────┘ └─────────┘│
    └──────────────────────────────────────┘
```

## Docker Compose Configuration

Based on Langflow's production docker-compose (`deploy/docker-compose.yml`), here's your multi-node setup:

### 1. Environment Variables (.env)
```bash
# Database (use your RDS endpoint)
LANGFLOW_DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/langflow
POSTGRES_DB=langflow
POSTGRES_USER=langflow
POSTGRES_PASSWORD=yourpassword

# Redis (use your ElastiCache endpoint)
LANGFLOW_REDIS_HOST=your-redis-cluster.cache.amazonaws.com
LANGFLOW_REDIS_PORT=6379
LANGFLOW_REDIS_DB=0
LANGFLOW_CACHE_TYPE=redis
RESULT_BACKEND=redis://your-redis-cluster:6379/0

# RabbitMQ (use your AmazonMQ or self-hosted)
BROKER_URL=amqp://admin:admin@your-rabbitmq:5672//
RABBITMQ_DEFAULT_USER=admin
RABBITMQ_DEFAULT_PASS=admin

# Deployment mode
LANGFLOW_BACKEND_ONLY=true  # For backend nodes
```

### 2. Backend Node Docker Compose (each EC2)
```yaml
version: '3.8'
services:
  langflow-backend:
    image: langflowai/langflow-backend:latest
    ports:
      - "7860:7860"
    environment:
      - LANGFLOW_DATABASE_URL=${LANGFLOW_DATABASE_URL}
      - LANGFLOW_REDIS_HOST=${LANGFLOW_REDIS_HOST}
      - LANGFLOW_REDIS_PORT=${LANGFLOW_REDIS_PORT}
      - LANGFLOW_CACHE_TYPE=redis
      - BROKER_URL=${BROKER_URL}
      - RESULT_BACKEND=${RESULT_BACKEND}
      - LANGFLOW_BACKEND_ONLY=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7860/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    volumes:
      - langflow-data:/app/data
    depends_on:
      - celeryworker

  celeryworker:
    image: langflowai/langflow-backend:latest
    environment:
      - LANGFLOW_DATABASE_URL=${LANGFLOW_DATABASE_URL}
      - BROKER_URL=${BROKER_URL}
      - RESULT_BACKEND=${RESULT_BACKEND}
    command: python -m celery -A langflow.worker.celery_app worker --loglevel=INFO --concurrency=2 -n worker@%h -P eventlet
    volumes:
      - langflow-data:/app/data

volumes:
  langflow-data:
    driver: local
```

### 3. Frontend Node (separate EC2)
```yaml
version: '3.8'
services:
  langflow-frontend:
    image: langflowai/langflow-frontend:latest
    ports:
      - "80:80"
    environment:
      - BACKEND_URL=http://your-alb-endpoint:7860
```

### 4. Load Balancer Configuration

**Option A: AWS Application Load Balancer**
- Target Group: All 3 backend EC2 instances on port 7860
- Health Check: `GET /health`
- Stickiness: Enable for WebSocket support

**Option B: Traefik (as used in Langflow's production setup)**
```yaml
services:
  traefik:
    image: traefik:v3.0
    command:
      - --providers.docker
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## Critical Configuration Points

1. **Shared Database**: All nodes MUST use the same PostgreSQL (your RDS)
2. **Redis for Sessions/Cache**: Required for shared state (`LANGFLOW_CACHE_TYPE=redis`)
3. **Celery Workers**: Distribute background tasks across nodes
4. **Message Queue**: RabbitMQ for task coordination
5. **Backend-Only Mode**: Set `LANGFLOW_BACKEND_ONLY=true` for API nodes

## Deployment Steps

1. **Prepare Shared Services**
   ```bash
   # Ensure RDS, Redis, and RabbitMQ are accessible from all EC2s
   # Update security groups accordingly
   ```

2. **Deploy on Each Backend EC2**
   ```bash
   # Copy docker-compose.yml and .env to each EC2
   docker-compose up -d
   ```

3. **Deploy Frontend (optional separate EC2)**
   ```bash
   docker-compose -f docker-compose.frontend.yml up -d
   ```

4. **Configure Load Balancer**
   - Add all backend instances to target group
   - Configure health checks on `/health`

5. **Verify Cluster**
   ```bash
   # Check health on each node
   curl http://node1:7860/health
   curl http://node2:7860/health
   curl http://node3:7860/health
   ```

## Monitoring

Langflow includes Flower for Celery monitoring:
```yaml
flower:
  image: langflowai/langflow-backend:latest
  command: python -m celery -A langflow.worker.celery_app flower --port=5555
  ports:
    - "5555:5555"
```

Access at `http://your-server:5555` to monitor worker status.

## Important Notes

1. **Shared Storage**: If using file uploads, consider EFS for shared storage across EC2s
2. **Database Migrations**: Run only once from a single node
3. **Celery Workers**: Can scale independently from API nodes
4. **WebSocket Support**: Ensure load balancer supports WebSocket for real-time features

This setup provides true high availability with automatic failover and proper state management across all nodes.

Best regards,
Langflow Support

---

## Additional Resources

- [Langflow Deployment Architecture](https://docs.langflow.org/deployment-architecture)
- [Production Best Practices](https://docs.langflow.org/deployment-prod-best-practices)
- Official Helm Charts for Kubernetes: https://github.com/langflow-ai/langflow-helm-charts