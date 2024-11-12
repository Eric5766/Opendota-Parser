FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY opendota_monitor.py .

VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1
ENV HOURS_THRESHOLD=24
ENV CHECK_INTERVAL=1200

CMD ["python", "opendota_monitor.py"]