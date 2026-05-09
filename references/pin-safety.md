# Pin Safety (ESP32 family)

Per-variant rules for assigning GPIO on the ESP32 family. The hard constraints below come from the ESP32 / ESP32-S2 / S3 / C3 / C6 / H2 datasheets and Technical Reference Manuals — they are not negotiable and have nothing to do with framework choice.

> This file is the **production checklist**. For the deeper authority — full GPIO pin table with capabilities and ADC channels, see [esp32-pins.md](esp32-pins.md). For the strapping-pin / ADC2-WiFi / flash-voltage deep dive, see [esp32-specifics.md](esp32-specifics.md). For voltage levels, current budgets, and pull-up sizing formulas, see [electrical-constraints.md](electrical-constraints.md). For protocol-bus specs and address conflicts, see [protocol-quick-ref.md](protocol-quick-ref.md). For per-part wiring (sensors, displays, radios), see [common-devices.md](common-devices.md).

## Reserved pins (NEVER assign)

### Flash SPI

| Variant | Reserved GPIO |
|---|---|
| esp32 (WROOM) | 6, 7, 8, 9, 10, 11 |
| esp32 (WROVER) | 6, 7, 8, 9, 10, 11, 16, 17 (PSRAM) |
| esp32-s2 | non-GPIO flash interface |
| esp32-s3 | non-GPIO flash interface (GPIO6–11 free; PSRAM uses dedicated pins) |
| esp32-c3 / c6 / h2 | non-GPIO flash interface |

If the user asks to use GPIO6–11 on `esp32`, refuse and propose alternatives — there is no recoverable way to use them while the chip is running from flash.

## Strapping pins (warn on every use)

| Variant | Strapping GPIOs |
|---|---|
| esp32      | 0, 2, 5, 12, 15 |
| esp32-s2   | 0, 45, 46 |
| esp32-s3   | 0, 3, 45, 46 |
| esp32-c3   | 2, 8, 9 |
| esp32-c6   | 4, 5, 8, 9, 15 |

If the project must use a strapping pin, the assignment requires:

1. A `// STRAPPING:` comment naming the required boot level (`high` / `low` / `floating`).
2. External pull-up/pull-down sized so the boot level is guaranteed before the SoC samples it.
3. **GPIO12 on `esp32` (MTDI)** is special: high at boot switches the flash voltage to 1.8 V and **bricks 3.3 V flash modules**. Either don't use it, or burn the appropriate efuse (`espefuse.py set_flash_voltage 3.3V`) at manufacturing.

## Input-only (esp32 only)

GPIO 34, 35, 36, 37, 38, 39 — input-only, no internal pulls, no output mode. Assign for ADC inputs, button inputs, etc. Refuse to use as outputs or open-drain.

## ADC2 / WiFi conflict (esp32 only)

When WiFi is enabled, ADC2 is unusable. ADC2 pins on `esp32`: GPIO 0, 2, 4, 12, 13, 14, 15, 25, 26, 27.

**S2/S3/C3/C6/H2 do not have this conflict** — ADC2 is independent of WiFi.

If the project enables WiFi on `esp32`, every analog input must be mapped to ADC1 (GPIO 32–39) or refuse the assignment.

## RTC GPIOs (deep-sleep wake)

Only RTC-domain GPIOs can wake the chip from deep sleep via `ESP_EXT0_WAKEUP` / `ESP_EXT1_WAKEUP`.

| Variant | RTC GPIOs |
|---|---|
| esp32     | 0–5, 12–15, 25–27, 32–39 |
| esp32-s2  | 0–21 |
| esp32-s3  | 0–21 |
| esp32-c3  | 0–5 |
| esp32-c6  | 0–7 |

If the design needs deep-sleep wake from a button or sensor, validate the chosen GPIO is in the variant's RTC set.

## UART0 (debug / programming)

Default debug serial on most boards: GPIO1 (TX), GPIO3 (RX) on `esp32`, native USB on S2/S3/C3 etc. **Don't reassign UART0** for application data unless you also reroute the bootloader log — silent factory-floor flash failures are the result.

## Current budgets

- Per-pin recommended source/sink: **20 mA** (40 mA absolute max).
- Total chip GPIO budget: ~1.2 A divided across power-supply pins, but the *ground-bounce-free* design budget is closer to 200 mA total.
- Anything driving more (relays, motors, NeoPixel strings >30 LEDs) needs an external driver / level shifter.

## Default I2C / SPI pins

These are conventions, not requirements — but every ESP32 example online uses them, so deviate only with reason.

| Bus | Variant | SDA / SCL or MOSI / MISO / SCK / CS |
|---|---|---|
| I2C0 | esp32 | SDA=21, SCL=22 |
| I2C0 | esp32-s3 | SDA=8, SCL=9 (DevKitC) |
| SPI2 (HSPI) | esp32 | MOSI=13, MISO=12, SCK=14, CS=15 (overlaps strapping pins — warn) |
| SPI3 (VSPI) | esp32 | MOSI=23, MISO=19, SCK=18, CS=5 (overlaps strapping GPIO5 — warn) |

## Validation checklist

Before declaring a pinmap final, walk through:

- [ ] Every assigned GPIO is *not* in the variant's flash-SPI / PSRAM reserved set.
- [ ] Every strapping pin used has a `// STRAPPING:` comment in the schematic / DTS / config that names the required boot level.
- [ ] On `esp32`, no analog input is on an ADC2 pin if WiFi is enabled in the build.
- [ ] On `esp32`, GPIO12 (MTDI) is either unused, pulled low at boot, or has the flash-voltage efuse explicitly burned at manufacturing.
- [ ] Any deep-sleep wake source is on an RTC GPIO for the chosen variant.
- [ ] UART0 (debug log + bootloader) is reachable on the production board, even if remapped.
- [ ] Per-pin current draw stays at or below 20 mA; the cumulative budget stays below 200 mA.
- [ ] I2C device addresses on a shared bus do not collide.

## External documentation

- ESP32-family datasheets (per variant) — pin attributes, ADC channel maps, RTC capability tables.
- ESP32-family Technical Reference Manuals — strapping pin behavior, eFuse-controlled flash voltage.
