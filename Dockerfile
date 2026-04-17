FROM python:3.11-slim

WORKDIR /app

COPY skills/f5-allinone/requirements.txt .
RUN pip install --no-cache-dir requests urllib3

COPY skills/f5-allinone/ ./f5_allinone/

ENV PYTHONPATH=/app

CMD ["python3", "-c", "from f5_allinone.f5_client import F5Client; print('F5 client ready')"]
