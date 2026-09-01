# ARM64 LLM Inference Lab

[![CI](https://github.com/LorSt4r/arm64-llm-inference-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/LorSt4r/arm64-llm-inference-lab/actions/workflows/ci.yml)

A reproducible systems-engineering case study for CPU-only LLM inference on an
Oracle Cloud Ampere A1 instance. It includes an OpenAI-compatible benchmark
harness, Linux memory and process sampling, hardened `systemd` templates, and
the evidence behind a controlled configuration comparison.

## Historical hardware scope

**All published measurements in this repository were collected on 30 July
2026, when the Oracle Always Free instance had 4 OCPU and 24 GiB of RAM**
(approximately 23 GiB visible to Linux). They do not describe the capacity or
state of the instance today. Reproducing the numbers requires comparable ARM64
hardware, the same model and engine revision, and the recorded parameters.

## What was measured

- Oracle Ampere A1, four Neoverse-N1 cores and 24 GiB provisioned RAM.
- Qwen3.6-35B-A3B `IQ4_XS`, served by an `ik_llama.cpp` revision.
- New-nonce prefill, exact prompt-cache replay, sustained decode, RSS, locked
  memory, swap, page faults, I/O, and selected `perf stat` counters.
- One-variable configuration changes for cache size, checkpoint count,
  effective `mlock`, and runtime repacking.
- A small correctness gate for grounded answers, strict JSON output, and
  untrusted-note handling.

The best measured long-run baseline reached 34.2–37.5 tokens/s for uncached
prefill and 7.27 tokens/s sustained decode. Runtime repacking improved decode
by approximately 22.9% relative to the measured no-repack variant, at the cost
of a longer cold start. These are dated measurements, not general performance
claims. See [results and limitations](docs/results.md).

## Repository layout

```text
scripts/                 API benchmark and Linux process sampler
tests/                   Dependency-free unit tests for result validation
infra/systemd/           Hardened service and environment templates
docs/results.md          Recorded A/B results and interpretation
docs/methodology.md      Reproduction requirements and measurement design
```

## Run the benchmark

The scripts use only the Python standard library. Start an OpenAI-compatible
`llama-server`, keep its API bound to a trusted interface, and export the key
outside the repository.

```bash
export LLAMA_API_KEY='replace-with-a-local-test-key'
python3 scripts/benchmark_inference.py \
  --base-url http://127.0.0.1:8080/v1 \
  --model local-model \
  --server-pid "$(pidof llama-server)" \
  --output benchmark-results/latest.json
```

Run the correctness-oriented cases separately:

```bash
python3 scripts/benchmark_llm.py \
  --base-url http://127.0.0.1:8080/v1 \
  --disable-thinking \
  --output benchmark-results/quality.json
```

## Verify the repository

```bash
make check
```

This compiles the Python scripts, runs unit tests, validates shell syntax, and
checks tracked files for private keys and common live-secret formats.

## Engineering decisions

- A nonce prevents an uncached prefill measurement from silently becoming a
  cache-hit measurement.
- Each exact-repeat request uses an identical payload to isolate prompt-cache
  reuse.
- Process and system counters are sampled while the API call is running.
- Model output quality is gated independently from throughput.
- The model API and agent-facing services remain loopback-only.
- Measurements are reported with model, quantization, engine, hardware, and
  date instead of being presented as portable benchmarks.

## AI assistance

AI agents assisted with investigation and implementation. I defined the test
matrix, validated commands and runtime state, reviewed the generated changes,
and accepted conclusions only when the recorded measurements supported them.

## License

MIT. See [LICENSE](LICENSE).
