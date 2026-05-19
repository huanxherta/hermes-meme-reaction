# hermes-meme-reaction

Pure Hermes Agent plugin: LLM-judged automatic meme/sticker reactions after each gateway turn.

- **pre_gateway_dispatch**: caches current session route
- **post_llm_call**: asks host LLM whether the assistant's reply should get a meme tail
- **Cross-platform send**: uses `ctx.dispatch_tool("send_message", ...)` with `MEDIA:<path>`
- **Import tool**: `meme_import(path=...)` builds a searchable index from your meme folders
- **Search tool**: `meme_search(tags=[...], query=...)` finds indexed memes

## Install

```bash
# Copy to Hermes plugins directory
cp -r meme_reaction ~/.hermes/plugins/meme-reaction
cp plugin.yaml ~/.hermes/plugins/meme-reaction/

# Enable in config.yaml
hermes config edit
```

```yaml
plugins:
  enabled:
    - meme-reaction

meme_reaction:
  enabled: true
  trigger_weight: 0.9
  threshold: 0.55
  cooldown_seconds: 90
  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true
```

## License

MIT
