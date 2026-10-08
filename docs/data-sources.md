# Data sources

| id | source | edition | terms |
|---|---|---|---|
| usc-11, usc-17, usc-28, usc-35 | U.S. Code, Titles 11, 17, 28 and 35, via govinfo.gov (GPO) | 2023 edition, laws through 2024-01-03 | U.S. Government work; public domain. See https://www.govinfo.gov/about/policies |

Pinned in `data/sources.json`. Raw HTML is downloaded to `data/raw/` (git-ignored) by `make dev-ingest` / `make ingest`.
Titles 15 (21 MB, ~3,000 sections), 18 (8 MB, ~1,400 sections) and 42 (77 MB, ~8,000 sections) were considered and dropped as too large for a small reproducible corpus.
CourtListener was not used: unauthenticated requests returned HTTP 403.

## SQL sample database

| id | source | terms |
|---|---|---|
| pagila | [Pagila](https://github.com/devrimgunduz/pagila) sample database by Devrim Gunduz, pinned to commit `9baf49c4149e43229f6021e6218d6b2ac8ef4f34` | MIT-style licence (see `LICENSE.txt` in that repository). GitHub's licence detector reports it as unrecognised, so the text was read directly. |

Downloaded at image build time by `sample-db/Dockerfile` (`make dev-sample-db` or `make up`); not stored in this repository.
