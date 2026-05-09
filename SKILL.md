---
name: esp32-developer
description: USE WHENEVER an ESP32 project is being created, scaffolded, or bootstrapped — including simple bring-up demos (blink, button, sensor read), prototypes, and production firmware. Default stack: ESP-IDF framework, PlatformIO project system, HAL abstraction over ESP-IDF drivers, FreeRTOS tasks with explicit core affinity (dual-core partitioning on ESP32 / ESP32-S3, single-core on C3/C6/H2/S2). Generates platformio.ini (with src_dir=main), OTA-capable partitions.csv, dev-baseline sdkconfig.defaults, components/app_hal/ + components/port_esp_idf/ HAL split, app_main.cpp supervisor, and per-feature components/app_*/ task modules. Default build is development (fast flash, verbose logs, no signing, no flash encryption); production hardening (Secure Boot v2, Flash Encryption release mode, signed OTA, anti-rollback, NVS encryption) is applied only when the user explicitly requests a production build. Trigger on any of: ESP32 variant named (esp32, esp32s2, esp32s3, esp32c3, esp32c6, esp32h2), "new ESP32 project", "blink an LED on ESP32", "wire a sensor to ESP32", "scaffold ESP32 firmware", "harden ESP32 for production". Even a one-LED blink should be scaffolded with this skill — the cost is small and the resulting project can grow without rewriting the layout.
license: MIT
metadata:
  domain: embedded
  triggers: ESP32, ESP32-C3, ESP32-S3, ESP32-S2, ESP32-C6, ESP32-H2, ESP-IDF, PlatformIO, FreeRTOS, HAL, blink, LED, button, sensor, GPIO, I2C, SPI, UART, dual-core, core affinity, secure boot, OTA, flash encryption, production firmware, industrial IoT, new project, scaffold, bootstrap, init
  role: specialist
  scope: implementation
  output-format: code
---

# ESP32 Production Application

Bootstrap an ESP32 application that can ship. Defaults: **ESP-IDF framework**, **PlatformIO project system**, **HAL-first** application code, **both cores used when the SoC has them**.

> **Framework policy.** The **default and only framework is ESP-IDF**, regardless of project size. Even a one-LED blink is scaffolded with ESP-IDF + HAL + FreeRTOS task wiring. Do **not** silently generate an Arduino project to "keep it simple". The Arduino framework is used **only when the user explicitly requests it** ("use Arduino", "Arduino IDE", "Arduino-ESP32", "Arduino sketch") — in which case this skill does not apply, and you should redirect to a plain Arduino-style project outside this scaffolding.

> **Layout policy.** Every project — bring-up, prototype, or production — uses the same HAL-split layout: `components/app_hal/`, `components/port_esp_idf/`, `components/app_<feature>/`, `main/app_main.cpp`. Do not collapse to a single `src/main.cpp` for "simple" projects. The cost of the structure is small (≈12 small files); the cost of bolting a HAL onto an Arduino-style sketch a month later is large.

> **Build-type policy.** The **default build is development** — unsigned, unencrypted, fast iteration, verbose logs. Production hardening (Secure Boot v2, Flash Encryption release, signed OTA, anti-rollback, NVS encryption) is **opt-in only**. Apply it **only when the user explicitly says** "production build", "build for production", "release for production", "harden for production", or equivalent. A user saying "release build", "optimized build", or "build it" without the word *production* still gets the development security posture (optimization may be raised, but signing and encryption stay off).

## 1 · When to Use

**Default trigger: any time an ESP32 project is being initialized.** This includes simple bring-up demos. A one-LED blink scaffolded under this skill costs ~12 small files and gives the user something that can grow into a real product without a rewrite — opting *out* of the structure for a "quick test" usually creates a second rewrite a week later.

Trigger this skill when the request matches **any** of:

- An ESP32 variant is named (esp32, esp32s2, esp32s3, esp32c3, esp32c6, esp32h2) and *any* code is being written for it — even "just blink an LED", "test the UART", "read the sensor"
- "new ESP32 project", "scaffold ESP32 firmware", "bootstrap ESP32", "ESP32 starter", "init an ESP32 project"
- ESP-IDF + PlatformIO together
- "use both cores", "pin to APP_CPU / PRO_CPU", "core affinity"
- Secure boot, flash encryption, signed OTA, anti-rollback for ESP32
- A HAL abstraction is required over ESP-IDF drivers
- Wiring an external device (sensor / display / radio / motor driver) to an ESP32

