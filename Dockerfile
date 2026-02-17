FROM python:3.12-slim

ENV http_proxy=http://cache.konts.lv:8080
ENV https_proxy=http://cache.konts.lv:8080
ENV no_proxy=localhost,127.0.0.1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000

CMD ["fastmcp", "dev", "server.py", "--transport", "sse", "--port", "8000", "--host", "0.0.0.0"]
