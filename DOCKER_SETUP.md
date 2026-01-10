# Docker Compose Setup for SegmentFlow

This docker-compose configuration provides a complete local development environment with PostgreSQL, Redis, FastAPI backend, and Vue 3 frontend for the SegmentFlow application.

## Services

- **PostgreSQL 15**: Primary database for project, labels, images, and masks
  - Host: `localhost:5432`
  - Database: `segmentflow`
  - User: `segmentflow`
  - Password: `segmentflow_dev_password`

- **Redis 7**: Cache and message broker for async tasks
  - Host: `localhost:6379`

- **FastAPI Backend**: Python web server with async database support
  - Host: `localhost:8000`
  - API Base: `http://localhost:8000/api/v1`
  - API Documentation: `http://localhost:8000/docs`
  - Auto-reload enabled for development

- **Vue 3 Frontend**: Modern web UI with Vite bundler
  - Host: `localhost:5173`
  - URL: `http://localhost:5173`
  - Hot Module Replacement (HMR) enabled for development

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your system
- Git (to clone the repository)

### Starting All Services

```bash
# Navigate to project root
cd SegmentFlow

# Build and start all services in the background
docker-compose up -d

# Wait for services to become healthy (~15 seconds)
docker-compose ps

# View logs while services start
docker-compose logs -f
```

### Accessing Services

Once all services are healthy:

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Stopping Services

```bash
# Stop all services (keeps data in volumes)
docker-compose down

# Stop services and remove volumes (WARNING: deletes database)
docker-compose down -v

# Rebuild images after dependency changes
docker-compose up -d --build
```

## Service Details

### Health Checks

All services include health checks that verify they're ready:

- **PostgreSQL**: Checks with `pg_isready`
- **Redis**: Checks with `redis-cli ping`
- **Backend**: Checks FastAPI health endpoint
- **Frontend**: Checks HTTP response status

View health status:
```bash
docker-compose ps
```

Expected output:
```
NAME                       IMAGE                      STATUS
segmentflow-postgres       postgres:15-alpine        Up (healthy)
segmentflow-redis          redis:7-alpine            Up (healthy)
segmentflow-backend        segmentflow-backend       Up (healthy)
segmentflow-frontend       segmentflow-frontend      Up (healthy)
```

### Backend Service

**Image**: Built from `backend/Dockerfile`  
**Environment Variables**:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`
- `DB_PASSWORD_FILE`: Path to the DB password secret (`/run/secrets/postgres_password`)
- `DATABASE_URL`: Optional override; if absent, assembled from the above
- `REDIS_URL`: Redis connection URL
- `ENVIRONMENT`: Set to `development`
- `DEBUG`: Set to `True`
- `CORS_ORIGINS`: Allows frontend and backend origins

**Features**:
- Auto-reload enabled for development (source code at `./backend` is volume-mounted)
- Hot-reloading on file changes
- Connects to PostgreSQL and Redis services
- Uses a Docker secret for the DB password (no plaintext in compose)

### Frontend Service

**Image**: Built from `frontend/Dockerfile` (multi-stage Node.js build)  
**Environment Variables**:
- `VITE_API_URL`: Points to backend container at `http://backend:8000/api/v1`

**Features**:
- Built with Vite for fast development
- Served with `serve` package in production mode
- For HMR, run locally via `npm run dev` (Workflow 2)

## Development Workflows

### Workflow 1: Full Docker Development (Recommended)

Everything runs in containers with automatic reloading:

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# Watch backend logs
docker-compose logs -f backend

# Watch frontend logs in another terminal
docker-compose logs -f frontend

# Make changes to source files - they auto-reload!
# Edit backend/app/* or frontend/src/* as needed

# Stop everything when done
docker-compose down
```

**Pros**:
- No local Python/Node setup required
- Isolated dependencies
- All services in one command

**Cons**:
- Slightly slower file sync (bind mounts)
- IDE integration more complex

### Workflow 2: Mixed Development (Docker Services + Local Apps)

Run databases in Docker, apps locally for better IDE integration:

```bash
# Start only PostgreSQL and Redis
docker-compose up -d postgres redis

# In Terminal 1: Run backend locally
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://segmentflow:segmentflow_dev_password@localhost:5432/segmentflow
export REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --reload

# In Terminal 2: Run frontend locally
cd frontend
npm install
npm run dev

# Access: http://localhost:5173
```

**Pros**:
- Better IDE integration
- Faster file reload
- Easier debugging

**Cons**:
- Need Python 3.11+ and Node 20+ locally
- More manual setup

### Workflow 3: Minimal (Only databases)

Use Docker for just databases, all apps local:

```bash
# Start only PostgreSQL and Redis
docker-compose up -d postgres redis

# Run backend and frontend as in Workflow 2
# (See above for details)
```

## Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Follow with timestamps
docker-compose logs -f --timestamps

# Last 100 lines
docker-compose logs --tail 100
```

### Connect to PostgreSQL

```bash
# Via container
docker-compose exec postgres psql -U segmentflow -d segmentflow

# Via local psql (if installed)
psql postgresql://segmentflow:segmentflow_dev_password@localhost:5432/segmentflow
```

