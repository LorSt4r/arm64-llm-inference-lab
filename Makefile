.PHONY: benchmark benchmark-reasoning check

check:
	bash scripts/check-public-safety.sh
	bash -n scripts/*.sh
	python3 -m py_compile scripts/*.py tests/*.py
	python3 -m unittest discover -s tests -v

benchmark:
	python3 scripts/benchmark_llm.py \
		--base-url "$${LLAMA_BASE_URL:-http://127.0.0.1:8080/v1}" \
		--disable-thinking \
		--output benchmark-results/latest.json

benchmark-reasoning:
	python3 scripts/benchmark_llm.py \
		--base-url "$${LLAMA_BASE_URL:-http://127.0.0.1:8080/v1}" \
		--max-tokens 512 \
		--output benchmark-results/latest-reasoning.json
