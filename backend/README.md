# SegmentFlow Backend

FastAPI-based backend for the SegmentFlow video instance segmentation labeling tool.

## Features

- RESTful API with FastAPI
- Async database support (SQLite/PostgreSQL)
- SQLAlchemy 2.0 ORM
- Pydantic data validation
- Health check endpoint
- CORS middleware configured

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── api/
│   │   └── v1/
│   │       ├── api.py          # API router configuration
│   │       └── endpoints/      # API endpoints
│   │           └── health.py   # Health check
│   ├── core/
│   │   ├── config.py           # Settings and configuration
│   │   └── database.py         # Database setup
│   └── models/
│       ├── base.py             # Base model class
│       ├── project.py          # Project model
│       ├── label.py            # Label model
│       └── image.py            # Image model
├── requirements.txt
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the backend directory (optional - defaults will work):

```env
# Database (default: SQLite)
DATABASE_URL=sqlite+aiosqlite:///./segmentflow.db
# For PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost/segmentflow

# CORS origins
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Debug mode
DEBUG=true

# File storage
PROJECTS_ROOT_DIR=./data/projects

# Processing configuration
MAX_PROPAGATION_LENGTH=1000
INFERENCE_WIDTH=1024
OUTPUT_WIDTH=1920
MASK_TRANSPARENCY=0.5
BIG_JUMP_SIZE=10
```

### 3. Run the Server

```bash
# From the backend directory
python -m app.main

# Or use uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check

```bash
GET /api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "service": "SegmentFlow",
  "version": "0.1.0",
  "database": "connected"
}
```

### Root

```bash
GET /api/v1/
```

## Database

The application uses SQLAlchemy with async support. By default, it uses SQLite for easy setup. For production, PostgreSQL is recommended.

### Database Models

- **Project**: Annotation projects
- **Label**: Label class definitions
- **Image**: Video frames/images

All models inherit from `BaseModel` which provides:
- `id`: UUID primary key
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Next Steps (Sprint 1)

- Implement Project CRUD endpoints (DATA-002)
- Implement Label CRUD endpoints (DATA-003)
- Add authentication/authorization
- Set up WebSocket support for SAM inference
