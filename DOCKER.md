# Docker Deployment Guide

This guide covers running Impulses using Docker Compose with PostgreSQL and persistent storage.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

## Quick Start

### 1. Setup Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Generate Secrets

**Generate application token:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Generate hashed token:**
```bash
python3 -c "import bcrypt, sys; token = input('Enter token: '); print(bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode())"
```

Update `TOKEN` and `HASHED_TOKEN` in `.env` file.

### 3. Configure Google OAuth2 (Optional)

If you want Google Calendar integration:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `http://localhost:8000/oauth2/google/callback`
4. Download credentials JSON
5. Update `GOOGLE_OAUTH2_CREDS` in `.env`

### 4. Start Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

### 5. Verify Deployment

```bash
# Check health
curl http://localhost:8000/healthz

# Should return: {"status":"UP"}
```

## Architecture

```
┌─────────────────────────────────────────────┐
│ Docker Compose                              │
│                                             │
│  ┌──────────────┐      ┌─────────────────┐│
│  │   postgres   │◄─────┤      app        ││
│  │  (port 5432) │      │  (port 8000)    ││
│  └──────┬───────┘      └────────┬────────┘│
│         │                       │          │
│         ▼                       ▼          │
│  ┌──────────────┐      ┌─────────────────┐│
│  │postgres_data │      │    app_data     ││
│  │   (volume)   │      │    (volume)     ││
│  └──────────────┘      └─────────────────┘│
└─────────────────────────────────────────────┘
```

## Volumes

### `postgres_data`
- PostgreSQL database files
- Users, tokens, sessions

### `app_data`
- File-based storage at `/app/data-store`
- User metrics
- Google Calendar event state
- Token credentials

## Configuration

### Environment Variables

All configured via `.env` file:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `POSTGRES_DB` | Database name | No | `impulses` |
| `POSTGRES_USER` | Database user | No | `impulses_user` |
| `POSTGRES_PASSWORD` | Database password | No | `impulses_password` |
| `PORT` | Application port | No | `8000` |
| `TOKEN` | Application auth token | **Yes** | - |
| `HASHED_TOKEN` | Bcrypt hash of TOKEN | **Yes** | - |
| `ORIGIN` | Base URL for OAuth | No | `http://localhost:8000` |
| `SESSION_TTL_SEC` | Session duration | No | `1800` |
| `GOOGLE_OAUTH2_CREDS` | Google OAuth JSON | **Yes** | - |

## Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Just the app
docker-compose logs -f app

# Just postgres
docker-compose logs -f postgres
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart app only
docker-compose restart app
```

### Stop Services

```bash
# Stop but keep containers
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (⚠️ deletes all data!)
docker-compose down -v
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U impulses_user -d impulses

# Run SQL
docker-compose exec postgres psql -U impulses_user -d impulses -c "SELECT * FROM app_user;"
```

### Backup Data

**Backup PostgreSQL:**
```bash
docker-compose exec postgres pg_dump -U impulses_user impulses > backup.sql
```

**Backup file storage:**
```bash
docker cp impulses-app:/app/data-store ./backup-data-store
```

### Restore Data

**Restore PostgreSQL:**
```bash
docker-compose exec -T postgres psql -U impulses_user impulses < backup.sql
```

**Restore file storage:**
```bash
docker cp ./backup-data-store/. impulses-app:/app/data-store
```

## Development Mode

For development with hot-reload:

```bash
# Use volume mounts for live code updates
docker-compose -f docker-compose.dev.yml up
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build

# Migrations run automatically on startup
```

## Troubleshooting

### App won't start

**Check logs:**
```bash
docker-compose logs app
```

**Common issues:**
- Missing environment variables (TOKEN, HASHED_TOKEN, GOOGLE_OAUTH2_CREDS)
- PostgreSQL not ready (wait for healthcheck)
- Port 8000 already in use

### Database connection failed

```bash
# Check postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Verify connection from app
docker-compose exec app pg_isready -h postgres -U impulses_user
```

### Data not persisting

Ensure volumes are created:
```bash
docker volume ls | grep impulses
```

Should see:
- `impulses_postgres_data`
- `impulses_app_data`

### Reset everything

```bash
# ⚠️ This deletes ALL data!
docker-compose down -v
docker-compose up -d
```

## Production Deployment

For production:

1. **Use secrets management** - Don't store credentials in `.env`
2. **Use external PostgreSQL** - Managed database service
3. **Use object storage** - S3/GCS instead of local volumes
4. **Enable HTTPS** - Add nginx/traefik reverse proxy
5. **Set strong passwords** - Generate secure tokens
6. **Enable monitoring** - Add Prometheus/Grafana
7. **Regular backups** - Automated database + storage backups

## Security Notes

- Change default PostgreSQL password
- Use strong application tokens
- Don't commit `.env` to version control
- Run behind HTTPS in production
- Limit PostgreSQL port exposure (remove `ports` section)
- Use Docker secrets for sensitive data

## Support

For issues, check:
1. Container logs: `docker-compose logs`
2. Health endpoint: `curl http://localhost:8000/healthz`
3. Database connectivity: `docker-compose exec app pg_isready -h postgres`
