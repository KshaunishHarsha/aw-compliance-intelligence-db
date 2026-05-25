# Phase 1: Foundation

This document outlines the foundation layer built during Phase 1 of the Animal Welfare Compliance Intelligence Platform. 

## Overview
Phase 1 established the core infrastructure, database schemas, and service scaffolding required to support the data ingestion and retrieval pipelines. The environment provides a fully working local development setup via Docker Compose where the database, API, background worker, and task queue all start with a single command.

## Repository Structure
The project is split into frontend and backend components.

- **`backend/`**: A Python-based API server built with FastAPI. It contains directories for `api`, `ingestion`, `retrieval`, `chat`, `models`, `schemas`, `tasks`, `db`, and `storage`.
- **`frontend/`**: A Next.js (App Router) client with Tailwind CSS and TypeScript, initialized using `create-next-app`.
- **`docker-compose.yml`**: Infrastructure definitions.
- **`.env.example` & `.env`**: Environment configuration templates.

## Core Infrastructure
The application leverages containerized services for robust local development:
1. **PostgreSQL 15**: The primary datastore (`compliance_db`) with `pgvector` enabled for embedding storage and vector similarity search.
2. **Redis 7**: The message broker used by Celery for asynchronous task processing.
3. **API (FastAPI)**: The main backend web server, providing API routes and health checks, with SQLAlchemy ORM handling database sessions asynchronously.
4. **Worker (Celery)**: A background worker process that connects to Redis and executes long-running data ingestion tasks (like document OCR and embedding generation).

## Database Schema & Migrations
The database schema strictly maps to the Phase 1 specifications using SQLAlchemy 2.0 and Alembic.

- **`documents`**: Tracks uploaded files, storage paths, and processing status.
- **`document_metadata`**: Stores structured data extracted from the documents (e.g., species, facility name, categories).
- **`chunks`**: Stores segmented pieces of documents. This table features an automated Full-Text Search (FTS) trigger (`chunks_fts_trigger`) that populates a `TSVECTOR` column automatically based on chunk contents and summaries.
- **`embeddings`**: Stores `pgvector` 1536-dimensional embeddings for semantic search. Includes a custom `ivfflat` index optimized with cosine similarity (`vector_cosine_ops`).

Alembic handles the migrations, ensuring the database can be rebuilt from scratch cleanly using `alembic upgrade head`.

## Verification & Smoke Tests
To ensure the foundation is fully functional:
- A `GET /health` endpoint confirms the FastAPI application is running.
- A `GET /health/db` endpoint executes a test query (`SELECT 1`) to ensure the Postgres connection is healthy.
- Async Pytest scripts (`backend/tests/test_health.py`) validate the endpoints automatically.
- A custom verification script confirmed the successful initialization of `pgvector`, the FTS trigger firing, and the Celery worker processing queue items successfully.
