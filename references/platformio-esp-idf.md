# PlatformIO + ESP-IDF Project Layout

Production project skeleton, build/upload/monitor commands, and the rules for how `platformio.ini`, partition tables, `sdkconfig.defaults`, and `idf_component.yml` interact.

## Why ESP-IDF (not Arduino)

| Concern | Arduino-ESP32 | ESP-IDF |
|---|---|---|
| Secure Boot v2 | Limited control via menuconfig | First-class, fully configurable |
| Flash Encryption release mode | Awkward | Documented production flow |
| Anti-rollback (`CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK`) | Inherited but undocumented | Explicit Kconfig + `app_version` |
| Component versioning | per-library `lib_deps` | `idf_component.yml` (semver, registry) |
| Per-task watchdogs | Possible | Native API |
| Custom partition tables | Possible | Native, documented |
| Long-term toolchain support | Tied to Arduino-ESP32 release cycle | Tied to ESP-IDF LTS branches |

**Verdict for production:** ESP-IDF. Use Arduino only for prototypes.

## platformio.ini layering

The default env is **always** a `*_dev` environment. `*_production` is opt-in.

```ini
[platformio]
default_envs = esp32s3_dev           ; default = development. Always.
src_dir = main                       ; required when using IDF-canonical layout (main/)

[env]                                ; shared across all envs
platform = espressif32@^6.7.0
framework = espidf
monitor_speed = 115200
monitor_filters = esp32_exception_decoder, time
; Lenient globals — PlatformIO has no per-component flag scoping, so
; everything here also compiles ESP-IDF source. Strict flags for app
; code go in per-component CMakeLists via target_compile_options(...).
build_flags =
    -Wall
    -Werror=return-type
    -Werror=implicit-fallthrough
    -Wno-error=format                ; IDF v5.2 esp_tls.c trips %p+addrinfo on GCC 13+
    -DCONFIG_FREERTOS_GENERATE_RUN_TIME_STATS=1
build_unflags = -std=gnu++11
build_flags += -std=gnu++17
board_build.partitions = partitions.csv

; Default — `pio run` flashes this.
[env:esp32s3_dev]
board = esp32-s3-devkitc-1
build_type = debug
build_flags = ${env.build_flags} -Og -g3 -DDEVELOPMENT_BUILD=1
board_build.sdkconfig_defaults = sdkconfig.defaults

; Opt-in — must be invoked explicitly:
;   pio run -e esp32s3_production -t upload
[env:esp32s3_production]
board = esp32-s3-devkitc-1
build_type = release
build_flags = ${env.build_flags} -O2 -DPRODUCTION_BUILD=1
board_build.sdkconfig_defaults = sdkconfig.defaults;sdkconfig.production.defaults
board_build.embed_txtfiles = certs/api_root_ca.pem
```

### Pin the platform version

`platform = espressif32@^6.7.0` locks IDF v5.x. Don't track HEAD — supply-chain risk and reproducibility.

### Multiple variants in one project

```ini
[env:esp32_release]
board = esp32dev
build_flags = ${env.build_flags} -O2

[env:esp32s3_release]
board = esp32-s3-devkitc-1
build_flags = ${env.build_flags} -O2 -DBOARD_HAS_PSRAM
board_build.mcu = esp32s3
```

`platformio.ini` is *not* the place for SDK options — those go in `sdkconfig.defaults` (and per-variant `sdkconfig.defaults.<board>` if needed).

## sdkconfig layering

The order applied depends on the env:

**`*_dev` env** (default):
1. `sdkconfig.defaults` — dev-baseline (watchdogs, brownout, stack canary, INFO logs). No signing, no encryption.
2. `sdkconfig` — generated, gitignored.

**`*_production` env** (opt-in):
1. `sdkconfig.defaults` — same dev-baseline.
2. `sdkconfig.production.defaults` — overlay that turns ON Secure Boot v2, Flash Encryption RELEASE, anti-rollback, NVS encryption, and drops log level to WARN.
3. `sdkconfig` — generated, gitignored.

Selection is controlled by `board_build.sdkconfig_defaults` per env (semicolon-separated; later files win on conflicts). This is the mechanism that makes the production hardening opt-in: a `pio run` with no `-e` flag never reads the production overlay.

To regenerate:
```bash
pio run -t menuconfig -e esp32s3_dev          # tweak dev SDK options
pio run -t menuconfig -e esp32s3_production   # tweak production SDK options
```

## Partition tables

Place `partitions.csv` next to `platformio.ini`. Reference it via `board_build.partitions = partitions.csv`. A production device must reserve OTA slots from day one — partition layout cannot be retroactively migrated on fielded units.

Minimum production layout (4 MB flash):

```
# Name,    Type, SubType, Offset,   Size,     Flags
nvs,       data, nvs,     0x9000,   0x6000
otadata,   data, ota,     0xf000,   0x2000
phy_init,  data, phy,     0x11000,  0x1000
factory,   app,  factory, 0x20000,  0x140000
ota_0,     app,  ota_0,   0x160000, 0x140000
ota_1,     app,  ota_1,   0x2A0000, 0x140000
nvs_keys,  data, nvs_keys,0x3E0000, 0x1000, encrypted
storage,   data, spiffs,  0x3E1000, 0x1F000
```

