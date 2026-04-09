# ============================================================
# APKeep Dashboard — Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 — Rust builder : compiles apkeep binary
#   Stage 2 — Python runtime: runs the dashboard
# ============================================================

# ── Stage 1: Build apkeep ────────────────────────────────────
FROM rust:1.75-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN cargo install apkeep

# ── Stage 2: Python runtime ──────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="APKeep Dashboard"
LABEL description="Cross-platform APK bulk downloader dashboard"

# Copy apkeep binary from builder stage
COPY --from=builder /usr/local/cargo/bin/apkeep /usr/local/bin/apkeep
RUN chmod +x /usr/local/bin/apkeep

# Install system utilities
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only the main script (always required)
COPY apkeep_dashboard.py .

# Copy packages.txt only if it exists — won't fail if missing
# We use a shell trick: copy the script itself as a dummy fallback
# The real solution is the entrypoint below which creates it if absent
COPY apkeep_dashboard.py packages_placeholder.tmp

# Create output + downloads directory
RUN mkdir -p /app/downloads

# Entrypoint script — creates empty packages.txt if not mounted
RUN printf '#!/bin/sh\n\
if [ ! -f /app/packages.txt ]; then\n\
  echo "# Add your package IDs here, one per line" > /app/packages.txt\n\
  echo "# Example: com.example.myapp" >> /app/packages.txt\n\
  echo "[INFO] packages.txt not found — created empty one at /app/packages.txt"\n\
fi\n\
rm -f /app/packages_placeholder.tmp\n\
exec python3 apkeep_dashboard.py\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Expose dashboard port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080 || exit 1

# Use entrypoint so packages.txt is always guaranteed to exist
ENTRYPOINT ["/app/entrypoint.sh"]
