ARG HERMES_IMAGE=nousresearch/hermes-agent:v2026.7.20
FROM ${HERMES_IMAGE}

LABEL org.opencontainers.image.title="ARM64 LLM inference lab"
LABEL org.opencontainers.image.description="Pinned Hermes harness for an OpenAI-compatible local inference endpoint"

# Keyless web search backend selected by config.yaml.
RUN VIRTUAL_ENV=/opt/hermes/.venv uv pip install --no-cache-dir ddgs==9.14.4

# Hermes 0.17-0.19 loads custom-provider extra_body during agent creation, then
# the gateway replaces request_overrides with an empty per-turn mapping. Merge
# the per-turn values so llama.cpp still receives chat_template_kwargs.
RUN target=/opt/hermes/gateway/run.py; \
    old='            agent.request_overrides = turn_route.get("request_overrides") or {}'; \
    new='            agent.request_overrides.update(turn_route.get("request_overrides") or {})'; \
    test "$(grep -Fxc "$old" "$target")" -eq 1; \
    sed -i "s|$old|$new|" "$target"; \
    grep -Fqx "$new" "$target"

# The iteration-limit summary bypasses the normal transport too. Preserve the
# same provider extra_body there so a failed tool loop cannot re-enable hidden
# thinking and occupy the CPU until the client timeout.
RUN target=/opt/hermes/agent/chat_completion_helpers.py; \
    old='        summary_extra_body = {}'; \
    new='        summary_extra_body = dict((agent.request_overrides or {}).get("extra_body") or {})'; \
    test "$(grep -Fxc "$old" "$target")" -eq 1; \
    sed -i "s|$old|$new|" "$target"; \
    grep -Fqx "$new" "$target"

# DDGS, Brave Free and SearXNG can search but cannot extract page contents.
# Hermes currently exposes web_extract whenever web_search is available, so
# give extraction its own capability check and keep unusable tools out of the
# model prompt.
RUN target=/opt/hermes/tools/web_tools.py; \
    old='    check_fn=check_web_api_key,'; \
    new='    check_fn=lambda: _get_extract_backend() in {"exa", "parallel", "firecrawl", "tavily"} and _is_backend_available(_get_extract_backend()),'; \
    test "$(sed -n '/name="web_extract",/,/requires_env=/p' "$target" | grep -Fxc "$old")" -eq 1; \
    sed -i "/name=\"web_extract\",/,/requires_env=/ s|$old|$new|" "$target"; \
    grep -Fqx "$new" "$target"; \
    python -m py_compile "$target"
