# Security & OTA

Production hardening for ESP-IDF: Secure Boot v2, Flash Encryption (release mode), signed OTA, anti-rollback, NVS encryption, and key custody.

> **Scope.** Everything in this document is **production-only**. Apply it **only** when the user has explicitly requested a production build (the trigger phrases are listed in [SKILL.md](../SKILL.md)). The default development build does not enable any of these flags — they are irreversible on real silicon and would turn a developer board into a single-use device.

## Threat model the defaults address

| Attack | Defense |
|---|---|
| Unauthorized firmware on the device | Secure Boot v2 (RSA 3072 / ECDSA P-256) verifies bootloader and app signatures |
| Reading firmware off the flash chip | Flash Encryption release mode (AES-XTS) |
| Reading credentials from NVS | NVS Encryption with keys in encrypted `nvs_keys` partition |
| Rollback to a known-vulnerable firmware | Anti-rollback (`CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK`) tracks `app_version` in efuse |
| Lab fault injection on bootloader | Secure Boot v2 + RTC watchdog + brownout |
| Stack/buffer overflow exploitation | Stack canary, W^X heap, ASLR (limited on Xtensa) |

## sdkconfig.production.defaults (production overlay)

This overlay is layered on top of the dev-baseline `sdkconfig.defaults` only by `*_production` envs in `platformio.ini`:

```ini
[env:esp32s3_production]
board_build.sdkconfig_defaults = sdkconfig.defaults;sdkconfig.production.defaults
```

The overlay file's contents:

```ini
# --- Secure Boot v2 ---
CONFIG_SECURE_BOOT=y
CONFIG_SECURE_BOOT_V2_ENABLED=y
CONFIG_SECURE_SIGNED_APPS_RSA_SCHEME=y       # or ECDSA on C-series
CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES=y
CONFIG_SECURE_BOOT_SIGNING_KEY="keys/secure_boot_signing_key.pem"

# --- Flash Encryption (RELEASE) ---
CONFIG_SECURE_FLASH_ENC_ENABLED=y
CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE=y
CONFIG_SECURE_BOOT_INSECURE=n                # never y in production

# --- Anti-rollback ---
CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK=y
CONFIG_BOOTLOADER_APP_SECURE_VERSION=1
CONFIG_BOOTLOADER_APP_SECURE_VERSION_SIZE_EFUSE_FIELD=32

# --- NVS encryption ---
CONFIG_NVS_ENCRYPTION=y
# nvs_keys partition is declared in partitions.csv with `encrypted` flag

# --- Watchdogs ---
CONFIG_ESP_TASK_WDT=y
CONFIG_ESP_TASK_WDT_TIMEOUT_S=10
CONFIG_ESP_TASK_WDT_PANIC=y
CONFIG_ESP_INT_WDT=y
CONFIG_ESP_INT_WDT_TIMEOUT_MS=300

# --- Brownout ---
CONFIG_ESP_BROWNOUT_DET=y
CONFIG_ESP_BROWNOUT_DET_LVL_SEL_7=y          # ~2.43V on most variants

# --- Stack canary ---
CONFIG_COMPILER_STACK_CHECK_MODE_NORM=y
CONFIG_COMPILER_STACK_CHECK=y

# --- Logging ---
CONFIG_LOG_DEFAULT_LEVEL_WARN=y              # not VERBOSE/DEBUG in release
CONFIG_LOG_MAXIMUM_LEVEL_INFO=y

# --- OTA ---
CONFIG_APP_ROLLBACK_ENABLE=y
CONFIG_BOOTLOADER_APP_TEST=y                 # test-then-confirm
```

Never put any of these flags into `sdkconfig.defaults` (the dev-baseline file). The validator (`scripts/verify_project.py`) raises `INSECURE_FLAG_IN_DEV_BUILD` if it sees them in a development build — that's intentional, because once burned into efuse on a real device they cannot be undone.

## Key custody (the part that fails most projects)

**The signing key is the device.** Anyone with `secure_boot_signing_key.pem` can ship firmware that runs on every device that trusts it.

| Key | Lives in | Used by |
|---|---|---|
| Secure Boot signing key (`.pem`) | HSM / encrypted CI artifact, never in repo | Build server signs `bootloader.bin` and `app.bin` |
| Flash Encryption key | Generated on-device (release mode) OR pre-provisioned at factory | Bootloader, transparent to app |
| OTA artifact signing key | Same as Secure Boot key (or a separate OTA-only key) | Build server signs OTA images |
| Server TLS root CA | `certs/ca.pem` embedded via `board_build.embed_files` | App when validating TLS |
| Device identity (cert / key) | Per-device, generated at manufacturing, stored in encrypted NVS | App when authenticating to cloud |

