# Build stage: compiles dashboard-v2 to static assets. Kept separate so the
# final image doesn't need Node.js/npm/node_modules at all -- Run_All.py's
# ensure_dashboard_built() sees the pre-built dashboard-v2/dist below (copied
# in with a newer mtime than src/) and correctly skips trying to invoke npm,
# which isn't installed in the final stage.
#
# node:24-slim matches the Node version this project is developed and
# tested against (Node 20 "Iron" left LTS maintenance in April 2026 -- see
# CHANGELOG.md's 2026-08-13 entry).
FROM node:24-slim AS dashboard-build
WORKDIR /app/dashboard-v2
COPY dashboard-v2/package.json dashboard-v2/package-lock.json ./
RUN npm ci
COPY dashboard-v2/ ./
RUN npm run build

# python:3.14-slim matches the Python version requirements.txt's pinned
# packages (pandas 3.0.0, numpy 2.4.2) are installed and tested against on
# this project's own dev machine -- see the "Requirements" section in
# README.md before changing this.
FROM python:3.14-slim

WORKDIR /app

# Install standard compiler dependencies for speed/scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements (single source of truth, shared with the
# native `pip install -r requirements.txt` path documented in README.md)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code, committed database snapshot, and committed artifacts. Does NOT
# copy credentials -- SERVICE KEY/ and .env* are excluded via .dockerignore
# on purpose, so a `docker build` never bakes a real key into an image
# layer. Supply credentials at `docker run` time instead: `-e
# BINANCE_API_KEY=...` / `-e GOOGLE_SHEET_ID=...` for the env vars, and
# `-v "./SERVICE KEY:/app/SERVICE KEY:ro"` to mount the service-account
# JSON in without it ever touching the image itself.
COPY . .

# Pre-built dashboard-v2 static assets, served at /dashboard/ by
# research_analysis.py's DashboardRequestHandler.
COPY --from=dashboard-build /app/dashboard-v2/dist ./dashboard-v2/dist

# Bind the dashboard server to all interfaces inside the container --
# `docker run -p` forwards host traffic to the container's external
# interface, not its loopback one, which 127.0.0.1 (the native-run default,
# see research_analysis.py's run_dashboard_server()) would silently refuse.
ENV DASHBOARD_HOST=0.0.0.0

# Without this, Python fully block-buffers stdout when it isn't a TTY (the
# case for `docker logs`/`docker run` without -t), so the pipeline's print
# statements only appear in bursts instead of as they happen. Verified via
# a live `docker run`: the ~2-3 minute pipeline run (which fetches candles
# from the live Binance API before falling back to the committed cache --
# see README.md's "Data pipeline overview") produced zero `docker logs`
# output until the very end without this.
ENV PYTHONUNBUFFERED=1

# Expose the dashboard web server port
EXPOSE 8765

# By default, start the dashboard runner
CMD ["python", "Run_All.py"]
