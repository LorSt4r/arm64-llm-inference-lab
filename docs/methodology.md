# Benchmark methodology

## Required metadata

Record the following with every result:

- UTC timestamp and host CPU/RAM;
- engine repository and exact commit;
- model name, quantization, file hash, and context size;
- thread, batch, KV-cache, prompt-cache, and repack parameters;
- cold or warm state and the number of repetitions;
- response correctness alongside performance.

## Prefill and cache isolation

The benchmark generates a new nonce for every prefill size. The first call is
therefore not eligible for exact-prompt reuse. A second call repeats the same
payload to measure exact replay separately.

## Decode

Decode uses deterministic sampling and requests a long response with EOS
ignored. Short generations can overstate stable throughput, so the recorded
comparison uses 256 requested tokens.

## Linux sampling

When `--server-pid` is supplied, the sampler reads `/proc` every 500 ms and
records RSS, anonymous/file-backed pages, swap, locked memory, available host
memory, faults, process reads, and system swap activity.

`scripts/run_server_profile.sh` can additionally attach `perf stat` to the
running process. This normally requires explicit local privilege; the script
does not embed or print the API key.

## Quality gate

`benchmark_llm.py` checks three small tasks: grounded retrieval, schema-bound
JSON extraction, and handling an untrusted instruction embedded in a note.
These cases do not establish general model quality; they prevent an obviously
incorrect configuration from being promoted solely because it is faster.
