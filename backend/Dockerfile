# Optional. Higashi does NOT require Docker: the supported install is
#   curl -fsSL https://hws.jotnotes.com/releases/install.sh | sudo sh
# which needs only Python 3.9+ and systemd. This image exists for people who
# would rather run it in a container.
#
# Corrected 2026-10-02. The previous version installed gcc and libpq-dev to build
# a PostgreSQL driver, and pointed at requirements.txt - both left over from a
# PostgreSQL/Redis stack the product no longer uses. It also ran uvicorn with
# --reload, a development flag that has no business in a built image.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

COPY . .

# SQLite, in a volume you mount, is the database.
ENV DATABASE_URL=sqlite+aiosqlite:////data/hws.db
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
