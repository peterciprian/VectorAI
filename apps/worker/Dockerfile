FROM python:3.11-slim

WORKDIR /app
RUN apt-get update \
	&& apt-get install -y --no-install-recommends libvips42 tesseract-ocr tesseract-ocr-hun \
	&& rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=INFO"]
