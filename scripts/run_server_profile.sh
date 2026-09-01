#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-$PWD/benchmark-results/live}"
benchmark_script="${2:-$PWD/scripts/benchmark_inference.py}"
service_name="${LLAMA_SERVICE_NAME:-llama-server}"
server_pid="$(systemctl show -p MainPID --value "$service_name")"

if [[ ! "$server_pid" =~ ^[1-9][0-9]*$ ]]; then
  echo "llama-server PID not found" >&2
  exit 1
fi

llama_api_key="$(sudo sed -n 's/^LLAMA_API_KEY=//p' /etc/llama-server.env)"
if [[ -z "$llama_api_key" ]]; then
  echo "llama-server API key not found" >&2
  exit 1
fi

install -d -m 700 "$output_dir"
export LLAMA_API_KEY="$llama_api_key"

sudo --preserve-env=LLAMA_API_KEY perf stat \
  -p "$server_pid" \
  -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,context-switches,cpu-migrations,page-faults,minor-faults,major-faults \
  -o "$output_dir/perf-stat.txt" \
  -- python3 "$benchmark_script" \
    --base-url http://127.0.0.1:8080/v1 \
    --server-pid "$server_pid" \
    --output "$output_dir/inference-benchmark.json"

unset LLAMA_API_KEY
sudo chown -R "$(id -u):$(id -g)" "$output_dir"
chmod 700 "$output_dir"
chmod 600 "$output_dir"/*
