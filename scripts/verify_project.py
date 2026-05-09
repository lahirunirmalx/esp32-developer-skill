#!/usr/bin/env python3
"""verify_project.py — validator for an ESP32 / ESP-IDF / PlatformIO project
descriptor.

Build-type policy enforced here:
  - Default build_type is "development". Permissive checks: framework, pinning,
    HAL, partition layout. Production-only flags are NOT required (and will
    raise INSECURE_FLAG_IN_DEV_BUILD if a dev build enables them, since
    Secure Boot / Flash Encryption RELEASE / anti-rollback are irreversible
    on real hardware and have no place in a re-flashable dev environment).
  - "production" is opt-in. Strict checks: every required release flag must
    be present, anti-rollback version must be >= 1, no secrets in repo.

JSON in, JSON out. Output structure: top-level `valid` (bool), `errors[]`,
`warnings[]`, and a `summary` block with counts and the resolved
build_type / variant.

Usage:
    python verify_project.py --format json < project.json
    python verify_project.py --format json project.json
    python verify_project.py --help

Python 3.9+ standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple

# ---- variant capability matrix --------------------------------------------

# variant -> (n_cores, has_wifi, has_bt, has_psram_bus)
VARIANTS: Dict[str, Tuple[int, bool, bool, bool]] = {
    "esp32":    (2, True,  True,  True),
    "esp32s2":  (1, True,  False, True),
    "esp32s3":  (2, True,  True,  True),
    "esp32c3":  (1, True,  True,  False),
    "esp32c6":  (1, True,  True,  False),
    "esp32h2":  (1, False, True,  False),
}

# Required sdkconfig flags for a PRODUCTION build (one-way operations).
REQUIRED_PRODUCTION_FLAGS = [
    "CONFIG_SECURE_BOOT_V2_ENABLED",
    "CONFIG_SECURE_FLASH_ENC_ENABLED",
    "CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK",
    "CONFIG_NVS_ENCRYPTION",
]

# Flags that should be on in BOTH dev and production (cheap, useful in dev).
REQUIRED_ALWAYS_FLAGS = [
    "CONFIG_ESP_TASK_WDT",
    "CONFIG_ESP_INT_WDT",
    "CONFIG_ESP_BROWNOUT_DET",
    "CONFIG_COMPILER_STACK_CHECK",
]

# Flags that are IRREVERSIBLE on real silicon — must not appear in a dev build.
PRODUCTION_ONLY_FLAGS = [
    "CONFIG_SECURE_BOOT_V2_ENABLED",
    "CONFIG_SECURE_FLASH_ENC_ENABLED",
    "CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE",
    "CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK",
    "CONFIG_NVS_ENCRYPTION",
]

# Aliases so legacy "release" payloads are interpreted as "production"
# and explicit "dev" maps to "development".
BUILD_TYPE_ALIASES = {
    "dev":         "development",
    "development": "development",
    "debug":       "development",
    "release":     "production",
    "production":  "production",
    "prod":        "production",
}

# ---- finding helpers ------------------------------------------------------

def err(code: str, msg: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "error", "message": msg, **extra}

def warn(code: str, msg: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "warning", "message": msg, **extra}

# ---- validators -----------------------------------------------------------

def check_variant(p: Dict[str, Any], errors: List, warnings: List) -> Tuple[int, bool]:
    variant = p.get("variant")
    if variant not in VARIANTS:
        errors.append(err(
            "UNKNOWN_VARIANT",
            f"variant {variant!r} is not one of {sorted(VARIANTS)}"))
        return 0, False
    cores, has_wifi, _has_bt, _ = VARIANTS[variant]
    return cores, has_wifi

def check_framework(p: Dict[str, Any], errors: List, warnings: List) -> None:
    fw = p.get("framework")
    if fw != "espidf":
        errors.append(err(
            "FRAMEWORK_NOT_ESPIDF",
            f"framework must be 'espidf' for production; got {fw!r}"))

def check_tasks(p: Dict[str, Any], cores: int, errors: List, warnings: List) -> None:
    tasks = p.get("tasks") or []
    if not tasks:
        warnings.append(warn(
            "NO_TASKS_DECLARED",
            "no tasks declared — at least app_main is expected"))
        return
    seen_names = set()
    cores_used = set()
    for t in tasks:
        name = t.get("name", "<unnamed>")
        if name in seen_names:
            errors.append(err("DUPLICATE_TASK_NAME",
                              f"duplicate task name {name!r}", task=name))
        seen_names.add(name)

        core = t.get("core")
        if core is None:
            errors.append(err(
                "TASK_NOT_PINNED",
                f"task {name!r} has no core affinity; "
                f"use xTaskCreatePinnedToCore", task=name))
        elif not isinstance(core, int) or core < 0 or core >= cores:
            errors.append(err(
                "TASK_PINNED_TO_MISSING_CORE",
                f"task {name!r} pinned to core {core} but variant has "
                f"{cores} core(s)", task=name, core=core))

        if core is not None:
            cores_used.add(core)

        prio = t.get("priority")
        if prio is None:
            errors.append(err("TASK_MISSING_PRIORITY",
                              f"task {name!r} has no priority", task=name))
        elif isinstance(prio, int) and prio > 7:
            warnings.append(warn(
                "TASK_PRIORITY_TOO_HIGH",
                f"task {name!r} priority={prio} fights WiFi/BT host tasks; "
                f"prefer <= 7", task=name, priority=prio))

        stack = t.get("stack")
        if stack is None:
            warnings.append(warn("TASK_STACK_UNDECLARED",
                                 f"task {name!r} has no stack size",
                                 task=name))
        elif isinstance(stack, int) and stack < 2048:
            warnings.append(warn(
                "TASK_STACK_SMALL",
                f"task {name!r} stack={stack}B is small; printf alone "
                f"can use 1.5KB", task=name, stack=stack))

    if cores >= 2 and len(cores_used) < 2:
        warnings.append(warn(
            "DUAL_CORE_UNDERUSED",
            f"variant has {cores} cores but tasks only pinned to "
            f"{sorted(cores_used)}; consider splitting net vs realtime"))

def normalize_build_type(p: Dict[str, Any]) -> str:
    """Default to development; map common aliases (release/debug/prod) to
    the canonical 'development' or 'production'."""
    raw = (p.get("build_type") or "development").lower()
    return BUILD_TYPE_ALIASES.get(raw, raw)

def check_sdkconfig(p: Dict[str, Any], errors: List, warnings: List) -> None:
    cfg = p.get("sdkconfig") or {}
    build_type = normalize_build_type(p)

    # Always-on flags apply to both dev and production.
    for flag in REQUIRED_ALWAYS_FLAGS:
        if not cfg.get(flag):
            warnings.append(warn(
                "ALWAYS_ON_FLAG_MISSING",
                f"sdkconfig missing {flag}=y (recommended in every build)",
                flag=flag))

    if build_type == "production":
        # Strict: every production hardening flag must be present.
        for flag in REQUIRED_PRODUCTION_FLAGS:
            if not cfg.get(flag):
                errors.append(err(
                    "PRODUCTION_FLAG_MISSING",
                    f"production sdkconfig missing {flag}=y",
                    flag=flag))
        if cfg.get("CONFIG_SECURE_BOOT_INSECURE"):
            errors.append(err(
                "INSECURE_FLAG_SET",
                "CONFIG_SECURE_BOOT_INSECURE must NOT be y in a production build"))
        log_level = cfg.get("CONFIG_LOG_DEFAULT_LEVEL")
        if isinstance(log_level, str) and log_level.upper() in ("DEBUG", "VERBOSE"):
            warnings.append(warn(
                "DEBUG_LOG_LEVEL_IN_PRODUCTION",
                f"CONFIG_LOG_DEFAULT_LEVEL={log_level} in production; "
                f"prefer WARN or INFO"))
        anti_rb = cfg.get("CONFIG_BOOTLOADER_APP_SECURE_VERSION")
        if isinstance(anti_rb, int) and anti_rb < 1:
            errors.append(err(
                "ANTI_ROLLBACK_VERSION_INVALID",
                f"CONFIG_BOOTLOADER_APP_SECURE_VERSION must be >= 1; "
                f"got {anti_rb}"))
    elif build_type == "development":
        # Strict the OTHER way: irreversible flags must NOT be on in dev.
        for flag in PRODUCTION_ONLY_FLAGS:
            if cfg.get(flag):
                errors.append(err(
                    "INSECURE_FLAG_IN_DEV_BUILD",
                    f"{flag}=y appears in a development build; this flag is "
                    f"irreversible on real silicon and must only be set in "
                    f"the *_production env",
                    flag=flag))
    else:
        warnings.append(warn(
            "UNKNOWN_BUILD_TYPE",
            f"unrecognised build_type {build_type!r}; expected "
            f"'development' or 'production'"))

def check_partitions(p: Dict[str, Any], errors: List, warnings: List) -> None:
    parts = p.get("partitions") or []
    if not parts:
        warnings.append(warn(
            "PARTITIONS_NOT_DECLARED",
            "no partition table declared — descriptor cannot verify OTA layout"))
        return
    subtypes = {x.get("subtype") for x in parts}
    needed = {"factory", "ota_0", "ota_1", "ota", "nvs"}
    missing = needed - subtypes
    if missing:
        errors.append(err(
            "PARTITION_LAYOUT_INCOMPLETE",
            f"partition table missing required subtypes: "
            f"{sorted(missing)} (need factory + 2 OTA slots + otadata + nvs)",
            missing=sorted(missing)))
    if "nvs_keys" not in subtypes:
        warnings.append(warn(
            "NVS_KEYS_PARTITION_MISSING",
            "no nvs_keys partition; required when CONFIG_NVS_ENCRYPTION=y"))

def check_secrets(p: Dict[str, Any], errors: List, warnings: List) -> None:
    leaks = p.get("declared_secrets_in_repo") or []
    for s in leaks:
        errors.append(err(
            "SECRET_IN_REPO",
            f"secret material {s!r} present in repo; move to HSM / "
            f"encrypted CI artifact", path=s))

# ---- entry point ----------------------------------------------------------

def validate(p: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    cores, _has_wifi = check_variant(p, errors, warnings)
    check_framework(p, errors, warnings)
    if cores:
        check_tasks(p, cores, errors, warnings)
    check_sdkconfig(p, errors, warnings)
    check_partitions(p, errors, warnings)
    check_secrets(p, errors, warnings)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "variant": p.get("variant"),
            "build_type": normalize_build_type(p),
        },
    }

def render_text(result: Dict[str, Any]) -> str:
    lines = []
    s = result["summary"]
    head = "OK" if result["valid"] else "FAIL"
    lines.append(f"[{head}] variant={s.get('variant')} "
                 f"build={s.get('build_type')} "
                 f"errors={s['errors']} warnings={s['warnings']}")
    for e in result["errors"]:
        lines.append(f"  ERROR  {e['code']}: {e['message']}")
    for w in result["warnings"]:
        lines.append(f"  WARN   {w['code']}: {w['message']}")
    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate an ESP32 production project descriptor.")
    ap.add_argument("input", nargs="?",
                    help="JSON file (default: stdin)")
    ap.add_argument("--format", choices=("json", "text"), default="json")
    args = ap.parse_args()

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"valid": False,
                          "errors": [{"code": "INVALID_JSON",
                                      "severity": "error",
                                      "message": str(e)}],
                          "warnings": [],
                          "summary": {"errors": 1, "warnings": 0}}))
        return 2
    except OSError as e:
        print(json.dumps({"valid": False,
                          "errors": [{"code": "INPUT_NOT_FOUND",
                                      "severity": "error",
                                      "message": str(e)}],
                          "warnings": [],
                          "summary": {"errors": 1, "warnings": 0}}))
        return 2

    result = validate(payload)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result))

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
