# Hermes Meme Reaction Plugin Refactor Design

## Scope

Refactor only this plugin repository: `/home/huanx/code/hermes-meme-reaction`.

Do not modify Hermes core code, Hermes bundled plugins, or Hermes user config:

- Do not write to `~/.hermes/hermes-agent/**`.
- Do not run `hermes plugins enable`, `hermes plugins disable`, or equivalent config-changing commands.
- Do not edit `~/.hermes/config.yaml`.
- Runtime state under `~/.hermes/meme_reaction/**` remains plugin-owned state, not Hermes core.

## Goals

Make the plugin safer and easier to use:

- Prevent accidental sends to the wrong chat.
- Keep configuration simple and permissive by default once the user opts in.
- Preserve the current pure-plugin model: `register(ctx)`, Hermes hooks, `ctx.llm`, and `ctx.dispatch_tool("send_message")`.
- Split the large plugin module into small, testable units.
- Keep local tests isolated from real `~/.hermes` state.

## Configuration Semantics

The plugin has one explicit activation gate:

- `meme_reaction.enabled: false` by default.
- If `enabled` is false, hooks and tools do no meaningful runtime work beyond registration.
- This avoids automatic sending just because the plugin is installed or discovered.

Restriction fields use the usability-first rule:

- Empty `allowed` lists mean unrestricted.
- Empty `denied` lists mean nothing is denied.
- Empty target lists mean all targets are allowed.
- Empty import-root lists mean all local import paths are allowed.

Examples:

- `platforms.allowed: []` means all platforms are allowed.
- `targets.allowed: []` means all chat targets are allowed.
- `import.allowed_roots: []` means `meme_import(path=...)` may scan any readable local path.

This rule does not weaken route correctness. Sending still requires a precise route for the current LLM response.

## Safety Behavior

The current fallback to "most recent route on the same platform" will be removed.

New route behavior:

- `pre_gateway_dispatch` stores route data by deterministic route key and by Hermes session id when available.
- `post_llm_call` sends only when it can find an exact session route.
- If no exact route exists, the plugin skips sending and logs the reason.

Target filtering remains optional:

- If target allowlists are empty, all targets are allowed.
- If target allowlists are configured, only matching targets can receive memes.
- Deny lists override allow lists.

Debug logging:

- File debug logging is disabled by default.
- If enabled, write under plugin state, for example `~/.hermes/meme_reaction/debug.log`.
- Normal diagnostics use `logger.debug`.

Dry run:

- Add `dry_run: false` by default.
- When true, the plugin runs route lookup, LLM decision, and meme selection, then records what would have been sent without calling `send_message`.

## Architecture

Keep the root `__init__.py` as a thin Hermes entrypoint.

Proposed modules:

- `plugin.py`: `register(ctx)` only, wires hooks and tools.
- `runtime.py`: orchestration for `pre_gateway_dispatch` and `post_llm_call`.
- `routes.py`: route key creation, route persistence, exact route lookup.
- `state.py`: JSON state files, history append, cooldown storage.
- `decision.py`: prompt input building and `ctx.llm.complete_structured` parsing.
- `sender.py`: target formatting, optional dry-run, `send_message` dispatch.
- `tools.py`: `meme_import` and `meme_search` handlers.
- `config.py`: dataclasses and parsing, including empty-means-unrestricted rules.

Existing focused modules stay in place:

- `index.py`: meme index persistence.
- `importer.py`: local meme library scanning.
- `selector.py`: meme scoring and selection.
- `prompts.py`: LLM instructions and schema.

## Data Flow

Incoming user message:

1. `pre_gateway_dispatch` reads event source and session store.
2. If plugin config is enabled and platform is allowed, store exact route data.
3. Route data is persisted under plugin state.

LLM response:

1. `post_llm_call` loads config.
2. If disabled, skip.
3. Resolve exact session route.
4. Apply optional platform and target restrictions.
5. Check cooldown.
6. Load meme index.
7. Ask `ctx.llm` for a structured decision.
8. Select a matching meme.
9. If `dry_run`, record a dry-run history entry.
10. Otherwise call `ctx.dispatch_tool("send_message", ...)`.
11. On success, update cooldown and history.

Manual tools:

- `meme_import` scans local files and writes the configured index.
- `meme_search` reads the index and returns matching metadata.

## Error Handling

Runtime hooks should be fail-closed:

- Missing config means disabled defaults.
- Missing exact route means skip.
- Empty index means skip.
- LLM failures mean skip.
- Send failures are logged but do not raise into Hermes.

Tool handlers should return structured JSON:

- `success: true` with counts and paths on success.
- `success: false` with a clear `error` string on user-facing failures.

## Tests

Add or update tests for:

- Root plugin entrypoint imports in a standalone checkout.
- Config parsing, especially empty-means-unrestricted behavior.
- Exact route lookup succeeds.
- Missing exact route does not send.
- Dry-run does not call `send_message`.
- Debug file logging is disabled by default.
- `meme_import` works with unrestricted empty import roots.
- Tests use temporary state paths and do not write real `~/.hermes`.

## Migration

Keep backwards-compatible config names where practical:

- Continue supporting `allowed_platforms` and `denied_platforms`.
- Also support README-style `platforms.allowed` and `platforms.denied`.
- Existing index format remains unchanged.

No Hermes core migration is required.
