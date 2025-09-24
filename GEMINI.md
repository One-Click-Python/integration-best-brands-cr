# GEMINI.md - AI Project Context

This document provides an AI-friendly context for the **RMS-Shopify Integration** project. It is intended to be used by Gemini and other large language models to understand the project's architecture, conventions, and key components.

## Project Overview

This project is a bidirectional integration system between **Microsoft Retail Management System (RMS)** and **Shopify**. It is a **FastAPI** application written in **Python 3.13** that automates the synchronization of products, inventory, prices, and orders between a physical store using RMS and a Shopify e-commerce platform.

The application is designed with a modern, asynchronous, and modular architecture, making it scalable and maintainable. It features a robust automatic synchronization engine, a REST API for manual control, and comprehensive logging and monitoring capabilities.

### Key Technologies

- **Backend:** Python 3.13, FastAPI
- **Database (RMS):** SQL Server with SQLAlchemy (async)
- **Shopify API:** GraphQL and REST
- **Caching & Locking:** Redis
- **Task Scheduling:** APScheduler
- **Dependency Management:** Poetry
- **Containerization:** Docker, Docker Compose

### Core Features

- **Automatic Sync Engine:** Detects changes in RMS every 5 minutes.
- **Bidirectional Sync:** RMS <-> Shopify.
- **Advanced Taxonomy Mapping:** Maps RMS product categories to Shopify's Standard Product Taxonomy.
- **Structured Metafields:** Preserves RMS product attributes (size, color, etc.) as structured metafields in Shopify.
- **REST API:** Provides endpoints for manual synchronization, monitoring, and administration.
- **Webhooks:** Captures real-time events from Shopify.
- **Microservices-oriented Architecture:** The application is structured into modular services for different functionalities (e.g., `rms_to_shopify`, `shopify_to_rms`).

## Building and Running

### Prerequisites

- Python 3.13+
- Poetry
- Docker and Docker Compose
- Access to a SQL Server instance with the RMS database.
- Shopify store with API credentials.

### Local Development

1.  **Install Dependencies:**
    ```bash
    poetry install
    ```

2.  **Configure Environment:**
    Create a `.env` file in the project root, using `.env.example` as a template.

3.  **Run the Application:**
    ```bash
    poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
    ```

### Docker

The project is fully containerized. The `docker-compose.yml` file defines the `api` and `redis` services.

1.  **Build the Docker Image:**
    ```bash
    docker build -t rms-shopify-integration:latest .
    ```

2.  **Run with Docker Compose:**
    ```bash
    docker-compose up -d
    ```

## Development Conventions

- **Code Style:** The project uses **Black** for code formatting and **isort** for import sorting. **Ruff** is used for linting. Configuration for these tools is in `pyproject.toml`.
- **Modularity:** The application is organized into modules with a clear separation of concerns:
    - `app/api`: API endpoints and schemas.
    - `app/core`: Core application configuration, middleware, and exception handlers.
    - `app/db`: Database handlers and clients for RMS and Shopify.
    - `app/services`: Business logic for synchronization.
    - `app/utils`: Utility functions.
- **Configuration:** Application settings are managed through environment variables and parsed using Pydantic's `BaseSettings` in `app/core/config.py`.
- **Data Validation:** Pydantic is used extensively for data validation in API schemas and configuration.
- **Asynchronous Operations:** The application is built with `async`/`await` and uses asynchronous libraries like `SQLAlchemy[asyncio]`, `httpx`, and `aiohttp`.
- **GraphQL for Shopify:** The project uses GraphQL for most interactions with the Shopify API, with queries defined in `app/db/shopify_graphql_queries.py`.

## Key Files

- **`app/main.py`**: The entry point for the FastAPI application.
- **`app/core/config.py`**: Defines all application settings and configurations.
- **`docker-compose.yml`**: Defines the services, networks, and volumes for the Dockerized application.
- **`pyproject.toml`**: Defines project dependencies, scripts, and tool configurations.
- **`README.md`**: Provides a comprehensive overview of the project, including setup instructions and API documentation.
- **`app/services/rms_to_shopify.py`**: Contains the business logic for synchronizing data from RMS to Shopify.
- **`app/services/shopify_to_rms.py`**: Contains the business logic for synchronizing data from Shopify to RMS.
- **`app/db/rms_handler.py`**: Handles the connection and queries to the RMS SQL Server database.
- **`app/db/shopify_graphql_client.py`**: A client for interacting with the Shopify GraphQL API.
- **`app/db/shopify_graphql_queries.py`**: Contains all the GraphQL queries and mutations for the Shopify API.
