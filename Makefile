# Cluster targets (up, down, ingest, eval) use the kind context only, never your current kube context.
# dev-* targets use docker compose + local uv/npm without Kubernetes.
CLUSTER := lexlens
K := kubectl --context kind-$(CLUSTER) -n lexlens
IMAGES := lexlens/rag-api:local lexlens/mcp-server:local lexlens/sample-db:local

.PHONY: up down ingest eval forward test lint dev-ingest dev-sample-db dev-eval dev-eval-answers

up:
	kind get clusters | grep -qx $(CLUSTER) || kind create cluster --config k8s/kind-config.yaml
	docker build -t lexlens/rag-api:local -f rag-api/Dockerfile .
	docker build -t lexlens/mcp-server:local mcp-server
	docker build -t lexlens/sample-db:local sample-db
	@echo 'loading images into the cluster: several minutes on a first run, one line per image, then silence'
	kind load docker-image --name $(CLUSTER) $(IMAGES)
	-$(K) get deployment rag-api >/dev/null 2>&1 && $(K) rollout restart deployment/rag-api deployment/mcp-server  # fixed :local tag: running pods keep the old image otherwise
	kubectl --context kind-$(CLUSTER) apply -f k8s/base/namespace.yaml
	k8s/make-secret.sh
	kubectl --context kind-$(CLUSTER) apply -k k8s/overlays/local
	$(K) rollout status statefulset/postgres --timeout=300s
	$(K) rollout status statefulset/sample-db --timeout=600s
	$(K) rollout status deployment/rag-api --timeout=600s
	$(K) rollout status deployment/mcp-server --timeout=300s
	@echo "Up. Next: make ingest (load the corpus), then make forward (rag-api :8000, MCP :3000)."

down:
	kind delete cluster --name $(CLUSTER)

ingest:
	k8s/run-job.sh ingest 1500

eval:
	LOG_FILE=/tmp/lexlens-eval.log k8s/run-job.sh eval 600
	python3 evals/compare.py /tmp/lexlens-eval.log

forward:
	@echo "rag-api http://localhost:8000   MCP http://localhost:3000/mcp   (Ctrl-C to stop)"
	@trap 'kill 0' INT TERM; \
	$(K) port-forward svc/rag-api 8000:8000 & \
	$(K) port-forward svc/mcp-server 3000:3000 & \
	wait

test:
	set -a; . ./.env 2>/dev/null; set +a; cd rag-api && uv run pytest
	set -a; . ./.env 2>/dev/null; set +a; cd mcp-server && npm test

lint:
	cd rag-api && uv run ruff check . && uv run ruff format --check .
	cd mcp-server && npm run lint
	kubectl kustomize k8s/overlays/local > /dev/null

dev-ingest:
	docker compose up -d --wait postgres
	set -a; . ./.env; set +a; cd rag-api && uv run python -m app.ingest

dev-sample-db:
	docker compose up -d --build --wait sample-db

dev-eval:
	set -a; . ./.env; set +a; cd rag-api && uv run python ../evals/run_eval.py

dev-eval-answers:
	set -a; . ./.env; set +a; cd rag-api && uv run python ../evals/run_answer_eval.py $(ARGS)
