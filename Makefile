PYTHON ?= python3
.PHONY: check test demo upstream-check proto docker clean
check:
	$(PYTHON) tools/generate_contracts.py --check
	$(PYTHON) tools/validate.py
test:
	$(PYTHON) -m unittest discover -s tests -v
demo:
	$(PYTHON) tools/demo_es.py
upstream-check:
	$(PYTHON) tools/check_logs.py
proto:
	mkdir -p build/proto
	$(PYTHON) -m grpc_tools.protoc -I proto --python_out=build/proto proto/domain_event.proto
docker:
	docker compose run --rm conformance
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
