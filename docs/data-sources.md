# Data sources

| id | source | edition | terms |
|---|---|---|---|
| usc-17, usc-35 | U.S. Code, Titles 17 and 35, via govinfo.gov (GPO) | 2023 edition, laws through 2024-01-03 | U.S. Government work; public domain. See https://www.govinfo.gov/about/policies |

Pinned in `data/sources.json`. Raw HTML is downloaded to `data/raw/` (git-ignored) by `make ingest`.
Title 15 was considered and dropped: 21 MB / ~3,000 sections, too large for a small reproducible corpus.
CourtListener was not used: unauthenticated requests returned HTTP 403.