**Do not silently downgrade to Arduino** to "save effort" on a small demo. If the user explicitly says "use Arduino" or "Arduino IDE", redirect: explain the skill produces ESP-IDF (with HAL + FreeRTOS scaffolding) and ask whether they want to proceed or genuinely need Arduino. If they confirm Arduino, this skill does not apply.

**Do not** apply this skill to non-ESP32 chips (STM32, RP2040, nRF52, etc.) — redirect.

## 2 · Variant Capability Matrix

Always confirm or detect the variant before generating `platformio.ini`. Capability differences directly drive pin maps, core-affinity decisions, and feature flags.

| Variant   | Cores | Core Names           | Wireless              | USB-OTG | PSRAM Cap | Secure Boot v2 | Flash Encryption |
|-----------|-------|----------------------|-----------------------|---------|-----------|----------------|------------------|
| esp32     | 2     | PRO_CPU(0), APP_CPU(1) | WiFi 4 + BT/BLE       | No      | external  | Yes (RSA)      | Yes              |
| esp32s2   | 1     | CPU(0)               | WiFi 4                | Yes     | external  | Yes (RSA)      | Yes              |
| esp32s3   | 2     | PRO_CPU(0), APP_CPU(1) | WiFi 4 + BLE 5        | Yes     | external  | Yes (RSA)      | Yes              |
| esp32c3   | 1     | CPU(0)               | WiFi 4 + BLE 5        | No      | none      | Yes (ECDSA)    | Yes              |
| esp32c6   | 1     | CPU(0)               | WiFi 6 + BLE 5 + 802.15.4 | No  | none      | Yes (ECDSA)    | Yes              |
| esp32h2   | 1     | CPU(0)               | BLE 5 + 802.15.4 (no WiFi) | No | none      | Yes (ECDSA)    | Yes              |

**Dual-core rule.** "Use both cores if supported" → on `esp32` and `esp32s3`, partition tasks across `PRO_CPU` (core 0) and `APP_CPU` (core 1). On single-core variants, *do not* fabricate dual-core tasking — pin everything to core 0 and document the fall-back. See [references/dual-core-architecture.md](references/dual-core-architecture.md).

## 3 · Reference Loading

Always load when starting a new app. Load the rest only when their trigger matches.

