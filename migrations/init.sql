-- ============================================================================
-- Autonomous Agentic Trading System — Database Initialization
-- ============================================================================
-- This script runs on first PostgreSQL startup via docker-entrypoint-initdb.d.
-- It creates extensions needed by the application.
-- Actual table creation is handled by Alembic migrations or init_db().
-- ============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable JSON path queries for JSONB columns
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Trading Agent database initialized successfully';
END $$;
