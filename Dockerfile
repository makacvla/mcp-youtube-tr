FROM python:3.12-slim

ENV http_proxy=http://proxy.server.com:8080
ENV https_proxy=http://proxy.server.com:8080
ENV no_proxy=localhost,127.0.0.1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, json; \
      req = urllib.request.Request('http://localhost:8000/mcp', \
      data=json.dumps({'jsonrpc':'2.0','method':'initialize','id':1,'params':{'capabilities':{},'protocolVersion':'0.1.0','clientInfo':{'name':'healthcheck','version':'1.0'}}}).encode(), \
      headers={'Content-Type':'application/json','Accept':'application/json'}); \
      urllib.request.urlopen(req, timeout=5)" || exit 1

# Ensure proper signal handling
STOPSIGNAL SIGTERM

CMD ["python", "server.py"]
