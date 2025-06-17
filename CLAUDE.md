# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RMS-Shopify Integration is a bidirectional synchronization system between Microsoft Retail Management System (RMS) and Shopify. It automates the sync of products, inventory, prices (RMS → Shopify) and orders (Shopify → RMS).

## Common Development Commands

### Package Management (Poetry)
```bash
# Install all dependencies
poetry install

# Add new dependency
poetry add <package-name>

# Add development dependency
poetry add --group dev <package-name>

# Update dependencies
poetry update

# Generate requirements.txt (if needed)
poetry export -f requirements.txt --output requirements.txt
```

### Running the Application
```bash
# Development mode with auto-reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Using environment file
poetry run uvicorn app.main:app --env-file .env --reload
```

### Code Quality Tools
```bash
# Format code with Black
poetry run black app/

# Sort imports with isort
poetry run isort app/

# Lint with ruff
poetry run ruff check app/
poetry run ruff check app/ --fix  # Auto-fix issues

# Type checking with pyright
poetry run pyright app/

# Run all quality checks
poetry run black app/ && poetry run isort app/ && poetry run ruff check app/ && poetry run pyright app/
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_rms_to_shopify.py

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run tests with verbose output
poetry run pytest -v

# Run specific test
poetry run pytest tests/test_rms_to_shopify.py::test_sync_products -v
```

## High-Level Architecture

### Application Structure

The application follows a **layered architecture** with clear separation of concerns:

1. **API Layer** (`app/api/v1/`)
   - FastAPI routers define REST endpoints
   - Request/response validation using Pydantic schemas
   - Main endpoints: `/sync/*`, `/webhooks/*`, `/health`, `/metrics`

2. **Service Layer** (`app/services/`)
   - Business logic for synchronization
   - `RMSToShopifySync` class handles product/inventory sync
   - `ShopifyToRMSSync` class handles order sync
   - Error aggregation and batch processing

3. **Data Access Layer** (`app/db/`)
   - `rms_handler.py`: SQL Server connection and queries for RMS
   - `shopify_client.py`: HTTP client for Shopify API
   - Connection pooling and retry logic

4. **Core Infrastructure** (`app/core/`)
   - `config.py`: Centralized configuration using Pydantic Settings
   - `lifespan.py`: Application startup/shutdown events
   - `middleware.py`: CORS, rate limiting, security headers
   - `exception_handlers.py`: Global error handling
   - `health.py`: Health check implementation

### Key Design Patterns

1. **Factory Pattern**: Application creation in `main.py`
2. **Repository Pattern**: Data access abstraction
3. **Service Pattern**: Business logic encapsulation
4. **Error Aggregation**: Batch error handling for sync operations
5. **Background Tasks**: Async processing for long-running operations

### Configuration Management

All configuration is managed through environment variables:
- Required: RMS database credentials, Shopify API token
- Optional: Redis URL, email alerts, metrics settings
- See `.env.example` for all available options

### Error Handling Strategy

The application uses custom exception classes:
- `AppException`: Base exception class
- `SyncException`: Synchronization-specific errors
- `ShopifyAPIException`: Shopify API errors
- `RMSConnectionException`: Database connection errors
- `ValidationException`: Data validation errors
- `RateLimitException`: API rate limit errors

All exceptions are handled globally and return consistent JSON responses.

### Synchronization Flow

**RMS → Shopify:**
1. Extract products from RMS `View_Items`
2. Transform to Shopify format
3. Check existing Shopify products
4. Create/update in batches
5. Log results and metrics

**Shopify → RMS:**
1. Receive webhook or fetch orders
2. Validate order data
3. Map to RMS format
4. Insert into `ORDER`/`ORDERENTRY` tables
5. Update Shopify order status

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Development Workflow

1. **Environment Setup**: Copy `.env.example` to `.env` and configure
2. **Database Access**: Ensure SQL Server connection for RMS
3. **Shopify Setup**: Configure shop URL and access token
4. **Run Application**: Use poetry run commands above
5. **Test Endpoints**: Use Swagger UI for testing
6. **Monitor Logs**: Check console output and log files

### Important Considerations

- The application expects RMS database to have specific views/tables
- Shopify API version is configurable (default: 2024-01)
- Rate limiting is implemented for both RMS queries and Shopify API
- Background tasks are used for long-running sync operations
- Health checks verify all dependencies before marking as healthy