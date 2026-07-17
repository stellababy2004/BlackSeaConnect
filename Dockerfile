FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system blacksea \
    && useradd --system --gid blacksea --home-dir /app --shell /usr/sbin/nologin blacksea \
    && mkdir -p /app/data /tmp/gunicorn \
    && chown -R blacksea:blacksea /app /tmp/gunicorn

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=blacksea:blacksea . .

USER blacksea

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health/ready', timeout=3)" || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
