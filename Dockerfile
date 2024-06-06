# Use the official Python image for the base image.
FROM python:3.11-slim

# Set environment variables to make Python print directly to the terminal and avoid .pyc files.
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install system dependencies required for pipx and Poetry.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install pipx.
RUN python3 -m pip install --no-cache-dir pipx \
    && pipx ensurepath

# Add poetry to the path
ENV PATH="${PATH}:/root/.local/bin"

# Install the latest version of Poetry using pipx.
RUN pipx install poetry

# Set the working directory.
WORKDIR /workspace

# Copy the pyproject.toml and poetry.lock files (if available) into the image.
COPY pyproject.toml poetry.lock* /workspace/

RUN poetry install --with dev

# Workspace content will be mounted, we don't need it in the image
RUN rm -r /workspace/*

# Entrypoint should be a shell in the workdir with poetry shell activated
# Before that, the project should be installed with poetry install
ENTRYPOINT ["/bin/bash", "-c", "poetry install --with dev && poetry shell && $0 $@"]
