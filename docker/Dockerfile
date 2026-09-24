# AWS Batch worker: RDKit descriptor computation per array shard.
FROM condaforge/mambaforge:24.9.2-0

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# RDKit via conda-forge; Python deps via pip (no RDKit on PyPI).
COPY requirements.txt /app/requirements.txt
RUN mamba install -y -c conda-forge \
        python=3.11 \
        rdkit
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
