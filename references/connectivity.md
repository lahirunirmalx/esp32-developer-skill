# Connectivity

WiFi / BLE provisioning, MQTT, HTTPS, reconnection, and footprint trimming for ESP-IDF. The production-relevant subset.

## Provisioning (no plaintext credentials in firmware)

Use the `wifi_provisioning` component. First boot: device exposes a BLE GATT service (or SoftAP) and accepts WiFi creds + a backend endpoint URL. Stored in encrypted NVS.

```c
#include "wifi_provisioning/manager.h"
#include "wifi_provisioning/scheme_ble.h"

void provision_if_needed(void) {
    bool provisioned = false;
    ESP_ERROR_CHECK(wifi_prov_mgr_is_provisioned(&provisioned));
    if (provisioned) return;

    wifi_prov_mgr_config_t cfg = {
        .scheme = wifi_prov_scheme_ble,
        .scheme_event_handler = WIFI_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM,
    };
    ESP_ERROR_CHECK(wifi_prov_mgr_init(cfg));
    ESP_ERROR_CHECK(wifi_prov_mgr_start_provisioning(
        WIFI_PROV_SECURITY_2,                 // SRP6a
        /*username*/ "wifiprov",
        /*pop*/ "<per-device PoP from sticker QR>",
        /*service_name*/ "PROV_XXYYZZ",
        /*service_key*/ NULL));
}
```

Per-device Proof-of-Possession (PoP) printed on the box / QR code — different per device, generated at manufacturing.

## Reconnect supervisor

WiFi will drop. The application must not crash; it should log, back off, retry, and keep functioning where possible.

```c
static int reconnect_attempts = 0;

static void on_disconnect(void *arg, esp_event_base_t base, int32_t id, void *data) {
    int delay_ms = 1000 * (1 << MIN(reconnect_attempts, 6));   // 1s, 2s, 4s, ... cap 64s
    ESP_LOGW("wifi", "disconnect, retry in %d ms", delay_ms);
    vTaskDelay(pdMS_TO_TICKS(delay_ms));
    esp_wifi_connect();
    reconnect_attempts++;
}

static void on_got_ip(void *arg, esp_event_base_t base, int32_t id, void *data) {
    reconnect_attempts = 0;
    xEventGroupSetBits(sys_events, EV_WIFI_UP);
}
```

Exponential backoff capped — never busy-retry. Always log every transition.

## TLS — the only acceptable defaults

```c
esp_http_client_config_t cfg = {
    .url               = "https://api.example.com/v1/telemetry",
    .cert_pem          = (const char *)server_cert_pem_start,   // pinned via embed_files
    .crt_bundle_attach = NULL,                                   // do not use the system bundle
    .skip_cert_common_name_check = false,
    .timeout_ms        = 10000,
    .keep_alive_enable = true,
    .keep_alive_idle   = 10,
    .keep_alive_interval = 5,
    .keep_alive_count  = 3,
};
```

`platformio.ini`:

```ini
board_build.embed_txtfiles =
    certs/api_root_ca.pem
```

Generates symbols `_binary_api_root_ca_pem_start` / `_end` automatically.

## MQTT (esp-mqtt)

```c
#include "mqtt_client.h"

esp_mqtt_client_config_t mqtt = {
    .broker = {
        .address = { .uri = "mqtts://mqtt.example.com:8883" },
        .verification = { .certificate = (const char*)broker_ca_pem_start },
    },
    .credentials = {
        .authentication = { .certificate = (const char*)device_cert_pem_start,
                             .key        = (const char*)device_key_pem_start },
    },
    .session = {
        .keepalive = 30,
        .last_will = {
            .topic = "devices/abc/status",
            .msg   = "offline",
            .qos   = 1,
            .retain = 1,
        },
    },
};

esp_mqtt_client_handle_t client = esp_mqtt_client_init(&mqtt);
esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
esp_mqtt_client_start(client);
```

Always set Last Will and Testament. Always use mTLS for production fleet identity (device cert + key from encrypted NVS).

## BLE peripheral (NimBLE host stack — production default on ESP-IDF v5+)

NimBLE has a much smaller footprint than Bluedroid. In `sdkconfig`:

```ini
CONFIG_BT_ENABLED=y
CONFIG_BT_NIMBLE_ENABLED=y
CONFIG_BT_BLE_ENABLED=y
```

**Send-When-Idle** for power: batch notifications, don't notify on every sample. The radio dominates the energy budget on a battery-powered design — every wake of the BT controller costs orders of magnitude more than the compute saved by emitting more often. Concretely: enqueue samples into a small ring buffer and flush via `ble_gatts_indicate` only when (a) the buffer is half-full, (b) a watchdog timer expires (e.g. every 1 s), or (c) a connection event opportunistically opens. Combine with a peripheral-latency increase on the connection parameters so the central allows longer idle periods before requiring a response.

## Async DNS

Blocking `gethostbyname` on the main task is a real-world cause of "deadline missed" reports. Use the lwIP async DNS or an explicit DNS task.

## Footprint trimming

Turn off what you don't use. The lwIP and BT host stacks are the largest sources of RAM/Flash in a typical connected ESP32 build, and most projects use a fraction of what's compiled in by default.

```ini
# Disable IPv6 if you don't need it (~10 KB RAM saved on lwIP)
CONFIG_LWIP_IPV6=n

# Disable TCP if you only do CoAP/UDP
CONFIG_LWIP_TCP=n

# Drop unused L2 protocols
CONFIG_LWIP_PPP_SUPPORT=n
CONFIG_LWIP_DHCP6=n

# If you don't use NimBLE peripheral mode, disable it explicitly
CONFIG_BT_NIMBLE_ROLE_BROADCASTER=n
CONFIG_BT_NIMBLE_ROLE_OBSERVER=n
```

Verify the trim made it into the final `.config` (not just `sdkconfig.defaults`) — `pio run` regenerates `sdkconfig` and a typo in the defaults file is silently ignored. After a build:

```bash
grep -E '^CONFIG_LWIP_(IPV6|TCP)=' .pio/build/<env>/config/sdkconfig
```

If the line is missing or `=y`, the trim didn't take effect.

## External documentation

- ESP-IDF Programming Guide — `wifi_provisioning`, `esp-mqtt`, `esp_https_ota`, NimBLE host stack.
- RFC 7252 (CoAP), RFC 5246 (TLS 1.2), RFC 8446 (TLS 1.3) — for production-grade TLS / IoT-protocol decisions.
