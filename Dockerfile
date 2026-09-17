# Java APEX single-container deployment image.
#
# This builds the React frontend first, then packages the compiled static
# assets into the Python/FastAPI backend image so both apps run from one
# container and one origin.

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend

COPY APEX-Frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY APEX-Frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS backend-runtime

# -- OS packages ------------------------------------------------------------ #
# git is non-negotiable: Discovery cannot clone a repository without it.
# curl/unzip are only needed to fetch the Java toolchain below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        unzip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -- Java toolchain --------------------------------------------------------- #
# Installed under /opt/java/jdk-<major>, which matters: _discover_jdks()
# (app/infrastructure/java_runtime.py) scans /opt/java and infers the major
# version from the directory name via _infer_major_from_name().
ARG JDK_VERSIONS="11 17 21 25"
RUN set -eux; \
    mkdir -p /opt/java; \
    for major in ${JDK_VERSIONS}; do \
        curl -fsSL -o /tmp/jdk.tar.gz \
            "https://api.adoptium.net/v3/binary/latest/${major}/ga/linux/x64/jdk/hotspot/normal/eclipse"; \
        mkdir -p "/opt/java/jdk-${major}"; \
        tar -xzf /tmp/jdk.tar.gz -C "/opt/java/jdk-${major}" --strip-components=1; \
        rm /tmp/jdk.tar.gz; \
    done

# -- Maven ------------------------------------------------------------------ #
ARG MAVEN_VERSION=3.9.9
RUN set -eux; \
    curl -fsSL -o /tmp/maven.tar.gz \
        "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz"; \
    mkdir -p /opt/maven; \
    tar -xzf /tmp/maven.tar.gz -C /opt/maven --strip-components=1; \
    rm /tmp/maven.tar.gz

# -- Gradle ----------------------------------------------------------------- #
ARG GRADLE_VERSION=8.10.2
RUN set -eux; \
    curl -fsSL -o /tmp/gradle.zip \
        "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip"; \
    unzip -q /tmp/gradle.zip -d /opt; \
    mv "/opt/gradle-${GRADLE_VERSION}" /opt/gradle; \
    rm /tmp/gradle.zip

ENV JAVA_HOME=/opt/java/jdk-17 \
    GRADLE_HOME=/opt/gradle \
    PATH="/opt/java/jdk-17/bin:/opt/maven/bin:/opt/gradle/bin:${PATH}"

# Quality gates use these executables at runtime.
ARG SONAR_SCANNER_VERSION=6.2.1.4610
RUN set -eux; \
    curl -fsSL -o /tmp/sonar-scanner.zip "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64.zip"; \
    unzip -q /tmp/sonar-scanner.zip -d /opt; \
    ln -s "/opt/sonar-scanner-${SONAR_SCANNER_VERSION}-linux-x64/bin/sonar-scanner" /usr/local/bin/sonar-scanner; \
    rm /tmp/sonar-scanner.zip; \
    curl -fsSL -o /tmp/install-fossa.sh https://raw.githubusercontent.com/fossas/fossa-cli/master/install-latest.sh; \
    BINDIR=/usr/local/bin bash /tmp/install-fossa.sh; \
    rm /tmp/install-fossa.sh

WORKDIR /app

# -- Python dependencies ---------------------------------------------------- #
COPY APEX-Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY APEX-Backend/requirements-render.txt ./requirements-render.txt
RUN pip install --no-cache-dir -r requirements-render.txt \
    && python -m playwright install --with-deps chromium

# -- Application ------------------------------------------------------------ #
COPY APEX-Backend/app ./app
COPY APEX-Backend/token_tracing ./token_tracing
COPY --from=frontend-build /frontend/dist ./frontend-dist

# Writable job workspace. Mount a persistent volume here if you want reports,
# the Gradle cache, and the vector store to survive container recreation.
RUN mkdir -p /app/storage/migration-jobs \
             /app/storage/support-tickets \
             /app/storage/vector-store \
             /app/storage/.gradle-cache

ENV GRADLE_USER_HOME=/app/storage/.gradle-cache \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# One worker keeps the in-process job state consistent. A second worker would
# not see the same local job state and could produce confusing behavior.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
