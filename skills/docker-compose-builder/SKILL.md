---
name: docker-compose-builder
description: "Docker Compose orchestration: multi-service setups, networking, volumes, health checks, production configs. Use when: building docker-compose.yml, setting up dev environments, configuring multi-container apps."
version: 1.0.0
---

# Docker Compose Builder

## Purpose

Design and build Docker Compose configurations for multi-service architectures.

## Production Template

```yaml
services:
  app:
    build:
      context: .
      target: production
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
    restart: unless-stopped

  db:
    image: postgres:17-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d app"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

## Rules

1. ALWAYS add health checks for all services
2. ALWAYS use `depends_on` with `condition: service_healthy`
3. ALWAYS set resource limits in production
4. Use named volumes for persistent data
5. Use `restart: unless-stopped` for production
6. Pin image versions — never use `latest` in production
7. Separate dev and prod configs: `docker-compose.yml` + `docker-compose.override.yml`
