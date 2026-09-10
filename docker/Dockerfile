# syntax=docker/dockerfile:1
#
# Linux runtime for the CDI deep-research application. Python 3.12 matches the verified host
# `compute` interpreter (3.12.13) and satisfies the repository's Python 3.11+ requirement.
# Nothing from the Conda environment is copied; the Linux dependency closure is installed from
# PyPI under the pins in docker/constraints.txt.
FROM python:3.12-slim AS runtime

# PYTHONIOENCODING mirrors run.ps1 so non-Latin domain and source names survive console output.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    JUPYTER_PLATFORM_DIRS=1

WORKDIR /app

# Dependencies first so source edits do not invalidate the install layer. Constraints are applied
# to both installs, so the notebook UI can never upgrade a pinned application framework.
COPY requirements.txt ./
COPY docker/constraints.txt docker/requirements-notebook.txt ./docker/
RUN python -m pip install --no-cache-dir -r requirements.txt -c docker/constraints.txt \
 && python -m pip install --no-cache-dir -r docker/requirements-notebook.txt -c docker/constraints.txt \
 && python -m pip check

# Token counting needs this public tokenizer asset even when model/network calls are disabled.
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"

# Application source. inputs/, runs/, outputs/ and .env are excluded by .dockerignore: research
# data and secrets stay outside the image and arrive at runtime as mounts or environment values.
COPY ML/ ML/
COPY tests/ tests/
COPY CDI_Layer2_Layer3.ipynb AGENTS.md README.md ./

# Non-root runtime. The mount points are created with appuser ownership so Docker-managed volumes
# inherit it, and Jupyter has a writable home for its runtime and configuration directories.
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser \
 && mkdir -p /app/runs /app/outputs /app/inputs \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8888

# Starting the container serves the notebook. It never executes a cell or resumes a run: JupyterLab
# only renders the document until a human runs a cell. Publishing is restricted to loopback by the
# Compose port mapping; token authentication stays enabled.
CMD ["jupyter", "lab", \
     "--ServerApp.ip=0.0.0.0", \
     "--ServerApp.port=8888", \
     "--ServerApp.root_dir=/app", \
     "--ServerApp.open_browser=False", \
     "--no-browser"]

# VS Code mounts the original project; the browser notebook service remains untouched.
FROM runtime AS development
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory /app \
 && git config --system core.autocrlf true
USER appuser
COPY --chown=appuser:appuser docker/ docker/
COPY --chown=appuser:appuser .devcontainer/ .devcontainer/
COPY --chown=appuser:appuser compose.yaml ./
RUN python -m ipykernel install --user --name sedai-docker --display-name "SedAI Docker — Python 3.12"
CMD ["sleep", "infinity"]
