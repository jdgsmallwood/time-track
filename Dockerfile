# ── Stage 1: build CSS ───────────────────────────────────────────────────────
FROM python:3.12-slim AS css-builder

WORKDIR /build

# Download Tailwind standalone CLI for the target arch
ARG TARGETARCH
RUN apt-get update -qq && apt-get install -y -qq curl ca-certificates \
    && ARCH=${TARGETARCH:-amd64} \
    && if [ "$ARCH" = "arm64" ]; then TAILWIND_ARCH="linux-arm64"; else TAILWIND_ARCH="linux-x64"; fi \
    && curl -sL "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${TAILWIND_ARCH}" \
       -o /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss

COPY static/css/input.css static/css/input.css
COPY templates/ templates/
COPY src/ src/

RUN tailwindcss -i static/css/input.css -o static/css/app.css --minify

# ── Stage 2: Python wheels ───────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update -qq && apt-get install -y -qq build-essential

COPY pyproject.toml .
COPY src/ src/
RUN pip install --upgrade pip --quiet \
    && pip wheel --no-deps --wheel-dir /wheels -e . --quiet \
    && pip wheel --wheel-dir /wheels \
       "django>=5.1,<6.0" gunicorn whitenoise django-environ \
       "google-auth>=2.30" "google-auth-oauthlib>=1.2" "google-api-python-client>=2.130" \
       "requests>=2.31" \
       --quiet

# ── Stage 3: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=timetrack.settings

WORKDIR /app

RUN addgroup --system app && adduser --system --group app

# Install wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl --quiet \
    && rm -rf /wheels

# Copy application
COPY --from=css-builder /build/static/css/app.css static/css/app.css
COPY static/vendor/ static/vendor/
COPY static/js/ static/js/
COPY templates/ templates/
COPY src/ src/
COPY manage.py .

# Collect static (runs against default SQLite settings; DB not needed for this)
RUN DATABASE_URL="sqlite:///tmp/build.db" SECRET_KEY="build-only" \
    python manage.py collectstatic --noinput --clear -v 0

COPY docker-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "timetrack.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