| File | Trigger |
|------|---------|
| `references/platformio-esp-idf.md` | Always (it's the project skeleton). |
| `references/dual-core-architecture.md` | Variant is dual-core OR user mentions cores, latency, real-time. |
| `references/hal-pattern.md` | Always (HAL is mandatory per requirements). |
| `references/security-and-ota.md` | Production build, signed OTA, secure boot, flash encryption, rollback. |
| `references/pin-safety.md` | Quick checklist: strapping / flash-SPI / ADC2-WiFi / RTC / current budget — load on every pinmap review. |
| `references/esp32-pins.md` | Deep authority: complete GPIO pin table, flash/PSRAM reservations, protocol pin groups, full ADC channel map. Load when assigning pins beyond a trivial count or when in doubt. |
| `references/esp32-specifics.md` | Strapping pins deep dive (especially GPIO12/MTDI flash-voltage hazard), ADC2/WiFi conflict explained, flash/PSRAM pin details. Load when boot behavior, brownout, deep-sleep efuse, or analog + WiFi together are in scope. |
| `references/electrical-constraints.md` | Voltage levels, current limits, power rails, drive strength, pull-resistor sizing formulas. Load when level shifting (3.3V/5V), current budget, pull-up calculation, or external power are in scope. |
| `references/protocol-quick-ref.md` | I²C / SPI / UART / 1-Wire / PWM specs, speed modes, pull-up requirements, common addresses. Load when a protocol bus is being chosen, sized, or terminated. |
| `references/common-devices.md` | Per-part wiring catalog. Load when the user names a module by part number (BME280, SSD1306, DHT22, DS18B20, MPU6050, ADS1115, INA219, NEO-6M, ST7789, nRF24L01, SX1276/RFM95W, MCP2515, PCA9685, L298N, DRV8825/A4988, MCP23017, WS2812B/NeoPixel, MAX31855, …). |
| `references/freertos-patterns.md` | Tasks, queues, semaphores, deadlock, priority, timing. |
| `references/connectivity.md` | WiFi/BLE provisioning, MQTT, HTTPS, reconnect logic. |

## 4 · Core Workflow

### Step 1 — Detect / confirm variant
Ask if the variant is ambiguous. Default to most conservative (`esp32` + `WROOM`) only if the user explicitly declines. Capture: variant, module (WROOM/WROVER), PSRAM yes/no, flash size, intended wireless.

### Step 2 — Generate the PlatformIO project
Single-environment `platformio.ini` targeting `framework = espidf`. Dependencies are added via `idf_component.yml` (managed components) — **do not** mix in `lib_deps` for ESP-IDF components. Template: [assets/platformio.ini](assets/platformio.ini).

### Step 3 — Write the partition table for OTA
Even if OTA is "later", lay down `factory + ota_0 + ota_1 + nvs + nvs_keys + otadata + storage` now. Retrofitting partitions invalidates devices already in the field. Template: [assets/partitions.csv](assets/partitions.csv).

### Step 4 — Apply sdkconfig: dev-baseline always, production overlay on opt-in
The dev-friendly baseline ([assets/sdkconfig.defaults](assets/sdkconfig.defaults)) keeps watchdogs, brownout, stack canary, and FreeRTOS run-time stats on (cheap, useful in dev), but leaves Secure Boot, Flash Encryption, anti-rollback, and NVS encryption **off** so the device can be re-flashed freely. The production overlay ([assets/sdkconfig.production.defaults](assets/sdkconfig.production.defaults)) is layered on top **only** in the `*_production` PlatformIO env (via `board_build.sdkconfig_defaults = "sdkconfig.defaults;sdkconfig.production.defaults"`). Do not enable production-only flags in the base file — once Flash Encryption release mode or anti-rollback is burned into efuse, the device cannot be returned to dev mode.

### Step 5 — Drop in the HAL layer
Application code talks to `hal_*.h` interfaces, never directly to `driver/gpio.h`, `driver/i2c.h`, etc. The `port_esp_idf/` implementation is the only translation unit that includes ESP-IDF driver headers. This unlocks: unit testing on host (with a `port_mock/`), cleaner peripheral swaps, MISRA boundary auditing. See [references/hal-pattern.md](references/hal-pattern.md) and [assets/hal/hal_gpio.h](assets/hal/hal_gpio.h).

### Step 6 — Wire external devices (sensors, displays, radios, motor drivers)
The wiring cluster — load these together whenever a peripheral is being attached:

1. **Identify the part**: when the user names a module (BME280, SSD1306, DHT22, DS18B20, MPU6050, ADS1115, INA219, NEO-6M, ST7789, nRF24L01, SX1276/RFM95W, MCP2515, PCA9685, L298N, DRV8825/A4988, MCP23017, WS2812B/NeoPixel, MAX31855, …) load [references/common-devices.md](references/common-devices.md) to pull interface, required pins, default and alternate I²C addresses, voltage, pull-ups, and known gotchas.
2. **Pick the protocol bus**: load [references/protocol-quick-ref.md](references/protocol-quick-ref.md) for I²C / SPI / UART / 1-Wire / PWM specs (speed modes, pull-up sizing, clock-mode selection, address-collision detection).
3. **Assign pins for the chosen variant**: cross-check against [references/pin-safety.md](references/pin-safety.md) for the production checklist, then [references/esp32-pins.md](references/esp32-pins.md) for the full GPIO table (flash/PSRAM reservations, protocol pin groups, ADC channel map) and [references/esp32-specifics.md](references/esp32-specifics.md) for the deep-dive on strapping pins (especially GPIO12/MTDI flash-voltage hazard) and the ADC2/WiFi conflict on the original `esp32`.
4. **Size pulls and check power**: load [references/electrical-constraints.md](references/electrical-constraints.md) for voltage levels, per-pin and total current limits, drive-strength settings, and pull-up/pull-down resistor sizing formulas. If mixing 3.3V logic with 5V devices (HD44780, WS2812B, some HC-05 variants), call out the level shifter explicitly — `74AHCT125`, `74HCT245`, or `SN74LV1T34` are the standard fixes.
5. **Resolve I²C address conflicts**: prefer changing the device's address-strapping pins. Use the I²C address-collision map at the bottom of `common-devices.md`. Fall back to a TCA9548A I²C multiplexer (`0x70`–`0x77`) only when address pins cannot disambiguate.

### Step 7 — Wire FreeRTOS tasks with explicit core affinity
Always use `xTaskCreatePinnedToCore` (not `xTaskCreate`). Even on single-core variants, pin to core 0 explicitly to make intent visible. Production task plan in [references/dual-core-architecture.md](references/dual-core-architecture.md).

### Step 8 — Validate
Run [scripts/verify_project.py](scripts/verify_project.py) against the project descriptor (variant, framework, tasks, sdkconfig flags, partition layout). The script reads JSON on stdin and emits JSON with `errors[]`, `warnings[]`, and a `summary` block (full schema in Section 9). Fix all errors, decide on warnings, re-run.

## 5 · Mandatory Constraints

### Always (dev and production — applies to ALL projects, including one-LED blinks)

The constraints below are **non-negotiable for every ESP32 project this skill scaffolds, no matter how trivial.** "It's just a blink test" is not a valid reason to skip the HAL split, the framework choice, or the task structure. The whole point of this skill is that a 12-file blink demo can grow into a shipping product without rewriting the layout — every shortcut taken at bring-up turns into a rewrite later.

- **ESP-IDF is the default and only framework.** Use `framework = espidf` in `platformio.ini`. Do not generate `framework = arduino` projects, even for trivial demos, **unless the user explicitly requests Arduino** ("use Arduino", "Arduino IDE", "Arduino-ESP32"). If the user is silent on the framework, choose ESP-IDF and proceed.
- **HAL split is mandatory even for one-peripheral demos.** A blink demo still has `components/app_hal/`, `components/port_esp_idf/`, and a `components/app_<feature>/`. Do not collapse the layout to a single `src/main.cpp` "to keep it simple" — the HAL boundary is what makes the project testable, swappable, and reviewable. If application code needs GPIO/I2C/SPI/UART, it goes through `hal_*`, never directly through `driver/*.h`.
- Use **`xTaskCreatePinnedToCore`** with explicit core ID for every task, even on single-core variants.
- Route **all peripheral I/O** through the project's HAL (`hal_gpio_*`, `hal_i2c_*`, `hal_uart_*`, `hal_spi_*`).
- Enable in `sdkconfig.defaults`: Task Watchdog, Interrupt Watchdog, Stack Canary, Brownout Detector. These are useful in dev too and have negligible cost.
- Reserve a **partition table that supports OTA from day one** (factory + 2× OTA slots + otadata + a `nvs_keys` slot). The partition layout cannot be retroactively migrated on fielded units — leaving room for OTA + encryption is free in dev and necessary later.
- Use **C++17 or newer** with `-Wall -Wextra -Wpedantic -Werror=return-type` and `-fno-exceptions -fno-rtti` (ESP-IDF default; document any deviation).
- Apply RAII (`std::unique_ptr`, scope guards) for every resource: queues, semaphores, file handles, sockets, mutexes.
- Use `ESP_ERROR_CHECK_WITHOUT_ABORT(...)` + structured error logging in long-running paths; reserve `ESP_ERROR_CHECK(...)` (which aborts) for boot-time invariants only.
- Pin one core for **time-critical / real-time** work and the other for **best-effort** work on dual-core variants.

### Only when user explicitly requests a production build

The trigger phrases are listed at the top of this skill. When matched, **also** apply:

- `CONFIG_SECURE_BOOT_V2_ENABLED=y` with a per-project signing key (path supplied by the user or pulled from CI secrets — never committed).
- `CONFIG_SECURE_FLASH_ENC_ENABLED=y` + `CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE=y`.
- `CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK=y` and a `CONFIG_BOOTLOADER_APP_SECURE_VERSION` ≥ 1, incremented monotonically on each production release.
- `CONFIG_NVS_ENCRYPTION=y` with the `nvs_keys` partition flagged `encrypted` in `partitions.csv`.
- `CONFIG_LOG_DEFAULT_LEVEL_WARN=y` (or `_INFO`) — never `_DEBUG`/`_VERBOSE` in production binaries.
- Signed OTA (`esp_https_ota` with verified TLS cert and signature check), test-then-confirm (`esp_ota_mark_app_valid_cancel_rollback` only after the app proves itself healthy).
- A `.gitignore` line for `keys/`, `*.pem`, `*.key`, and a CI grep gate that blocks merging if private-key material appears in the diff.

Before flipping a device into production for the first time: confirm with the user that they understand **Flash Encryption release mode is irreversible** and **anti-rollback efuses are one-way**. Do not silently enable these without confirmation even if "production build" was requested — say what's about to be burned and wait for go-ahead.

### MUST NOT DO

- **Never** use `framework = arduino`.
- **Never** call `xTaskCreate` (no affinity) — silent migration across cores breaks real-time analysis.
- **Never** include ESP-IDF driver headers (`driver/*.h`) outside of `port_esp_idf/*.cpp`. Application code must not know which SoC vendor it runs on.
- **Never** use `delay(...)` / busy loops for synchronization. Use `vTaskDelay`, queues, semaphores, or event groups.
- **Never** assign a strapping pin (esp32: GPIO0/2/5/12/15) without an explicit `// STRAPPING:` comment stating the required boot level. **Never** drive GPIO12 high at boot on `esp32` without efuse override — it forces 1.8V flash and bricks 3.3V modules.
- **Never** assign flash SPI pins (esp32: GPIO6–11; WROVER also: GPIO16–17 for PSRAM).
- **Never** use ADC2 channels (esp32 only: GPIO0/2/4/12–15/25–27) when WiFi is enabled.
- **Never** check pre-shared keys, secure-boot signing keys, or device certificates into the repo. They live in a manufacturing HSM / encrypted artifact bucket. CI provisions them at flash time.
- **Never** enable Secure Boot, Flash Encryption release mode, anti-rollback, or NVS encryption in the development env — these are one-way operations on the device. Keep them confined to the `*_production` env.
- **Never** use `printf` for application output — use `ESP_LOGx` so log level, tag, and color are honored.
- **Never** name a project component `hal`, `driver`, `freertos`, `log`, `esp_*`, `bootloader`, `mbedtls`, or any other ESP-IDF reserved component name. The IDF build system silently lets the project component shadow the framework one, hiding its public headers (e.g. `hal/uart_types.h`, `hal/misc.h`) and breaking unrelated IDF source. Prefix project components with `app_` (`app_hal`, `app_strobe`, …).
- **Never** put a top-level `CMakeLists.txt` at the project root in a PlatformIO + ESP-IDF project. PlatformIO generates its own; a hand-rolled one fights the wrapper. Only `main/CMakeLists.txt` and `components/*/CMakeLists.txt` are under your control.
- **Never** apply strict warning flags (`-Wextra`, `-Wpedantic`, `-Werror=format`, `-Werror=conversion`, etc.) globally via PlatformIO `build_flags`. PlatformIO has no per-component scoping, so they also compile ESP-IDF source — current GCC + IDF v5.2 fails on `esp_tls.c` and others. Globally apply only `-Wall -Werror=return-type -Werror=implicit-fallthrough` (and `-Wno-error=format` to neutralize the known IDF format bug). Strict flags for application code go in per-component CMakeLists via `target_compile_options(${COMPONENT_LIB} PRIVATE -Wextra -Wpedantic ...)`.
- **Never** omit `src_dir = main` in `[platformio]` when using IDF-canonical layout. Without it, PlatformIO looks for `src/` and aborts with `Missing the 'src' folder with project sources` — even though `main/` exists.

## 6 · Project Skeleton

```
my-esp32-app/
├── platformio.ini                    # framework = espidf, board, build flags, src_dir=main
├── partitions.csv                    # factory + ota_0 + ota_1 + nvs + nvs_keys + otadata
├── sdkconfig.defaults                # security ON, watchdogs ON, log level WARN
├── sdkconfig.defaults.<variant>      # per-variant overrides
│                                     # NOTE: NO top-level CMakeLists.txt — PlatformIO generates its own.
│                                     #       Adding one fights the wrapper and breaks the build.
├── main/                             # PlatformIO src_dir points here (IDF "main" component)
│   ├── CMakeLists.txt
│   ├── app_main.cpp                  # entry: idf bootstrap + spawn supervisor
│   └── idf_component.yml             # managed component deps
├── components/
│   ├── app_hal/                      # public HAL interfaces (header-only API)
│   │   ├── include/hal_gpio.h        # NOTE: directory MUST NOT be named `hal` — that
│   │   ├── include/hal_i2c.h         #       collides with ESP-IDF's built-in `hal`
│   │   ├── include/hal_uart.h        #       component, hiding hal/uart_types.h, hal/misc.h
│   │   ├── include/hal_spi.h         #       and breaking IDF's own builds.
│   │   └── include/hal_result.h
│   ├── port_esp_idf/                 # the ONLY place ESP-IDF drivers are included
│   │   ├── CMakeLists.txt            # REQUIRES app_hal driver esp_common log
│   │   ├── port_gpio.cpp
│   │   └── port_i2c.cpp
│   ├── app_core_realtime/            # tasks pinned to APP_CPU (core 1)
│   ├── app_core_network/             # tasks pinned to PRO_CPU (core 0)
│   └── app_security/                 # OTA, key handling, secure-boot helpers
└── test/
    └── test_hal_native/              # host-side unit tests against hal_*.h via port_mock
```

The skill itself follows the same layout (separated `references/` + `scripts/` + `assets/`) so application-side conventions and skill-side conventions reinforce each other.

## 7 · Quick Patterns

### platformio.ini (development is the default; production is explicit opt-in)

```ini
[platformio]
default_envs = esp32s3_dev          ; default = development. Always.
src_dir = main                      ; PlatformIO's IDF wrapper expects sources in src/ by
                                    ; default; point it at IDF-canonical main/ instead.
                                    ; Without this, `pio run` fails: "Missing the `src` folder".

[env]
platform = espressif32@^6.7.0
framework = espidf
monitor_speed = 115200
monitor_filters = esp32_exception_decoder, time
; PlatformIO has NO per-component flag scoping — anything here is also
; applied to ESP-IDF source. Keep globals lenient enough that IDF builds
; clean. Strict flags for application code (-Wextra, -Wpedantic, etc.)
; belong in per-component CMakeLists.txt via:
;     target_compile_options(${COMPONENT_LIB} PRIVATE -Wextra -Wpedantic ...)
build_flags =
    -Wall
    -Werror=return-type
    -Werror=implicit-fallthrough
    -Wno-error=format               ; IDF v5.2 esp_tls.c trips %p+addrinfo* on GCC 13+
    -DCONFIG_FREERTOS_GENERATE_RUN_TIME_STATS=1
build_unflags = -std=gnu++11
build_flags += -std=gnu++17
board_build.partitions = partitions.csv

; ---- DEVELOPMENT (default) -----------------------------------------------
; Unsigned, unencrypted, INFO-level logs, fast flash. Re-flashable forever.
[env:esp32s3_dev]
board = esp32-s3-devkitc-1
build_type = debug
build_flags = ${env.build_flags} -Og -g3 -DDEVELOPMENT_BUILD=1
board_build.sdkconfig_defaults = sdkconfig.defaults

; ---- PRODUCTION (opt-in: pio run -e esp32s3_production) ------------------
; Secure Boot v2, Flash Encryption RELEASE, anti-rollback, NVS encryption,
; WARN logs, signed OTA. IRREVERSIBLE on first flash.
[env:esp32s3_production]
board = esp32-s3-devkitc-1
build_type = release
build_flags = ${env.build_flags} -O2 -DPRODUCTION_BUILD=1
board_build.sdkconfig_defaults = sdkconfig.defaults;sdkconfig.production.defaults
board_build.embed_txtfiles = certs/api_root_ca.pem
```

`pio run` (no args) flashes the development env. The user must type `pio run -e esp32s3_production -t upload` to engage the irreversible production hardening.

### app_main.cpp (dual-core skeleton)

```cpp
#include "esp_system.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "soc/soc_caps.h"

static constexpr char TAG[] = "app";

#if SOC_CPU_CORES_NUM >= 2
static constexpr BaseType_t kCorePro = 0;   // PRO_CPU: WiFi/BT, network, logging
static constexpr BaseType_t kCoreApp = 1;   // APP_CPU: real-time work
#else
static constexpr BaseType_t kCorePro = 0;
static constexpr BaseType_t kCoreApp = 0;   // single-core: pin everything to core 0
#endif

extern "C" void network_task(void*);   // implemented in components/app_core_network
extern "C" void realtime_task(void*);  // implemented in components/app_core_realtime

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "boot ok, cores=%d", SOC_CPU_CORES_NUM);

    // Network / housekeeping pinned to PRO_CPU
    xTaskCreatePinnedToCore(network_task, "net", 8192, nullptr,
                            tskIDLE_PRIORITY + 2, nullptr, kCorePro);

    // Real-time / latency-critical pinned to APP_CPU when available
    xTaskCreatePinnedToCore(realtime_task, "rt", 4096, nullptr,
                            tskIDLE_PRIORITY + 5, nullptr, kCoreApp);
}
```

### HAL interface (no ESP-IDF leakage)

```c
// components/app_hal/include/hal_gpio.h
//   (directory must NOT be named `hal` — collides with ESP-IDF's built-in component)
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "hal_result.h"

typedef enum { HAL_GPIO_DIR_IN, HAL_GPIO_DIR_OUT } hal_gpio_dir_t;
typedef enum { HAL_GPIO_PULL_NONE, HAL_GPIO_PULL_UP, HAL_GPIO_PULL_DOWN } hal_gpio_pull_t;

typedef struct {
    uint8_t          pin;
    hal_gpio_dir_t   dir;
    hal_gpio_pull_t  pull;
} hal_gpio_cfg_t;

#ifdef __cplusplus
extern "C" {
#endif
hal_result_t hal_gpio_init(const hal_gpio_cfg_t *cfg);
hal_result_t hal_gpio_set(uint8_t pin, bool level);
hal_result_t hal_gpio_get(uint8_t pin, bool *level);
#ifdef __cplusplus
}
#endif
```

The `driver/gpio.h` include lives in `components/port_esp_idf/port_gpio.cpp` only — see [assets/hal/hal_gpio.h](assets/hal/hal_gpio.h) and [assets/src/port_gpio.cpp](assets/src/port_gpio.cpp).

## 8 · Validation Checklist

### Always (every build, dev or production)

- [ ] `pio run` (default = `*_dev`) builds with `-Werror=return-type` clean.
- [ ] Every task is created with `xTaskCreatePinnedToCore`. Grep: `grep -nE 'xTaskCreate\b' components/ main/` returns zero hits.
- [ ] Every peripheral access in `main/` and `components/app_*` goes through `hal_*`. No `driver/*.h` includes outside `components/port_esp_idf/`.
- [ ] No strapping-pin or flash-SPI-pin assignments, or each is justified with a `// STRAPPING:` comment plus boot-state note.
- [ ] No private keys / certs / device IDs in the repo (search: `grep -rIE 'BEGIN (RSA|EC|PRIVATE)|sk-|api[_-]?key' .`).
- [ ] Stack high-water marks logged for each task; all tasks below 75% allocation under load.
- [ ] `idf.py size-components` shows app fits in the smaller of `ota_0` / `ota_1`.
- [ ] `python scripts/verify_project.py < project.json` returns `valid: true` for both `build_type: development` and a hypothetical `build_type: production` payload.

### Only when shipping a production build

Run these only after the user has explicitly authorized a production build.

- [ ] `pio run -e <board>_production` builds clean.
- [ ] Final `sdkconfig` shows `CONFIG_SECURE_BOOT_V2_ENABLED=y`, `CONFIG_SECURE_FLASH_ENC_ENABLED=y`, `CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE=y`, `CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK=y`, `CONFIG_NVS_ENCRYPTION=y`.
- [ ] `CONFIG_BOOTLOADER_APP_SECURE_VERSION` is strictly greater than the previous production tag.
- [ ] Signing key path resolves to a CI/HSM-supplied location, not a file in the repo tree.
- [ ] OTA flow round-trips on a *test* device: signed image installs, anti-rollback rejects an older signed image.
- [ ] User has been warned (and acknowledged) that Flash Encryption release mode and anti-rollback efuses are one-way.

## 9 · Script Interface

### verify_project.py

`scripts/verify_project.py` audits a project descriptor and the generated configs.

```bash
python scripts/verify_project.py --format json < project.json
```

Input:
```json
{
  "variant": "esp32 | esp32s2 | esp32s3 | esp32c3 | esp32c6 | esp32h2",
  "module": "WROOM | WROVER | null",
  "wifi_enabled": true,
  "framework": "espidf",
  "build_type": "development | production",
  "tasks": [
    {"name": "net", "core": 0, "priority": 4, "stack": 8192},
    {"name": "rt",  "core": 1, "priority": 6, "stack": 4096}
  ],
  "sdkconfig": {
    "CONFIG_SECURE_BOOT_V2_ENABLED": true,
    "CONFIG_SECURE_FLASH_ENC_ENABLED": true,
    "CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK": true,
    "CONFIG_ESP_TASK_WDT": true
  }
}
```

Output:
```json
{
  "valid": true,
  "errors": [
    {"code": "FRAMEWORK_NOT_ESPIDF", "severity": "error", "message": "..."},
    {"code": "TASK_PINNED_TO_MISSING_CORE", "severity": "error", "message": "..."}
  ],
  "warnings": [
    {"code": "SECURE_BOOT_DISABLED", "severity": "warning", "message": "..."},
    {"code": "DEBUG_LOG_LEVEL_IN_RELEASE", "severity": "warning", "message": "..."}
  ],
  "summary": {"errors": 0, "warnings": 1}
}
```

Exit codes: `0` valid (warnings ok), `1` errors found, `2` invalid input. Python 3.9+ stdlib only.

## 10 · Resources

- **References** ([references/](references/)):
  - `platformio-esp-idf.md` — `platformio.ini`, partitions, `idf_component.yml`, sdkconfig layering.
  - `dual-core-architecture.md` — core-affinity rules, task taxonomy, IPC across cores.
  - `hal-pattern.md` — HAL contract, port layout, native testing.
  - `security-and-ota.md` — Secure Boot v2, Flash Encryption, signed OTA, anti-rollback, NVS encryption, key custody.
  - `pin-safety.md` — production pinmap checklist (strapping / flash-SPI / ADC2-WiFi / RTC / current budget).
  - `esp32-pins.md` — complete GPIO pin table, flash/PSRAM reservations, protocol pin groups, full ADC channel map.
  - `esp32-specifics.md` — strapping pin deep dive, ADC2/WiFi conflict explained, flash/PSRAM pin details, GPIO12 flash-voltage hazard.
  - `electrical-constraints.md` — voltage levels, current limits, power rails, pull-resistor sizing, drive strength, level shifting.
  - `protocol-quick-ref.md` — I²C / SPI / UART / 1-Wire / PWM specs, speed modes, common addresses, pull-up requirements.
  - `common-devices.md` — per-part wiring catalog (interface, pins, I²C addresses, voltage, pull-ups, gotchas) for ~28 sensor / display / radio / motor-driver modules, plus an I²C address-collision map.
  - `freertos-patterns.md` — task creation, queues, mutexes, deadlocks, priority inversion.
  - `connectivity.md` — WiFi provisioning, MQTT/HTTPS, reconnection, NVS-backed config.
- **Scripts** ([scripts/](scripts/)):
  - `verify_project.py` — JSON-in/JSON-out project validator.
- **Assets** ([assets/](assets/)):
  - `platformio.ini` — `default_envs = *_dev`; `*_production` is opt-in.
  - `partitions.csv` — OTA-capable partition table (used by both envs).
  - `sdkconfig.defaults` — dev-friendly baseline (watchdogs / brownout / canary on, signing & encryption off).
  - `sdkconfig.production.defaults` — overlay applied only by `*_production` env.
  - `main/app_main.cpp` — dual-core entry point.
  - `hal/hal_gpio.h`, `hal/hal_result.h` — HAL contract example.
  - `src/port_gpio.cpp` — sole ESP-IDF driver translation unit.

## 11 · Requirements

- Python 3.9+ (stdlib only) for `scripts/`.
- PlatformIO Core 6.x (`pip install platformio`).
- ESP-IDF v5.x (PlatformIO pulls the matching toolchain via `platform = espressif32@^6.7.0`).
- For signed OTA: `espsecure.py`, `espefuse.py` (bundled with ESP-IDF).
