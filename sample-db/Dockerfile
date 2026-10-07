FROM postgres:18
# hypopg: hypothetical indexes for suggest_indexes. pgvector: pagila schema dependency (PGDG apt repo is preconfigured in this image)
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-18-hypopg postgresql-18-pgvector && rm -rf /var/lib/apt/lists/*
# Pagila (MIT, Devrim Gunduz) pinned to a commit; not stored in this repo.
ARG PAGILA=https://raw.githubusercontent.com/devrimgunduz/pagila/9baf49c4149e43229f6021e6218d6b2ac8ef4f34
ADD --chmod=644 ${PAGILA}/pagila-schema.sql /docker-entrypoint-initdb.d/1-schema.sql
ADD --chmod=644 ${PAGILA}/pagila-data.sql /docker-entrypoint-initdb.d/2-data.sql
COPY --chmod=755 init-roles.sh /docker-entrypoint-initdb.d/3-roles.sh
