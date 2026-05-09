# FreeRTOS Patterns (ESP-IDF SMP)

ESP-IDF ships its own SMP-aware FreeRTOS. The patterns below are the production subset.

## Task creation (always pinned)

```c
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

xTaskCreatePinnedToCore(
    sensor_task,            // entry
    "sensor",               // name (pcTaskGetName / Tracealyzer / GDB)
    4096,                   // stack bytes — measure with uxTaskGetStackHighWaterMark
    nullptr,                // arg
    PRIO_REALTIME_CTRL,     // priority
    &sensor_handle,         // out handle
    APP_CORE_REALTIME);     // explicit core
```

`xTaskCreate` (no affinity) is banned by this skill. See [dual-core-architecture.md](dual-core-architecture.md).

## Stack sizing

Measure, don't guess. Each task should call:

```c
ESP_LOGI(TAG, "stack hwm: %u bytes",
         (unsigned)uxTaskGetStackHighWaterMark(NULL) * sizeof(StackType_t));
```

Provision **at least 1.5×** the high-water mark observed under load. Tasks that take interrupts or call `printf` need extra headroom.

## Queues

For typed messages between tasks. Use a struct, not raw bytes.

```c
typedef struct {
    uint8_t  type;
    uint32_t timestamp_us;
    int16_t  payload[8];
} sensor_msg_t;

QueueHandle_t sensor_q = xQueueCreate(16, sizeof(sensor_msg_t));

// Producer
sensor_msg_t m = { .type = MSG_TEMP, .timestamp_us = esp_timer_get_time() };
if (xQueueSend(sensor_q, &m, pdMS_TO_TICKS(50)) != pdPASS) {
    ESP_LOGW(TAG, "sensor queue full, drop");
}

// Consumer
sensor_msg_t m;
if (xQueueReceive(sensor_q, &m, pdMS_TO_TICKS(100)) == pdPASS) {
    handle(m);
}
```

**Production rule:** never `portMAX_DELAY` on a consumer that has a watchdog. Use a finite timeout and feed the WDT in the loop.

## Mutexes

Priority inheritance is on by default — keep it. Use `xSemaphoreCreateMutex()`, never a plain binary semaphore for mutual exclusion.

```c
SemaphoreHandle_t cfg_mutex = xSemaphoreCreateMutex();

bool with_config(void (*fn)(const config_t*)) {
    if (xSemaphoreTake(cfg_mutex, pdMS_TO_TICKS(100)) != pdPASS) {
        return false;
    }
    fn(&g_config);
    xSemaphoreGive(cfg_mutex);
    return true;
}
```

RAII wrapper for C++ call sites:

```cpp
class MutexGuard {
public:
    explicit MutexGuard(SemaphoreHandle_t m, TickType_t t = portMAX_DELAY)
        : m_(m), held_(xSemaphoreTake(m, t) == pdPASS) {}
    ~MutexGuard() { if (held_) xSemaphoreGive(m_); }
    MutexGuard(const MutexGuard&) = delete;
    MutexGuard& operator=(const MutexGuard&) = delete;
    bool ok() const { return held_; }
private:
    SemaphoreHandle_t m_;
    bool held_;
};
```

## Deadlock prevention

Two rules, in order:

1. **Consistent lock order.** If two tasks ever take both `mutex_a` and `mutex_b`, both must take them in the same order.
2. **Bounded wait.** Use timeouts, log on timeout, release any held locks before returning.

## Event groups (AND/OR conditions)

```c
#define EV_WIFI_UP      (1 << 0)
#define EV_TIME_SYNCED  (1 << 1)
#define EV_PROVISIONED  (1 << 2)

EventGroupHandle_t sys_events = xEventGroupCreate();

// Wait for ALL three before connecting to backend:
EventBits_t bits = xEventGroupWaitBits(
    sys_events,
    EV_WIFI_UP | EV_TIME_SYNCED | EV_PROVISIONED,
    pdFALSE,                          // don't clear
    pdTRUE,                           // wait for ALL
    pdMS_TO_TICKS(30000));
```

## ISR-safe variants

Inside `IRAM_ATTR` ISRs, use the `*FromISR` variants and check `pxHigherPriorityTaskWoken`:

```c
void IRAM_ATTR gpio_isr(void *arg) {
    BaseType_t hp = pdFALSE;
    xQueueSendFromISR(button_q, &evt, &hp);
    if (hp == pdTRUE) portYIELD_FROM_ISR();
}
```

## Watchdog hygiene

Production tasks should subscribe to the Task Watchdog and feed it explicitly:

```c
void net_task(void*) {
    esp_task_wdt_add(NULL);
    for (;;) {
        do_one_pass();
        esp_task_wdt_reset();
    }
}
```

If a task has a legitimate long blocking call (e.g. waiting on TLS handshake), `esp_task_wdt_delete(NULL)` before the call and re-add after.

## Diagnostics

```c
void dump_tasks(void) {
    UBaseType_t n = uxTaskGetNumberOfTasks();
    TaskStatus_t *list = (TaskStatus_t*)pvPortMalloc(n * sizeof(*list));
    n = uxTaskGetSystemState(list, n, NULL);
    for (UBaseType_t i = 0; i < n; ++i) {
        ESP_LOGI("tasks",
            "%-12s prio=%2u core=%d stack_hwm=%5u state=%d",
            list[i].pcTaskName,
            (unsigned)list[i].uxCurrentPriority,
            list[i].xCoreID,                    // -1 = no affinity (should never appear in this project)
            (unsigned)list[i].usStackHighWaterMark,
            list[i].eCurrentState);
    }
    vPortFree(list);
}
```

If `xCoreID` is ever `-1` in the dump, you have a banned `xTaskCreate` call somewhere — track it down.

## External documentation

- ESP-IDF Programming Guide — FreeRTOS (SMP), Task Watchdog.
- FreeRTOS official kernel reference — for primitive semantics independent of the ESP-IDF port.