**`.gitignore` must contain:** `keys/`, `certs/device_*`, `*.pem`, `*.key`, `secure_boot_signing_key*`.

## OTA — signed image, anti-rollback, test-then-confirm

```c
#include "esp_ota_ops.h"
#include "esp_https_ota.h"

esp_err_t do_ota(const char *url) {
    esp_http_client_config_t http = {
        .url           = url,
        .cert_pem      = (const char *)server_cert_pem_start,
        .timeout_ms    = 10000,
        .keep_alive_enable = true,
    };
    esp_https_ota_config_t ota = { .http_config = &http };

    esp_err_t err = esp_https_ota(&ota);
    if (err != ESP_OK) {
        ESP_LOGE("ota", "ota failed: %s", esp_err_to_name(err));
        return err;
    }

    // After reboot the bootloader marks new image as PENDING_VERIFY.
    // The app has CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE_TIMEOUT_S to confirm.
    // Confirmation should happen ONLY after the app proves it's healthy:
    // network up, backend reachable, sensors responding.
    return ESP_OK;
}

void confirm_after_health_check(void) {
    if (app_health_passed()) {
        ESP_ERROR_CHECK(esp_ota_mark_app_valid_cancel_rollback());
    } else {
        // Returning without confirming → bootloader rolls back on next boot.
        ESP_LOGW("ota", "health check failed, will roll back");
    }
}
```

Don't confirm the new image in `app_main`. The whole point of test-then-confirm is to catch crashes that only surface after running for a while. Confirm after at least one successful end-to-end transaction with the cloud.

## Anti-rollback discipline

`CONFIG_BOOTLOADER_APP_SECURE_VERSION` must increase monotonically across releases. Once a higher version is booted and confirmed, the bootloader burns an efuse that **prevents booting any lower version forever**. This is the desired behavior — and the reason a bricked release-train is unrecoverable.

Add a CI gate that enforces monotonic version progression on every production release:

- Parse `CONFIG_BOOTLOADER_APP_SECURE_VERSION` from `sdkconfig.production.defaults`.
- Compare against the version on the latest released tag (read from `git tag` or your release-tracking system).
- Reject the merge / fail the pipeline if the new value is not strictly greater. A reusable shape:

  ```bash
  prev=$(git show "$LATEST_TAG":sdkconfig.production.defaults \
         | sed -nE 's/^CONFIG_BOOTLOADER_APP_SECURE_VERSION=([0-9]+).*/\1/p')
  curr=$(sed -nE 's/^CONFIG_BOOTLOADER_APP_SECURE_VERSION=([0-9]+).*/\1/p' \
         sdkconfig.production.defaults)
  [ "$curr" -gt "$prev" ] || { echo "anti-rollback regression: $prev -> $curr"; exit 1; }
  ```

Why monotonic and not "version exists": once an old version is rolled out and confirmed, the bootloader burns its number into efuse. A subsequent release with a *lower or equal* version cannot boot — devices brick on the next OTA. A merge gate is cheaper than a recall.

## TLS / HTTPS

- Pin a CA bundle via `board_build.embed_files`. Don't trust the system CA store — there is none.
- Use `mbedtls` directly or the `esp-tls` wrapper. Never disable certificate verification in production.
- For MQTT: `esp-mqtt` with `cert_pem` set, `skip_cert_common_name_check = false`.

## NVS encryption

```c
#include "nvs_flash.h"

static void nvs_init_secure(void) {
    nvs_sec_cfg_t cfg;
    const esp_partition_t *part = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS_KEYS, NULL);
    ESP_ERROR_CHECK(nvs_flash_read_security_cfg(part, &cfg));
    ESP_ERROR_CHECK(nvs_flash_secure_init(&cfg));
}
```

The keys partition itself is encrypted by Flash Encryption — that's the chain of custody.

## Secrets in code: hard rules

- No `const char* api_key = "sk-..."` ever.
- No plaintext WiFi credentials in source. Provision via WiFi-provisioning component (BLE or SoftAP) on first boot, store in encrypted NVS.
- No device certs / private keys in the firmware image. Generated at manufacturing, written to encrypted NVS via a dedicated provisioning flow.
- CI: `grep -rIE 'BEGIN (RSA|EC|PRIVATE)|sk-[A-Za-z0-9_-]{20,}' .` must return zero hits before tagging a release.

## External documentation

- ESP-IDF Programming Guide — Secure Boot V2, Flash Encryption, OTA, NVS Encryption.
- ESP32 Technical Reference Manual — efuse layout, eFuse programming sequence (read before any first-time production flash).
- NIST SP 800-147 / IEC 62443-4-1 — for projects with regulatory firmware-integrity requirements.
