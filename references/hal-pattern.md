# HAL Pattern

Why HAL: testability, vendor portability, MISRA boundary, and a reviewable seam where peripheral access meets application logic. **Application code never includes `driver/*.h` directly.**

## Layering

```
┌─────────────────────────────────────────┐
│   main/, components/app_*               │  application logic
│   includes hal_*.h only                 │
└─────────────────────────────────────────┘
                    │
                    ▼ (interface boundary)
┌─────────────────────────────────────────┐
│   components/app_hal/include/hal_*.h    │  vendor-neutral C API
│   header-only contract                  │  (must NOT be named `hal` —
│                                         │   collides w/ IDF's built-in)
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│   components/port_esp_idf/port_*.cpp    │  ONLY place driver/*.h is included
│   translates HAL → ESP-IDF              │
└─────────────────────────────────────────┘
```

Swapping silicon vendors → swap the port. Unit testing on host → swap in `port_mock`. Auditing for unsafe peripheral access → audit one directory.

## Mandatory rules

1. Every public HAL function returns `hal_result_t` (never `void`, never raw `esp_err_t`). The translation `esp_err_t → hal_result_t` happens inside the port.
2. HAL headers are pure C (`extern "C"` guards) — they are consumable from both C and C++ TUs.
3. HAL headers must not include any ESP-IDF header. Only `<stdint.h>`, `<stddef.h>`, `<stdbool.h>`, and other HAL headers.
4. Resources (GPIO config slots, I2C buses, UART ports) are referred to by **opaque handles or numeric IDs**, never by ESP-IDF types.
5. There is exactly one port implementation linked into the binary at a time — selected by build configuration, not by `#ifdef` inside application code.

## hal_result.h (canonical error type)

```c
#pragma once
#include <stdint.h>

typedef enum {
    HAL_OK              = 0,
    HAL_ERR_INVALID_ARG = 1,
    HAL_ERR_NO_MEM      = 2,
    HAL_ERR_TIMEOUT     = 3,
    HAL_ERR_NOT_FOUND   = 4,
    HAL_ERR_BUSY        = 5,
    HAL_ERR_HW_FAULT    = 6,
    HAL_ERR_UNSUPPORTED = 7,
    HAL_ERR_INTERNAL    = 255
} hal_result_t;

static inline int hal_is_ok(hal_result_t r) { return r == HAL_OK; }
```

`HAL_ERR_INTERNAL` is for unexpected `esp_err_t` codes the port hasn't mapped — log and treat as a bug.

## Port translation example

```c
// components/port_esp_idf/port_gpio.cpp  (ONLY place driver/gpio.h appears)
#include "driver/gpio.h"
#include "esp_log.h"
#include "hal_gpio.h"
#include "hal_result.h"

static constexpr char TAG[] = "port_gpio";

static hal_result_t map_err(esp_err_t e) {
    switch (e) {
        case ESP_OK:                return HAL_OK;
        case ESP_ERR_INVALID_ARG:   return HAL_ERR_INVALID_ARG;
        case ESP_ERR_NO_MEM:        return HAL_ERR_NO_MEM;
        case ESP_ERR_TIMEOUT:       return HAL_ERR_TIMEOUT;
        case ESP_ERR_NOT_FOUND:     return HAL_ERR_NOT_FOUND;
        case ESP_ERR_INVALID_STATE: return HAL_ERR_BUSY;
        default:                    return HAL_ERR_INTERNAL;
    }
}

extern "C" hal_result_t hal_gpio_init(const hal_gpio_cfg_t *cfg) {
    if (cfg == nullptr) return HAL_ERR_INVALID_ARG;

    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << cfg->pin;
    io.mode         = (cfg->dir == HAL_GPIO_DIR_OUT)
                       ? GPIO_MODE_OUTPUT : GPIO_MODE_INPUT;
    io.pull_up_en   = (cfg->pull == HAL_GPIO_PULL_UP)   ? GPIO_PULLUP_ENABLE   : GPIO_PULLUP_DISABLE;
    io.pull_down_en = (cfg->pull == HAL_GPIO_PULL_DOWN) ? GPIO_PULLDOWN_ENABLE : GPIO_PULLDOWN_DISABLE;

    return map_err(gpio_config(&io));
}
```

## Native unit tests via port_mock

For host-side tests, link `components/port_mock/` instead of `components/port_esp_idf/`. The mock keeps an in-memory model of pin levels and lets tests drive inputs / observe outputs.

```cpp
// test/test_hal_native/test_button_debounce.cpp
TEST(Button, Debounces15ms) {
    port_mock_set_input(GPIO_BTN, false);
    button_init();
    port_mock_set_input(GPIO_BTN, true);
    port_mock_advance_ms(5);
    EXPECT_FALSE(button_is_pressed());
    port_mock_advance_ms(20);
    EXPECT_TRUE(button_is_pressed());
}
```

PlatformIO env for this:

```ini
[env:native_test]
platform = native
test_framework = unity
build_flags = -DUSE_PORT_MOCK -I components/app_hal/include
```

## What HAL is NOT

- It is **not** an Arduino-API clone. `hal_*` is intentionally narrower; only the operations the application actually performs.
- It is **not** a place to hide business logic. Debouncing, state machines, retry policy belong in `components/app_*`, not in the port.
- It is **not** a reason to abstract away ESP-IDF features the application genuinely needs (e.g. `esp_timer`, `esp_event`). For those, prefer using ESP-IDF directly from `components/app_core_*`, but document the exception. The strict no-leak rule applies to **driver/peripheral** headers.

## External documentation

- C++ Core Guidelines — RAII (R.1, R.5), no-naked-new (R.11), zero-overhead abstractions (P.4).
- ESP-IDF Programming Guide — Build System (component model), Native Test Framework.
