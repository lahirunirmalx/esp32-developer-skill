# Dual-Core Architecture

How to partition an ESP-IDF application across `PRO_CPU` (core 0) and `APP_CPU` (core 1) on dual-core variants — and what to do on single-core variants.

## Which variants are dual-core?

| Variant | Cores | Notes |
|---|---|---|
| esp32     | 2 | Xtensa LX6 |
| esp32s2   | 1 | Xtensa LX7 |
| esp32s3   | 2 | Xtensa LX7, vector unit |
| esp32c3   | 1 | RISC-V |
| esp32c6   | 1 | RISC-V, WiFi 6 |
| esp32h2   | 1 | RISC-V, no WiFi |

**Rule:** detect at compile time using `SOC_CPU_CORES_NUM` from `soc/soc_caps.h`. Don't read the variant string at runtime.

```c
#include "soc/soc_caps.h"

#if SOC_CPU_CORES_NUM >= 2
#  define APP_CORE_REALTIME 1   // APP_CPU
#  define APP_CORE_NETWORK  0   // PRO_CPU
#else
#  define APP_CORE_REALTIME 0   // single-core: pin everything to core 0
#  define APP_CORE_NETWORK  0
#endif
```

## Always pin tasks (even on single-core)

```c
xTaskCreatePinnedToCore(
    network_task,                  // entry
    "net",                         // name (debugging)
    8192,                          // stack bytes
    nullptr,                       // arg
    tskIDLE_PRIORITY + 2,          // priority
    &network_task_handle,          // out handle
    APP_CORE_NETWORK);             // explicit core, never tskNO_AFFINITY
```

`xTaskCreate` (no affinity) is banned by this skill. Even on single-core variants, pin to core 0 so intent is visible and grep-friendly.

## Default task taxonomy (dual-core variants)

| Core | Workload | Examples | Priority band |
|---|---|---|---|
| PRO_CPU (0) | Network, system services, logging, "best effort" | WiFi/BT stack, MQTT, HTTPS, OTA download, log queue drain | 1–4 |
| APP_CPU (1) | Real-time / latency-critical | Sensor sampling, motor control, LED frame, audio DSP, control loop | 4–8 |

Why this split: WiFi & BT host tasks are anchored to PRO_CPU by ESP-IDF. Putting your latency-critical work on APP_CPU eliminates contention with the wireless stack.

### Priority bands

```c
// Match these defines across the project
#define PRIO_IDLE_BG          1   // logging drain, telemetry
#define PRIO_NETWORK          3   // MQTT, HTTPS
#define PRIO_AUDIO_DSP        4
#define PRIO_REALTIME_CTRL    5   // motor / LED frame
#define PRIO_SAFETY_CRITICAL  7   // watchdog feeders, e-stop handlers
```

Anything above 7 fights the IDF event loop and the WiFi stack. Don't.

## Cross-core IPC

Use FreeRTOS primitives — they are SMP-safe in ESP-IDF FreeRTOS.

| Need | Primitive |
|---|---|
| Best-effort message passing, fixed schema | `xQueueCreate` |
| Bounded back-pressure between producer and consumer | counting semaphore + queue |
| Mutual exclusion for shared structs | `xSemaphoreCreateMutex` (priority inheritance ON by default) |
| Multiple "ready" conditions | `xEventGroupCreate` |
| One-to-many fan-out (e.g. system events) | `esp_event` system |

**Avoid** raw `volatile` flags across cores — even reads are not atomic for >32-bit values, and the ESP-IDF FreeRTOS memory model requires explicit barriers.

## Real-time deadline pattern

If APP_CPU has a hard frame deadline (e.g. 8.33 ms for 120 FPS LED, or 1 ms for a control loop), use periodic delay:

```c
void realtime_task(void*) {
    TickType_t last_wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(8);   // 120 FPS

    for (;;) {
        int64_t t0 = esp_timer_get_time();

        sample_inputs();
        compute();
        drive_outputs();

        int64_t elapsed_us = esp_timer_get_time() - t0;
        if (elapsed_us > 8000) {
            ESP_LOGW("rt", "frame overrun: %lld us", elapsed_us);
        }
        vTaskDelayUntil(&last_wake, period);
    }
}
```

`vTaskDelayUntil` keeps the period stable even if a frame ran long. `vTaskDelay` does not.

## Priority inversion

ESP-IDF FreeRTOS mutexes have priority inheritance enabled by default — keep it that way. Do **not** roll your own "spin lock" out of `volatile`s for shared resources; you will get unbounded inversion.

If a high-priority task on APP_CPU shares state with a low-priority task on PRO_CPU, use `xSemaphoreCreateMutex()` and accept the inheritance bump.

## Watchdog discipline

Each pinned task should be subscribed to the Task Watchdog (`esp_task_wdt_add(NULL)` from inside the task) and feed it (`esp_task_wdt_reset()`) at least once per `CONFIG_ESP_TASK_WDT_TIMEOUT_S`. Tasks that legitimately block longer than that should `esp_task_wdt_delete(NULL)` before blocking and re-add after.

## Debugging cross-core behavior

```c
// Print which core, with task name
ESP_LOGI(TAG, "running on core %d task=%s",
         xPortGetCoreID(),
         pcTaskGetName(NULL));
```

`uxTaskGetSystemState()` enumerates all tasks with priority, state, core, and stack high-water mark. See [freertos-patterns.md](freertos-patterns.md) for the diagnostic helper.

## External documentation

- ESP-IDF Programming Guide — FreeRTOS (SMP), `esp_event`, `esp_timer`.
- ESP32 Technical Reference Manual — Xtensa core layout (PRO_CPU vs APP_CPU pinning behavior).
