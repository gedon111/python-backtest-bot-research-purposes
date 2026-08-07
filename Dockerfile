# Build stage: compiles dashboard-v2 to static assets. Kept separate so the
# final image doesn't need Node.js/npm/node_modules at all -- Run_All.py's
# ensure_dashboard_built() sees the pre-built dashboard-v2/dist below (copied
# in with a newer mtime than src/) and correctly skips trying to invoke npm,
# which isn't installed in the final stage.
FROM node:20-slim AS dashboard-build
WORKDIR /app/dashboard-v2
COPY dashboard-v2/package.json dashboard-v2/package-lock.json ./
RUN npm ci
COPY dashboard-v2/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install standard compiler dependencies for speed/scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
RUN pip install --no-cache-dir pandas numpy sqlalchemy scikit-learn python-binance oauth2client gspread gspread-formatting

# Copy code, database, credentials, and artifacts
COPY . .

# Pre-built dashboard-v2 static assets, served at /dashboard/ by
# export_gui_data.py's SilentHandler.
COPY --from=dashboard-build /app/dashboard-v2/dist ./dashboard-v2/dist

# Expose the dashboard web server port
EXPOSE 8765

# By default, start the dashboard runner
CMD ["python", "Run_All.py"]
