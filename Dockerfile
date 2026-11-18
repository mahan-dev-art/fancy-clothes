# Delta Shop store — deploy on Deplexo
# No pip dependencies: serve.py uses only the Python standard library,
# so there is nothing to install. The image stays small on purpose
# (Deplexo free plan: ~128 MB RAM, ~250 MB disk).
FROM python:3.12-slim

WORKDIR /app

# Copy only what the server needs (see .dockerignore).
COPY serve.py products.json admin.html ./
COPY site/ ./site/

ENV PYTHONUNBUFFERED=1

# Deplexo runs the container read-only except for the /data volume:
# serve.py keeps products.json and uploaded pictures there so admin
# changes survive redeploys.
ENV DATA_DIR=/data

# Hint only: the real port comes from the PORT environment variable
# that Deplexo sets at runtime (serve.py reads it, default 8080).
EXPOSE 8080

CMD ["python3", "serve.py"]
