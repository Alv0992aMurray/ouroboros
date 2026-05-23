# Ouroboros

> Automatically update your running Docker containers to the latest available image.

[![Docker Pulls](https://img.shields.io/docker/pulls/pyouroboros/ouroboros)](https://hub.docker.com/r/pyouroboros/ouroboros)
[![GitHub Issues](https://img.shields.io/github/issues/pyouroboros/ouroboros)](https://github.com/pyouroboros/ouroboros/issues)
[![License](https://img.shields.io/github/license/pyouroboros/ouroboros)](LICENSE)

Ouroboros will monitor your running Docker containers and update them to the latest available image — similar to [Watchtower](https://github.com/containrrr/watchtower) but with additional features like Prometheus metrics, notifications, and flexible scheduling.

## Features

- 🔄 Automatically pull latest images and recreate containers
- 📊 Prometheus metrics endpoint
- 🔔 Notifications via Apprise (Slack, Discord, Email, etc.)
- 🏷️ Monitor specific containers or all running containers
- ⏱️ Configurable polling interval or cron-style scheduling
- 🔒 Support for private registries with authentication
- 📝 Structured logging

## Quick Start

### Docker Run

```bash
docker run -d --name ouroboros \
  -v /var/run/docker.sock:/var/run/docker.sock \
  pyouroboros/ouroboros
```

### Docker Compose

```yaml
version: '3'
services:
  ouroboros:
    image: pyouroboros/ouroboros
    container_name: ouroboros
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CLEANUP=true
      - INTERVAL=300
      - LOG_LEVEL=info
      - SELF_UPDATE=true
      - NOTIFIERS=
```

## Configuration

Ouroboros can be configured via environment variables or command-line arguments.

| Environment Variable | CLI Flag | Default | Description |
|---|---|---|---|
| `INTERVAL` | `--interval` | `300` | Polling interval in seconds |
| `CRON` | `--cron` | `None` | Cron expression for scheduling |
| `LOG_LEVEL` | `--log-level` | `info` | Logging level (debug/info/warn/error) |
| `SELF_UPDATE` | `--self-update` | `False` | Update ouroboros itself |
| `CLEANUP` | `--cleanup` | `False` | Remove old images after update |
| `MONITOR` | `--monitor` | `[]` | Containers to monitor (default: all) |
| `IGNORE` | `--ignore` | `[]` | Containers to ignore |
| `NOTIFIERS` | `--notifiers` | `[]` | Apprise notification URLs |
| `REPO_USER` | `--repo-user` | `None` | Registry username |
| `REPO_PASS` | `--repo-pass` | `None` | Registry password |
| `METRICS_PORT` | `--metrics-port` | `8080` | Prometheus metrics port |

See [`.env.example`](.env.example) for a full list of configuration options.

## Metrics

When enabled, Ouroboros exposes a Prometheus metrics endpoint at `http://localhost:8080/metrics`.

Available metrics:

- `containers_updated_total` — Total number of container updates
- `containers_scanned_total` — Total number of containers scanned
- `ouroboros_up` — Whether Ouroboros is running

## Notifications

Ouroboros uses [Apprise](https://github.com/caronc/apprise) for notifications. Set the `NOTIFIERS` environment variable to a space-separated list of Apprise-compatible URLs.

```bash
# Slack
NOTIFIERS=slack://tokenA/tokenB/tokenC

# Discord
NOTIFIERS=discord://webhook_id/webhook_token

# Multiple
NOTIFIERS="slack://... discord://..."
```

## Development

### Prerequisites

- Python 3.8+
- Docker

### Setup

```bash
git clone https://github.com/pyouroboros/ouroboros.git
cd ouroboros
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
python -m ouroboros
```

### Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## License

MIT — see [LICENSE](LICENSE) for details.
