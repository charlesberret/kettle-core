# Model catalog refresh

Kettle's sitting model picker reads from `CATALOG_MODELS` in `kettle/curator.py`.
That list is hand-maintained. Provider CLIs rename and retire model ids often;
defaults live beside it in `DEFAULT_MODELS`, `DEFAULT_MODELS_GROK`,
`DEFAULT_MODELS_CHATGPT`, and `DEFAULT_MODELS_GEMINI`. **Custom CLI** has no fixed
catalog — users supply ids via `curator.menu.cli`.

## Who updates it

Anyone landing a curator change that bumps a built-in default or adds/removes a
first-class model id should refresh the catalog in the same change. Reviewers
should treat a missing or stale id as a release blocker for provider-facing work.

## What to check (public sources only)

Confirm the id still appears on the vendor's current model list and matches what
the installed CLI accepts (`--model` / equivalent). Use the provider's public
documentation — not private release notes or internal dashboards.

| Provider | Kettle key | Default task ids | Check here |
| -------- | ---------- | ---------------- | ---------- |
| Claude Code | `claude` | `setup` / `chat` → `sonnet` (see `DEFAULT_MODELS`) | [Claude models overview](https://docs.anthropic.com/en/docs/about-claude/models) |
| Grok Build CLI | `grok` | `grok-4.5` | [xAI docs](https://docs.x.ai/docs/models) |
| ChatGPT / Codex CLI | `chatgpt` | `gpt-5.1` | [OpenAI model docs](https://platform.openai.com/docs/models) |
| Gemini CLI | `gemini` | `gemini-2.5-pro` | [Gemini models](https://ai.google.dev/gemini-api/docs/models) |

When adding a catalog row:

1. Append an entry to `CATALOG_MODELS` with `id`, `provider`, `label`, `blurb`,
   `good_for`, and `effort_supported` consistent with neighbouring rows.
2. If the row affects desk ordering, add or adjust `MODEL_CALIBRE` for that `id`
   (lower rank = lighter / listed earlier within the provider).
3. If the **default** for a built-in provider changed, update the matching
   `DEFAULT_MODELS_*` dict and any seeded `DEFAULT_MENU` entries in the same file.
4. Run the regression test below.

Custom CLI (`cli`) does not use `CATALOG_MODELS`; skip it unless you are
documenting user-facing menu behaviour.

## Regression test

`tests/test_curator.py` asserts that:

- every catalog `id` is unique; and
- each built-in provider's default model ids (`claude`, `grok`, `chatgpt`, `gemini`)
  appear in `CATALOG_MODELS` under the correct `provider`.

After editing the catalog or defaults, run:

```sh
pytest tests/test_curator.py -q
```

Commit only when that command passes. Quote the command and its summary in the
pull request so reviewers can replay the check.
