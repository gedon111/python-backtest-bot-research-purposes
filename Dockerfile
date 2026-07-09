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

# Expose the dashboard web server port
EXPOSE 8765

# By default, start the dashboard runner
CMD ["python", "Run_All.py"]
