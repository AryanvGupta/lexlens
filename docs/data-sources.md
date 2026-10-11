# Data sources

| id | source | edition | terms |
|---|---|---|---|
| usc-11, usc-17, usc-28, usc-35 | U.S. Code, Titles 11, 17, 28 and 35, via govinfo.gov (GPO) | 2023 edition, laws through 2024-01-03 | U.S. Government work; public domain. See https://www.govinfo.gov/about/policies |

Pinned in `data/sources.json`. Raw HTML is downloaded to `data/raw/` (git-ignored) by `make dev-ingest` / `make ingest`.
Titles 15 (21 MB, ~3,000 sections), 18 (8 MB, ~1,400 sections) and 42 (77 MB, ~8,000 sections) were considered and dropped as too large for a small reproducible corpus.
CourtListener was not used: unauthenticated requests returned HTTP 403.

## Scaling experiment corpus (not part of the shipped corpus)

`evals/scale/sources-3x.json` and `evals/scale/sources-extra.json` list the four baseline Titles plus extra Titles from the same source and edition (govinfo.gov, U.S. Code 2023 edition, `https://www.govinfo.gov/content/pkg/USCODE-2023-title<N>/html/USCODE-2023-title<N>.htm`). They are used only by `evals/scale_experiment.py` and downloaded to a directory outside the repository (`evals/scale/download.sh`; `LEXLENS_SOURCES` and `LEXLENS_RAW` override the manifest and the download directory for `app.ingest`).

| Title | name | HTML size | passages (300/40) | in |
|---|---|---|---|---|
| 8 | Aliens and Nationality | 5.0 MB | 1,143 | 3x, 10x |
| 18 | Crimes and Criminal Procedure | 8.8 MB | 2,407 | 3x, 10x |
| 29 | Labor | 7.9 MB | 2,453 | 3x, 10x |
| 31 | Money and Finance | 5.4 MB | 1,158 | 10x |
| 21 | Food and Drugs | 8.3 MB | 2,645 | 10x |
| 38 | Veterans' Benefits | 12.3 MB | 2,620 | 10x |
| 20 | Education | 15.5 MB | 4,067 | 10x |
| 15 | Commerce and Trade | 21.5 MB | 6,951 | 10x |
| 47 | Telecommunications | 4.1 MB | 1,269 | 10x |

Totals: 3x is 8,855 passages and 10x is 27,565 (the baseline is 2,852). Basis for use: like the baseline Titles, the text of the U.S. Code published by the GPO is a U.S. Government work and public domain (<https://www.govinfo.gov/about/policies>); no separate per-Title licence page was read.

## SQL sample database

| id | source | terms |
|---|---|---|
| pagila | [Pagila](https://github.com/devrimgunduz/pagila) sample database by Devrim Gunduz, pinned to commit `9baf49c4149e43229f6021e6218d6b2ac8ef4f34` | MIT-style licence (see `LICENSE.txt` in that repository). GitHub's licence detector reports it as unrecognised, so the text was read directly. |

Downloaded at image build time by `sample-db/Dockerfile` (`make dev-sample-db` or `make up`); not stored in this repository.
