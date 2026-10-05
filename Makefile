.PHONY: up down ingest eval test lint

up:      ## M6
	@echo "not implemented until M6 (kind)"; exit 1
down:    ## M6
	@echo "not implemented until M6 (kind)"; exit 1
ingest:
	docker compose up -d --wait postgres
	set -a; . ./.env; set +a; cd rag-api && uv run python -m app.ingest
eval:
	set -a; . ./.env; set +a; cd rag-api && uv run python ../evals/run_eval.py

test:
	set -a; . ./.env 2>/dev/null; set +a; cd rag-api && uv run pytest
	cd mcp-server && npm test

lint:
	cd rag-api && uv run ruff check . && uv run ruff format --check .
	cd mcp-server && npm run lint
