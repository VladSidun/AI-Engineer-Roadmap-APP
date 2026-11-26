FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /quest
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/quest/backend
COPY backend/requirements.lock .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend/ backend/
COPY curriculum/ curriculum/
COPY runner/quest_runner/suites/ runner/quest_runner/suites/
COPY --from=web /web/dist static/
RUN useradd --no-create-home quest
USER quest
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers --no-access-log"]
