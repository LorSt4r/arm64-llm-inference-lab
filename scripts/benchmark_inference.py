#!/usr/bin/env python3
"""Measure prefill, prompt-cache reuse, and decode on an OpenAI-compatible API."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="local-model")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--prefill-words",
        type=int,
        nargs="+",
        default=[256, 1024, 2048],
    )
    parser.add_argument("--decode-tokens", type=int, default=256)
    parser.add_argument("--server-pid", type=int)
    return parser.parse_args()


def call_api(base_url: str, api_key: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=900) as response:
        body = json.load(response)
    elapsed = time.monotonic() - started
    choice = body["choices"][0]
    message = choice["message"]
    return {
        "elapsed_seconds": round(elapsed, 3),
        "finish_reason": choice.get("finish_reason"),
        "content_characters": len(message.get("content", "")),
        "reasoning_characters": len(message.get("reasoning_content", "")),
        "usage": body.get("usage", {}),
        "timings": body.get("timings", {}),
    }


def prefill_payload(model: str, word_count: int) -> dict:
    nonce = uuid.uuid4().hex
    corpus = " ".join(f"dato{i % 97}" for i in range(word_count))
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 4,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {
                "role": "system",
                "content": f"Benchmark {nonce}. Non ragionare. Rispondi solo OK.",
            },
            {"role": "user", "content": f"Leggi questi dati:\n{corpus}\nFine."},
        ],
    }


def decode_payload(model: str, token_count: int) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": token_count,
        "ignore_eos": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Benchmark {uuid.uuid4().hex}. Non ragionare. "
                    "Produci una sequenza numerata continua."
                ),
            },
            {
                "role": "user",
                "content": "Elenca numeri e una breve parola, senza fermarti.",
            },
        ],
    }


def read_key_values(path: Path) -> dict[str, int]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        first = raw_value.strip().split()
        if first and first[0].isdigit():
            values[key] = int(first[0])
    return values


def read_process_faults(path: Path) -> dict[str, int]:
    fields = path.read_text(encoding="utf-8").rsplit(")", 1)[1].split()
    return {
        "minor_faults": int(fields[7]),
        "major_faults": int(fields[9]),
    }


def sample_memory(
    server_pid: int, stop_event: threading.Event, samples: list[dict]
) -> None:
    status_path = Path(f"/proc/{server_pid}/status")
    stat_path = Path(f"/proc/{server_pid}/stat")
    io_path = Path(f"/proc/{server_pid}/io")
    meminfo_path = Path("/proc/meminfo")
    vmstat_path = Path("/proc/vmstat")
    while not stop_event.wait(0.5):
        try:
            status = read_key_values(status_path)
            faults = read_process_faults(stat_path)
            process_io = read_key_values(io_path)
            meminfo = read_key_values(meminfo_path)
            vmstat = read_key_values(vmstat_path)
        except FileNotFoundError:
            return
        samples.append(
            {
                "monotonic_seconds": round(time.monotonic(), 3),
                "rss_kb": status.get("VmRSS"),
                "rss_anon_kb": status.get("RssAnon"),
                "rss_file_kb": status.get("RssFile"),
                "swap_kb": status.get("VmSwap"),
                "locked_kb": status.get("VmLck"),
                "available_kb": meminfo.get("MemAvailable"),
                "process_minor_faults": faults["minor_faults"],
                "process_major_faults": faults["major_faults"],
                "process_read_bytes": process_io.get("read_bytes"),
                "system_pswpin": vmstat.get("pswpin"),
                "system_pswpout": vmstat.get("pswpout"),
            }
        )


def summarize_samples(samples: list[dict]) -> dict:
    summary = {"sample_count": len(samples)}
    for key in (
        "rss_kb",
        "rss_anon_kb",
        "rss_file_kb",
        "swap_kb",
        "locked_kb",
        "available_kb",
    ):
        values = [sample[key] for sample in samples if sample.get(key) is not None]
        if values:
            summary[f"{key}_min"] = min(values)
            summary[f"{key}_max"] = max(values)
    for key in (
        "process_minor_faults",
        "process_major_faults",
        "process_read_bytes",
        "system_pswpin",
        "system_pswpout",
    ):
        values = [sample[key] for sample in samples if sample.get(key) is not None]
        if values:
            summary[f"{key}_delta"] = values[-1] - values[0]
    return summary


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("LLAMA_API_KEY")
    if not api_key:
        raise SystemExit("Set LLAMA_API_KEY outside the repository")

    memory_samples: list[dict] = []
    stop_event = threading.Event()
    sampler = None
    if args.server_pid:
        sampler = threading.Thread(
            target=sample_memory,
            args=(args.server_pid, stop_event, memory_samples),
            daemon=True,
        )
        sampler.start()

    try:
        prefill_results = []
        for word_count in args.prefill_words:
            payload = prefill_payload(args.model, word_count)
            first = call_api(args.base_url, api_key, payload)
            second = call_api(args.base_url, api_key, payload)
            prefill_results.append(
                {
                    "requested_words": word_count,
                    "uncached": first,
                    "cached_repeat": second,
                }
            )

        decode = call_api(
            args.base_url,
            api_key,
            decode_payload(args.model, args.decode_tokens),
        )
    finally:
        stop_event.set()
        if sampler:
            sampler.join(timeout=2)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "prefill": prefill_results,
        "decode": decode,
        "memory": summarize_samples(memory_samples),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
