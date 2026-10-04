# =============================================================
#  Backend Dockerfile - Python / FastAPI
# =============================================================

FROM python:3.11-slim

# System packages (ffmpeg + ffprobe + build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# The project root inside the container keeps backend.app.main importable.
WORKDIR /project

# Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The build context is ./backend; preserve the backend package path.
COPY . ./backend/

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--app-dir", "/project", "--host", "0.0.0.0", "--port", "8000", "--reload"]
