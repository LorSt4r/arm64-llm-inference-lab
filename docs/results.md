# Recorded results

## Evidence boundary

These measurements were recorded on 30 July 2026 on an Oracle Cloud Ampere A1
instance configured with **4 OCPU and 24 GiB RAM**. Linux reported roughly
23 GiB usable. The instance configuration later changed; the table below is a
historical experiment, not a statement about the current VM.

The engine was an `ik_llama.cpp` revision serving a
Qwen3.6-35B-A3B `IQ4_XS` GGUF with one slot, four threads, a 65,536-token
context, flash attention, and Q4 key/value cache.

## Reproducible request measurements

Each uncached request used a fresh nonce. The cached measurement repeated the
identical payload.

| Prompt tokens | Uncached prefill | Exact repeat |
|---:|---:|---:|
| 804 | 37.50 tok/s, 21.68 s | 0.49 s |
| 3,026 | 36.22 tok/s, 83.87 s | 0.65 s |
| 5,993 | 34.23 tok/s, 175.45 s | 0.71 s |

A forced 256-token generation measured 7.27 tokens/s and approximately 38
seconds end to end. Longer application logs placed sustained decode mostly
between 6.2 and 7.7 tokens/s; a previous 50-token micro-test reporting 9.90
tokens/s was rejected as unrepresentative.

## Controlled configuration comparison

| Variant | Prefill 0.8k / 3k / 6k | Decode | Process swap | Observed major faults |
|---|---:|---:|---:|---:|
| A0 original | 38.43 / 36.03 / 34.63 | 7.38 | 571 MiB | 613 |
| A1 cache cap 1536 MiB | 38.52 / 37.23 / 34.58 | 7.35 | 0 | 0 |
| A2 16 checkpoints | 38.63 / 37.05 / 34.06 | 7.39 | 0 | 0 |
| A3 effective `mlock` | 38.67 / 36.97 / 34.69 | 7.27 | 0 | 0 |
| A4 runtime repack disabled | 34.62 / 34.60 / 31.74 | 5.92 | 0 | 0 |

Runtime repacking added about 24 seconds to the observed cold start but
improved decode by approximately 22.9% relative to A4. A3 locked 17,357,472
KiB and kept the model process out of swap during the measurement.

## Interpretation and limitations

- Four cores were already saturated; memory pressure and paging were more
  actionable than adding another wrapper around the same backend.
- Exact prompt replay is useful but is not representative of a conversation
  whose history changes every turn.
- A global cache-hit percentage cannot replace per-request latency and cache
  invalidation evidence.
- A1 and A2 began from clean restarts, so eliminating observed faults could not
  be attributed to a single setting without a longer soak test.
- Throughput alone was insufficient: strict JSON and response-quality checks
  were evaluated separately.
- Results should not be extrapolated to other models, quantizations, engine
  commits, ARM CPUs, or current Oracle Free Tier allocations.
