.PHONY: up down ingest eval test lint

up:      ## M6
	@echo "not implemented until M6 (kind)"; exit 1
down:    ## M6
	@echo "not implemented until M6 (kind)"; exit 1
ingest:  ## M1
	@echo "not implemented until M1"; exit 1
eval:    ## M2
	@echo "not implemented until M2"; exit 1

test:
	cd rag-api && uv run pytest
	cd mcp-server && npm test

lint:
	cd rag-api && uv run ruff check . && uv run ruff format --check .
	cd mcp-server && npm run lint
