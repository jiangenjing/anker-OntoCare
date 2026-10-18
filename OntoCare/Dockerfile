FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
RUN mkdir -p data/handoffs uploads
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn judge_server:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 8 --timeout 120 --access-logfile -"]
