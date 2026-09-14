FROM python:3.12-slim

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Make Python output appear immediately
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN useradd -m -u 1000 sandbox

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

# Create workspace
RUN mkdir -p /workspace && \
    chown -R sandbox:sandbox /workspace

# Run as non-root
USER sandbox

# Work inside the sandbox workspace
WORKDIR /workspace

# Keep the container alive.
# The adapter executes Python processes with docker exec.
CMD ["sleep", "infinity"]