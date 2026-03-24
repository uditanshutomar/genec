FROM python:3.13-slim

# Install Java 21 for JDT wrapper
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk-headless \
    maven \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /genec

# Copy requirements first for layer caching
COPY requirements.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Build JDT wrapper
RUN cd genec-jdt-wrapper && mvn clean package -q -DskipTests

# Install GenEC
RUN pip install -e .

# Verify installation
RUN genec --version && python -m pytest tests/ -c /dev/null -q --ignore=tests/integration

ENTRYPOINT ["genec"]