### Rotate the database password (non-destructive)

Use the helper script to generate a new strong password, apply it to Postgres, and restart the backend:

```bash
./scripts/rotate_db_password.sh

# Verify backend health after rotation
curl -s http://localhost:8000/api/v1/health
```

What the script does:
- Generates a new 48-char alphanumeric password and writes `secrets/postgres_password.txt`
- Executes `ALTER ROLE segmentflow WITH PASSWORD '<new>'` inside Postgres
- Restarts the backend so it reads the updated secret

If you want to reset everything (data loss):

```bash
docker-compose down -v
./scripts/rotate_db_password.sh
docker-compose up -d --build
```

### Access Redis

```bash
# Redis CLI in container
docker-compose exec redis redis-cli

# From local machine (if redis-cli installed)
redis-cli -h localhost -p 6379
```

### Execute Commands in Container

```bash
# Run migrations (when available)
docker-compose exec backend alembic upgrade head

# Run tests
docker-compose exec backend pytest

# Install new Python packages
docker-compose exec backend pip install <package>
```

### View Volumes

```bash
# List all Docker volumes
docker volume ls | grep segmentflow

# Inspect volume
docker volume inspect segmentflow_postgres_data
```

## Troubleshooting

### Services won't start

```bash
# Check for port conflicts
lsof -i :8000  # Backend port
lsof -i :5173  # Frontend port
lsof -i :5432  # PostgreSQL port
lsof -i :6379  # Redis port

# If ports are in use, either:
# 1. Kill the process using the port
# 2. Or change the port in docker-compose.yml
```

### PostgreSQL connection issues

```bash
# Check if container is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec -T postgres pg_isready -U segmentflow

# Try connecting
docker-compose exec postgres psql -U segmentflow -d segmentflow
```

### Redis connection issues

```bash
# Check if container is running
docker-compose ps redis

# Test connectivity
docker-compose exec redis redis-cli ping

# View Redis logs
docker-compose logs redis
```

### Backend can't connect to database

```bash
# Ensure PostgreSQL is healthy
docker-compose ps postgres

# Check backend logs
docker-compose logs backend

# Verify database environment variables in backend service (docker-compose.yml)
# For example:
#   DB_HOST=postgres
#   DB_PORT=5432
#   DB_NAME=segmentflow
#   DB_USER=segmentflow
#   DB_PASSWORD_FILE=/run/secrets/db_password

# Test connection from backend container
docker-compose exec backend python -c "import asyncio; from app.core.database import engine; asyncio.run(engine.connect())"
```

### Frontend can't connect to backend

```bash
# Check backend is running and healthy
docker-compose ps backend

# Check backend logs
docker-compose logs backend

# Verify VITE_API_URL in frontend service
# Should be: http://backend:8000/api/v1 (internal)

# Or if running locally, use: http://localhost:8000/api/v1
```

### Reset everything and start fresh

```bash
# Stop and remove everything
docker-compose down -v

# Remove images (optional)
docker rmi segmentflow-backend segmentflow-frontend

# Start fresh
docker-compose up -d
```

## Docker Compose Configuration Details

### Service Dependencies

- **backend** depends on:
  - `postgres` (waits for health check)
  - `redis` (waits for health check)
- **frontend** depends on:
  - `backend` (waits for service start)

Dependencies ensure services start in the correct order.

### Volumes

Persistent volumes:
- `postgres_data`: Stores PostgreSQL database files
- `redis_data`: Stores Redis persistence files

Bind mounts (for development):
- `./backend:/app`: Live code reload for backend
- `./frontend:/app`: Live code reload for frontend

### Networks

All services connect via `segmentflow-network` bridge network, allowing:
- Service-to-service communication by name (e.g., `postgres:5432`)
- Isolation from other Docker networks

## Production Considerations

**Note**: This setup is for development only. For production:

1. Use environment-specific docker-compose files
2. Add authentication and secrets management
3. Use strong passwords (not `segmentflow_dev_password`)
4. Consider using managed databases (AWS RDS, Google Cloud SQL)
5. Add reverse proxy (Nginx) for SSL/TLS
6. Setup proper logging and monitoring
7. Use read-only root filesystems
8. Set resource limits (CPU, memory)

See DEPLOY-001 in the project plan for production setup details.

## Notes

- **Default credentials** (`segmentflow`/`segmentflow_dev_password`) are for development only
- **Persistent volumes** survive container restarts but are deleted with `docker-compose down -v`
- **Network isolation** via `segmentflow-network` enables service-to-service communication
- **Health checks** ensure services are ready before dependent services start
- **Volume mounts** enable live code reloading during development

## Next Steps

1. Complete SETUP-001: Initialize FastAPI backend structure with SQLAlchemy ORM
2. Complete SETUP-002: Initialize Vue 3 frontend with Vite, Pinia, Vue Router
3. Implement database models in [backend/app/models](backend/app/models)
4. Create database migrations using Alembic
5. Start implementing features from Sprint 1
