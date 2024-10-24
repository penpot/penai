# Use the official Python image for the base image.
# Note: The platform is explicitly set to linux/amd64 as Google Chrome won't work on ARM.
FROM --platform=linux/amd64 python:3.11-slim

# Set environment variables to make Python print directly to the terminal and avoid .pyc files.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies required for the project.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    wget \
    unzip \
    libvips-dev \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# install google chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

RUN CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}') && \
    echo "Chrome version: ${CHROME_VERSION}" && \
    wget https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver


# Install pipx.
RUN python3 -m pip install --no-cache-dir pipx \
    && pipx ensurepath

# Add poetry to the path
ENV PATH="${PATH}:/root/.local/bin"

# Install the latest version of Poetry using pipx.
RUN pipx install poetry

# Set the working directory. IMPORTANT: can't be changed as needs to be in sync to the dir where the project is cloned
# to in the codespace
WORKDIR /workspaces/penai

# Copy the pyproject.toml and poetry.lock files (if available) into the image.
COPY pyproject.toml poetry.lock* /workspaces/penai/

RUN poetry install --with dev

# Entrypoint should be a shell in the workdir with poetry shell activated
# Before that, the project should be installed with poetry install
ENTRYPOINT ["/bin/bash", "-c", "poetry install --with dev && poetry run jupyter trust notebooks/*.ipynb docs/02_notebooks/*.ipynb && poetry shell && $0 $@"]
