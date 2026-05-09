# esp32-developer

A Claude Code skill for scaffolding production-shaped **ESP32** firmware projects.

Default stack:

- **ESP-IDF** framework (Arduino is opt-in only)
- **PlatformIO** project system
- **HAL split** — application code talks to `hal_*.h`, never to `driver/*.h`
- **FreeRTOS** with explicit core affinity (`xTaskCreatePinnedToCore`)
- **OTA-ready partitions** from day one (factory + 2× OTA + nvs + nvs_keys + otadata + storage)
- Dev-baseline `sdkconfig.defaults`; production hardening (Secure Boot v2, Flash Encryption release, signed OTA, anti-rollback, NVS encryption) is **opt-in only**

Supports `esp32`, `esp32s2`, `esp32s3`, `esp32c3`, `esp32c6`, `esp32h2`.

## Layout

```text
esp32-developer/
├── SKILL.md           # frontmatter + procedural body (loaded by Claude Code)
├── references/        # topic-gated deep references
├── scripts/           # verify_project.py — JSON-in/JSON-out validator
├── assets/            # platformio.ini, partitions.csv, sdkconfig defaults, HAL/main templates
└── LICENSE            # MIT
```

`SKILL.md` lists which references load on which triggers (variant, peripheral, security, etc.) — see `## 3 · Reference Loading`.

## Using the skill

This skill is automatically triggered whenever Claude Code detects an ESP32 project is being created, scaffolded, or bootstrapped — including bring-up demos like blink, button read, or single-sensor wiring. See `## 1 · When to Use` in [SKILL.md](SKILL.md) for the full trigger list.

To install, drop the directory under your Claude Code skills path (e.g. `~/.claude/skills/esp32-developer/`) or wherever your skill loader looks.

## Validating a generated project

```bash
echo '{...project descriptor...}' | python scripts/verify_project.py
```

Exit codes: `0` ok, non-zero on validation failure. Full input/output schema is documented in [SKILL.md](SKILL.md) `## 9 · Script Interface`.

## License

MIT — see [LICENSE](LICENSE).
