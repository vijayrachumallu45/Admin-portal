# NexusOps Admin Portal - local development image
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "wsgi.py"]
