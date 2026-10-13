PYTHON ?= python3
.PHONY: check test demo upstream-check docs-check proto docker clean pg-live
check:
	$(PYTHON) tools/generate_contracts.py --check
	$(PYTHON) tools/validate.py
test:
	$(PYTHON) -m unittest discover -s tests -v
demo:
	$(PYTHON) tools/demo_es.py
upstream-check:
	$(PYTHON) tools/check_logs.py
docs-check:
	$(PYTHON) tools/check_docs.py
proto:
	mkdir -p build/proto
	$(PYTHON) -m grpc_tools.protoc -I proto --python_out=build/proto proto/domain_event.proto proto/line.proto
pg-live:
	@test -n "$(DATA_PLANE_PG_DSN)" || (echo "set DATA_PLANE_PG_DSN to a disposable PostgreSQL 16 server" && exit 2)
	DATA_PLANE_PG_DSN="$(DATA_PLANE_PG_DSN)" $(PYTHON) -m unittest -v tests.test_postgres_live
docker:
	docker compose run --rm conformance
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
