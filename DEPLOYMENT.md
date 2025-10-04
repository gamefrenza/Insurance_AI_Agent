# Insurance AI Agent - Deployment Guide

Complete guide for deploying the Insurance AI Agent API to various platforms.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Deployment](#cloud-deployment)
   - [AWS](#aws-deployment)
   - [Heroku](#heroku-deployment)
   - [Azure](#azure-deployment)
5. [Configuration](#configuration)
6. [Security](#security)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- OpenAI API Key
- Git

### Optional
- AWS CLI (for AWS deployment)
- Heroku CLI (for Heroku deployment)
- Azure CLI (for Azure deployment)

---

## Local Development

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/Insurance_AI_Agent.git
cd Insurance_AI_Agent
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
OPENAI_API_KEY=your-openai-api-key-here
API_KEYS=key1,key2,key3
API_HOST=0.0.0.0
API_PORT=8000
```

### 5. Run Application

```bash
# Direct run
python insurance_agent_api.py

# Or with uvicorn
uvicorn insurance_agent_api:app --reload --host 0.0.0.0 --port 8000
```

### 6. Test API

```bash
curl http://localhost:8000/health
```

Access API documentation at: http://localhost:8000/docs

---

## Docker Deployment

### 1. Build Docker Image

```bash
docker build -t insurance-agent-api:latest .
```

### 2. Run with Docker Compose

```bash
# Set environment variables
export OPENAI_API_KEY=your-key-here
export API_KEYS=key1,key2,key3

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Test Docker Deployment

```bash
curl http://localhost:8000/health
```

---

## Cloud Deployment

### AWS Deployment

#### Option 1: AWS Elastic Beanstalk

1. **Install EB CLI**
   ```bash
   pip install awsebcli
   ```

2. **Initialize EB Application**
   ```bash
   eb init -p docker insurance-agent-api --region us-east-1
   ```

3. **Create Environment**
   ```bash
   eb create insurance-agent-prod
   ```

4. **Set Environment Variables**
   ```bash
   eb setenv OPENAI_API_KEY=your-key \
             API_KEYS=key1,key2
   ```

5. **Deploy**
   ```bash
   eb deploy
   ```

6. **Access Application**
   ```bash
   eb open
   ```

#### Option 2: AWS ECS (Elastic Container Service)

1. **Create ECR Repository**
   ```bash
   aws ecr create-repository --repository-name insurance-agent-api
   ```

2. **Build and Push Image**
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin YOUR_ECR_URI
   
   # Build image
   docker build -t insurance-agent-api .
   
   # Tag image
   docker tag insurance-agent-api:latest YOUR_ECR_URI/insurance-agent-api:latest
   
   # Push image
   docker push YOUR_ECR_URI/insurance-agent-api:latest
   ```

3. **Create ECS Task Definition**
   
   Create `task-definition.json`:
   ```json
   {
     "family": "insurance-agent-api",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [
       {
         "name": "insurance-agent-api",
         "image": "YOUR_ECR_URI/insurance-agent-api:latest",
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "OPENAI_API_KEY",
             "value": "your-key"
           },
           {
             "name": "API_KEYS",
             "value": "key1,key2"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/insurance-agent-api",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         }
       }
     ]
   }
   ```

4. **Register Task Definition**
   ```bash
   aws ecs register-task-definition --cli-input-json file://task-definition.json
   ```

5. **Create ECS Service**
   ```bash
   aws ecs create-service \
     --cluster your-cluster \
     --service-name insurance-agent-api \
     --task-definition insurance-agent-api \
     --desired-count 2 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
   ```

---

### Heroku Deployment

1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create Heroku App**
   ```bash
   heroku create insurance-agent-api
   ```

3. **Set Stack to Container**
   ```bash
   heroku stack:set container
   ```

4. **Create `heroku.yml`**
   ```yaml
   build:
     docker:
       web: Dockerfile
   run:
     web: uvicorn insurance_agent_api:app --host 0.0.0.0 --port $PORT
   ```

5. **Set Environment Variables**
   ```bash
   heroku config:set OPENAI_API_KEY=your-key
   heroku config:set API_KEYS=key1,key2,key3
   ```

6. **Deploy**
   ```bash
   git push heroku main
   ```

7. **Open Application**
   ```bash
   heroku open
   ```

8. **View Logs**
   ```bash
   heroku logs --tail
   ```

---

### Azure Deployment

#### Option 1: Azure Container Instances

1. **Login to Azure**
   ```bash
   az login
   ```

2. **Create Resource Group**
   ```bash
   az group create --name insurance-agent-rg --location eastus
   ```

3. **Create Container Registry**
   ```bash
   az acr create --resource-group insurance-agent-rg \
                 --name insuranceagentacr \
                 --sku Basic
   ```

4. **Build and Push Image**
   ```bash
   az acr build --registry insuranceagentacr \
                --image insurance-agent-api:latest .
   ```

5. **Deploy Container Instance**
   ```bash
   az container create \
     --resource-group insurance-agent-rg \
     --name insurance-agent-api \
     --image insuranceagentacr.azurecr.io/insurance-agent-api:latest \
     --cpu 1 \
     --memory 2 \
     --registry-login-server insuranceagentacr.azurecr.io \
     --ip-address Public \
     --ports 8000 \
     --environment-variables \
       OPENAI_API_KEY=your-key \
       API_KEYS=key1,key2
   ```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for LLM |
| `API_KEYS` | Yes | test-key-12345 | Comma-separated API keys for authentication |
| `API_HOST` | No | 0.0.0.0 | API host address |
| `API_PORT` | No | 8000 | API port number |
| `API_RELOAD` | No | false | Enable auto-reload (development only) |

### API Keys Management

For production, use a secure secret management service:

**AWS Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name insurance-agent/api-keys \
  --secret-string '{"openai":"key1","api_keys":"key2,key3"}'
```

**Azure Key Vault:**
```bash
az keyvault create --name insurance-agent-vault \
                   --resource-group insurance-agent-rg \
                   --location eastus

az keyvault secret set --vault-name insurance-agent-vault \
                       --name openai-api-key \
                       --value your-key
```

---

## Security

### 1. API Key Authentication

All endpoints require `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/api/v1/quote
```

### 2. HTTPS Configuration

**For production, always use HTTPS:**

#### With Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### With Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d api.yourdomain.com
```

### 3. Rate Limiting

Add rate limiting middleware (production recommended):

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/quote")
@limiter.limit("10/minute")
async def generate_quote(request: Request, ...):
    ...
```

### 4. Security Headers

Add security headers in production:

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["api.yourdomain.com"])
```

---

## Monitoring

### 1. Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/api/v1/status
```

### 2. Logging

View application logs:

```bash
# Docker
docker-compose logs -f insurance-agent-api

# Heroku
heroku logs --tail

# AWS CloudWatch
aws logs tail /ecs/insurance-agent-api --follow
```

### 3. Metrics

Integration with monitoring tools:

**Prometheus:**
```python
from prometheus_client import Counter, Histogram

request_count = Counter('api_requests_total', 'Total API requests')
request_duration = Histogram('api_request_duration_seconds', 'Request duration')
```

**New Relic:**
```bash
pip install newrelic
newrelic-admin run-program uvicorn insurance_agent_api:app
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest test_tools.py -v

# Run specific test
pytest test_tools.py::TestQuotingTool::test_auto_insurance_quote -v

# With coverage
pytest --cov=. --cov-report=html
```

### Integration Tests

```bash
# Test API endpoints
pytest test_api.py -v
```

### Load Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 -H "X-API-Key: your-key" \
   http://localhost:8000/health

# Using Locust
pip install locust
locust -f locustfile.py
```

---

## Troubleshooting

### Common Issues

#### 1. "OPENAI_API_KEY not found"

**Solution:**
```bash
export OPENAI_API_KEY=your-key-here
# Or add to .env file
```

#### 2. "Port 8000 already in use"

**Solution:**
```bash
# Find process using port
lsof -i :8000
# Kill process
kill -9 <PID>
# Or use different port
export API_PORT=8001
```

#### 3. "Module not found" errors

**Solution:**
```bash
pip install -r requirements.txt --upgrade
```

#### 4. Docker build fails

**Solution:**
```bash
# Clear Docker cache
docker system prune -a
# Rebuild
docker-compose build --no-cache
```

#### 5. PDF generation errors

**Solution:**
```bash
# Install system dependencies
sudo apt-get install libpng-dev libjpeg-dev
```

### Debug Mode

Enable debug logging:

```python
# In insurance_agent_api.py
logging.basicConfig(level=logging.DEBUG)
```

---

## Scaling

### Horizontal Scaling

**Docker Swarm:**
```bash
docker swarm init
docker stack deploy -c docker-compose.yml insurance-agent
docker service scale insurance-agent_api=3
```

**Kubernetes:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: insurance-agent-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: insurance-agent-api
  template:
    metadata:
      labels:
        app: insurance-agent-api
    spec:
      containers:
      - name: api
        image: insurance-agent-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: openai-key
```

---

## Backup and Recovery

### Database Backup (if using)

```bash
# Backup
pg_dump insurance_db > backup.sql

# Restore
psql insurance_db < backup.sql
```

### Document Storage

Configure cloud storage for generated documents:

**AWS S3:**
```python
import boto3

s3 = boto3.client('s3')
s3.upload_file('document.pdf', 'insurance-docs', 'document.pdf')
```

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/Insurance_AI_Agent/issues
- Email: support@yourcompany.com
- Documentation: https://docs.yourcompany.com

---

## License

See LICENSE file for details.