Adjust offsets/sizes for 8 MB / 16 MB flash. Encrypted `nvs_keys` is required when `CONFIG_NVS_ENCRYPTION=y`.

## idf_component.yml

For ESP-IDF managed components (registry: `components.espressif.com`). Lives in `main/idf_component.yml`:

```yaml
dependencies:
  espressif/mdns: "^1.4.0"
  espressif/esp_websocket_client: "^1.2.0"
  espressif/json_generator: "^1.1.0"
  idf: ">=5.1"
```

**Rule:** ESP-IDF dependencies belong in `idf_component.yml`, *not* `lib_deps`. Mixing both produces hard-to-diagnose link errors because PlatformIO's `lib_deps` resolver and IDF's component manager pull from different roots.

## Common commands

```bash
# Build the DEFAULT (development) env
pio run

# Upload the development env
pio run -t upload

# Combined flash + monitor (development)
pio run -t upload -t monitor

# Serial monitor with exception decoder
pio device monitor

# Build the PRODUCTION env (opt-in — only when user explicitly asked for it)
pio run -e esp32s3_production

# Upload a production build (irreversible: burns Secure Boot key digest etc.)
pio run -e esp32s3_production -t upload

# Clean / full clean
pio run -t clean
pio run -t cleanall

# Configure SDK options interactively
pio run -t menuconfig                    # dev env
pio run -t menuconfig -e esp32s3_production

# Erase flash before flashing (factory reset — dev only; production efuses are one-way)
pio run -t erase

# Component-level size report
pio run -t size
```

## Common pitfalls (PlatformIO + ESP-IDF integration)

These are the integration issues that bite first-time scaffolds. Bake the fixes into `platformio.ini` and component layout from the start — retrofitting under build-error pressure is harder than getting it right up front.

### 1. `Missing the 'src' folder with project sources`
PlatformIO's IDF wrapper looks for `src/` by default. If you follow the IDF-canonical layout (with `main/`), you **must** set:
```ini
[platformio]
src_dir = main
```
Without it, `pio run` aborts before compiling anything.

### 2. Component-name collisions with built-in IDF components
ESP-IDF reserves these component names — never name a project component the same:
`hal`, `driver`, `freertos`, `log`, `esp_*`, `bootloader`, `mbedtls`, `nvs_flash`, `app_update`, `lwip`, `mdns`, `wpa_supplicant`, `esp-tls`.

A project `components/hal/` will silently shadow ESP-IDF's `hal` component. Symptom: cryptic build errors deep in IDF source — `fatal error: hal/uart_types.h: No such file or directory` from `driver/uart.h`, `fatal error: hal/misc.h` from `efuse_periph.h`, etc. (IDF's hal headers live at `framework-espidf/components/hal/include/hal/*.h`; if your component wins the name, IDF's include path is dropped.)

**Convention:** prefix project components with `app_`: `app_hal`, `app_strobe`, `app_core_realtime`. Update `REQUIRES` lines in dependent components' `CMakeLists.txt` accordingly.

### 3. No top-level `CMakeLists.txt` at the project root
PlatformIO generates its own. Adding a hand-rolled one (with `include($ENV{IDF_PATH}/tools/cmake/project.cmake)` etc.) fights the wrapper and breaks the build. Only `main/CMakeLists.txt` and `components/*/CMakeLists.txt` are user-managed.

### 4. Strict warning flags applied globally to ESP-IDF source
PlatformIO's `[env].build_flags` apply to **every** translation unit, including framework source. ESP-IDF v5.2 + GCC 13+ does not compile clean under `-Wextra -Wpedantic -Werror=format` — for instance, `esp_tls.c` line ~213 passes a `struct addrinfo *` to `%p` (only valid for `void *`) and fails under `-Werror=format=`.

Keep globals lenient (`-Wall -Werror=return-type -Werror=implicit-fallthrough -Wno-error=format`). Apply the strict app-code flags at the component level:
```cmake
# components/app_strobe/CMakeLists.txt
idf_component_register(SRCS "strobe_task.cpp" INCLUDE_DIRS "include" REQUIRES app_hal log freertos)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wextra -Wpedantic -Werror=conversion)
```

### 5. INI parser quirks
`build_flags  +=  -std=gnu++17` (double-space) is parsed as an unknown key in PlatformIO 6.x. Use single-space: `build_flags += -std=gnu++17`.

### 6. ESP-IDF deps in `lib_deps`
Mixing `lib_deps` and `idf_component.yml` produces hard-to-diagnose link errors because PlatformIO's resolver and IDF's component manager pull from different roots. ESP-IDF dependencies belong **only** in `main/idf_component.yml`.

## External documentation

- PlatformIO Core docs — `platformio.ini` reference, ESP-IDF integration, `board_build.*` options.
- ESP-IDF Programming Guide — Build System, Partition Tables, Component Manager.
