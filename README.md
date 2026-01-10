# SegmentFlow

AI-Assisted Video Segmentation

A web-based AI-assisted video instance segmentation labeling tool using SAM3 (Segment Anything Model 3) for semi-automated annotation. The system enables users to manually label key frames and automatically propagate labels across video sequences, drastically reducing labeling time.

Tech Stack: FastAPI (Backend) + Vue 3 (Frontend) + SAM3 + SQLite/PostgreSQL

Target Users: ML engineers, data annotators, computer vision researchers

Key Differentiator: GPU-accelerated video propagation with real-time SAM3 inference (<50ms latency)

## Quick Start

### Prerequisites
- Ubuntu 22+
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Setup

```bash
# Clone repository
git clone <repo-url>
cd SegmentFlow

# Backend setup
cd backend
./install_python_environment.sh
cd ..

# Frontend setup
cd frontend
npm install
cd ..

# Start services
docker-compose up -d

# Run backend
cd backend && python -m uvicorn app.main:app --reload

# Run frontend (in another terminal)
cd frontend && npm run dev
```

Visit `http://localhost:5173` for the frontend and `http://localhost:8000/docs` for the API documentation.

## Documentation

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Complete development guide with setup, running servers, and code standards
- **[CI_CD_SETUP.md](./CI_CD_SETUP.md)** - GitHub Actions CI/CD pipeline documentation
- **[DOCKER_SETUP.md](./DOCKER_SETUP.md)** - Docker Compose configuration guide

## Validation & Testing

Run the all-in-one validation script:

```bash
# Full validation and tests
./scripts/validate-and-test.sh

# Backend only
./scripts/validate-and-test.sh backend

# Frontend only
./scripts/validate-and-test.sh frontend

# Run specific checks
./scripts/validate-and-test.sh lint       # Linting only
./scripts/validate-and-test.sh test       # Tests only
./scripts/validate-and-test.sh type       # Type checking only
./scripts/validate-and-test.sh format-fix # Auto-fix formatting
```

## Project Structure

```
SegmentFlow/
├── backend/                 # FastAPI backend
│   ├── app/
│   ├── tests/
│   ├── config.toml
│   └── pyproject.toml
├── frontend/                # Vue 3 frontend
│   ├── src/
│   ├── vite.config.ts
│   └── tsconfig.json
├── scripts/                 # Utility scripts
├── validate-and-test.sh     # All-in-one validation script
├── docker-compose.yml       # Local development services
└── DEVELOPMENT.md           # Development guide
```

## Contributing

1. See [DEVELOPMENT.md](./DEVELOPMENT.md) for setup and code standards
2. Create feature branch: `git checkout -b feature/feature-name`
3. Make changes and ensure all validations pass: `./scripts/validate-and-test.sh`
4. Commit with meaningful messages
5. Push and create a Pull Request
6. Ensure CI passes before merge

## Code Quality

This project enforces:
- **Linting:** Ruff (Python style, imports, common errors)
- **Type Checking:** MyPy (Python) + vue-tsc (TypeScript/Vue)
- **Testing:** Pytest (Python) with ≥80% coverage
- **Formatting:** Ruff formatter for consistent code style
- **CI/CD:** GitHub Actions on every PR

See [CI_CD_SETUP.md](./CI_CD_SETUP.md) for details.

## Technology Stack

### Backend
- FastAPI 0.128+
- SQLAlchemy 2.0+
- Pydantic 2.12+
- PostgreSQL 15+ / SQLite
- Pytest

### Frontend
- Vue 3.4+
- Vite 5+
- Pinia 2.1+
- Vue Router 4.2+
- TypeScript

### DevOps
- Docker & Docker Compose
- GitHub Actions CI/CD

## License

TBD

## Support

For issues and questions:
1. Check documentation files
2. Review GitHub issues
3. Create new issue with details

