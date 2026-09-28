#!/usr/bin/env python3
"""Generate realistic Keycloak Event / AdminEvent JSON payloads (KETE shape).

Matches schemas under schemas/json/ and the headers KETE sets on NATS messages:
  eventkind, eventtype, contenttype
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterator, Literal

Kind = Literal["EVENT", "ADMIN_EVENT", "both"]

USER_EVENT_TYPES = [
    "LOGIN",
    "LOGIN_ERROR",
    "LOGOUT",
    "LOGOUT_ERROR",
    "CODE_TO_TOKEN",
    "CODE_TO_TOKEN_ERROR",
    "REFRESH_TOKEN",
    "REFRESH_TOKEN_ERROR",
    "REGISTER",
    "REGISTER_ERROR",
    "VERIFY_EMAIL",
    "UPDATE_PASSWORD",
    "UPDATE_PROFILE",
    "RESET_PASSWORD",
    "SEND_RESET_PASSWORD",
    "CLIENT_LOGIN",
    "IDENTITY_PROVIDER_LOGIN",
    "REVOKE_GRANT",
]

ADMIN_RESOURCE_TYPES = [
    "USER",
    "CLIENT",
    "REALM",
    "REALM_ROLE",
    "CLIENT_ROLE",
    "GROUP",
    "IDENTITY_PROVIDER",
    "AUTHORIZATION_RESOURCE",
    "AUTHORIZATION_SCOPE",
    "AUTHORIZATION_POLICY",
    "USER_SESSION",
    "AUTH_FLOW",
    "AUTH_EXECUTION",
    "COMPONENT",
]

ADMIN_OPERATION_TYPES = ["CREATE", "UPDATE", "DELETE", "ACTION"]

USERNAMES = [
    "alice",
    "bob",
    "carol",
    "dave",
    "erin",
    "frank",
    "grace",
    "heidi",
]
CLIENT_IDS = ["account-console", "admin-cli", "my-app", "mobile-app", "security-admin-console"]
REALMS = [("master", "master"), ("demo", "demo-realm-id"), ("acme", "acme-corp")]
ERROR_CODES = ["invalid_user_credentials", "user_not_found", "expired_code", "invalid_token"]


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ip() -> str:
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _pick_realm(realm_name: str | None) -> tuple[str, str]:
    if realm_name:
        for name, rid in REALMS:
            if name == realm_name:
                return name, rid
        return realm_name, realm_name
    return random.choice(REALMS)


def generate_event(
    *,
    realm_name: str | None = None,
    event_type: str | None = None,
    error_rate: float = 0.1,
    force_error: bool | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (payload, eventtype header value)."""
    name, realm_id = _pick_realm(realm_name)
    etype = event_type or random.choice(USER_EVENT_TYPES)
    if force_error is True:
        if not etype.endswith("_ERROR"):
            etype = f"{etype}_ERROR"
    elif force_error is False:
        if etype.endswith("_ERROR"):
            etype = etype[: -len("_ERROR")]
    elif not etype.endswith("_ERROR") and random.random() < error_rate:
        etype = f"{etype}_ERROR"

    username = random.choice(USERNAMES)
    payload = {
        "id": _uuid(),
        "time": _now_ms(),
        "type": etype,
        "realmId": realm_id,
        "realmName": name,
        "clientId": random.choice(CLIENT_IDS),
        "userId": _uuid(),
        "sessionId": _uuid(),
        "ipAddress": _ip(),
        "error": random.choice(ERROR_CODES) if etype.endswith("_ERROR") else None,
        "details": {
            "username": username,
            "auth_method": "openid-connect",
            "redirect_uri": f"https://app.example.com/callback",
            "response_type": "code",
            "remember_me": random.choice(["true", "false"]),
        },
    }
    return payload, etype


def generate_admin_event(
    *,
    realm_name: str | None = None,
    resource_type: str | None = None,
    operation_type: str | None = None,
    include_representation: bool = True,
    include_kc26_fields: bool = True,
    error_rate: float = 0.05,
    force_error: bool | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (payload, eventtype header value = RESOURCE_OPERATION)."""
    name, realm_id = _pick_realm(realm_name)
    rtype = resource_type or random.choice(ADMIN_RESOURCE_TYPES)
    op = operation_type or random.choice(ADMIN_OPERATION_TYPES)
    resource_id = _uuid()

    path_prefix = {
        "USER": "users",
        "CLIENT": "clients",
        "GROUP": "groups",
        "REALM_ROLE": "roles",
        "CLIENT_ROLE": "clients/roles",
        "IDENTITY_PROVIDER": "identity-provider/instances",
        "COMPONENT": "components",
        "USER_SESSION": "sessions",
        "AUTH_FLOW": "authentication/flows",
        "AUTH_EXECUTION": "authentication/executions",
        "REALM": "",
        "AUTHORIZATION_RESOURCE": "authz/resource-server/resource",
        "AUTHORIZATION_SCOPE": "authz/resource-server/scope",
        "AUTHORIZATION_POLICY": "authz/resource-server/policy",
    }.get(rtype, rtype.lower())

    resource_path = path_prefix if rtype == "REALM" else f"{path_prefix}/{resource_id}"

    has_error = force_error if force_error is not None else (random.random() < error_rate)

    representation: str | None = None
    if include_representation and op != "DELETE":
        if rtype == "USER":
            representation = json.dumps(
                {
                    "id": resource_id,
                    "username": random.choice(USERNAMES),
                    "email": f"{random.choice(USERNAMES)}@example.com",
                    "enabled": True,
                }
            )
        elif rtype == "CLIENT":
            representation = json.dumps(
                {
                    "id": resource_id,
                    "clientId": random.choice(CLIENT_IDS),
                    "enabled": True,
                    "publicClient": True,
                }
            )
        else:
            representation = json.dumps({"id": resource_id, "name": f"{rtype.lower()}-{resource_id[:8]}"})

    payload: dict[str, Any] = {
        "id": _uuid(),
        "time": _now_ms(),
        "realmId": realm_id,
        "realmName": name,
        "authDetails": {
            "realmId": realm_id,
            "realmName": name,
            "clientId": random.choice(["security-admin-console", "admin-cli"]),
            "userId": _uuid(),
            "ipAddress": _ip(),
        },
        "resourceType": rtype,
        "resourceTypeAsString": rtype,
        "operationType": op,
        "resourcePath": resource_path,
        "representation": representation,
        "error": random.choice(ERROR_CODES) if has_error else None,
    }

    if include_kc26_fields:
        payload["details"] = {"custom": "true", "source": "event-generator"}
        payload["resourceId"] = resource_id if rtype != "REALM" else name

    eventtype = f"{rtype}_{op}"
    return payload, eventtype


def iter_events(
    kind: Kind,
    count: int,
    **kwargs: Any,
) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Yield (eventkind, payload, eventtype) count times."""
    for i in range(count):
        if kind == "EVENT":
            payload, etype = generate_event(**{k: v for k, v in kwargs.items() if k in _EVENT_KW})
            yield "EVENT", payload, etype
        elif kind == "ADMIN_EVENT":
            payload, etype = generate_admin_event(**{k: v for k, v in kwargs.items() if k in _ADMIN_KW})
            yield "ADMIN_EVENT", payload, etype
        else:
            if i % 2 == 0:
                payload, etype = generate_event(**{k: v for k, v in kwargs.items() if k in _EVENT_KW})
                yield "EVENT", payload, etype
            else:
                payload, etype = generate_admin_event(**{k: v for k, v in kwargs.items() if k in _ADMIN_KW})
                yield "ADMIN_EVENT", payload, etype


_EVENT_KW = {"realm_name", "event_type", "error_rate", "force_error"}
_ADMIN_KW = {
    "realm_name",
    "resource_type",
    "operation_type",
    "include_representation",
    "include_kc26_fields",
    "error_rate",
    "force_error",
}


def _load_schema(name: str) -> dict[str, Any] | None:
    root = Path(__file__).resolve().parents[2] / "schemas" / "json" / name
    if not root.exists():
        return None
    return json.loads(root.read_text(encoding="utf-8"))


def validate(payload: dict[str, Any], eventkind: str) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed; skip validation (pip install jsonschema)"]

    schema_name = "event.json" if eventkind == "EVENT" else "admin_event.json"
    schema = _load_schema(schema_name)
    if schema is None:
        return [f"schema not found: schemas/json/{schema_name}"]

    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(payload)]


def publish_nats(
    events: list[tuple[str, dict[str, Any], str]],
    *,
    servers: str,
    subject: str,
) -> None:
    try:
        import nats
        from nats.aio.client import Client
    except ImportError as exc:
        raise SystemExit(
            "nats-py is required for --nats. Install with: pip install nats-py"
        ) from exc

    import asyncio

    async def _run() -> None:
        nc: Client = await nats.connect(servers)
        try:
            for eventkind, payload, eventtype in events:
                headers = {
                    "eventkind": eventkind,
                    "eventtype": eventtype,
                    "contenttype": "application/json",
                }
                # Support simple templates: {{realm}}, {{kind}}, {{eventType}}
                actual_subject = (
                    subject.replace("{{realm}}", payload.get("realmName") or "unknown")
                    .replace("{{kind}}", eventkind)
                    .replace("{{eventType}}", eventtype)
                )
                await nc.publish(actual_subject, json.dumps(payload).encode("utf-8"), headers=headers)
            await nc.flush()
        finally:
            await nc.drain()

    asyncio.run(_run())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate Keycloak Event / AdminEvent JSON (KETE NATS message shape).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s --kind EVENT --count 3 --pretty
  %(prog)s --kind ADMIN_EVENT --count 5 --ndjson
  %(prog)s --kind both --count 10 --nats nats://localhost:4222 --subject events.{{realm}}.{{kind}}
  %(prog)s --kind EVENT --type LOGIN --validate
""",
    )
    p.add_argument(
        "--kind",
        choices=["EVENT", "ADMIN_EVENT", "both"],
        default="both",
        help="Which event kind to generate (default: both)",
    )
    p.add_argument("--count", type=int, default=1, help="Number of events to generate")
    p.add_argument("--realm", default=None, help="Force realm name (default: random)")
    p.add_argument("--type", dest="event_type", default=None, help="Force user event type (e.g. LOGIN)")
    p.add_argument("--resource-type", default=None, help="Force admin resource type (e.g. USER)")
    p.add_argument("--operation-type", default=None, help="Force admin operation (CREATE|UPDATE|DELETE|ACTION)")
    p.add_argument("--error-rate", type=float, default=0.1, help="Probability of error events (0-1)")
    p.add_argument("--error", action="store_true", help="Force error events")
    p.add_argument("--no-error", action="store_true", help="Force success events")
    p.add_argument("--no-representation", action="store_true", help="Omit admin representation")
    p.add_argument(
        "--no-kc26-fields",
        action="store_true",
        help="Omit AdminEvent details/resourceId (Keycloak < 26 fields)",
    )
    p.add_argument("--interval", type=float, default=0.0, help="Seconds between events (streaming)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON array to stdout")
    p.add_argument("--ndjson", action="store_true", help="Print one JSON object per line (default for count>1)")
    p.add_argument("--validate", action="store_true", help="Validate against schemas/json/*.json")
    p.add_argument("--nats", metavar="URL", default=None, help="Publish to NATS (e.g. nats://localhost:4222)")
    p.add_argument(
        "--subject",
        default="kete.events",
        help="NATS subject; supports {{realm}}, {{kind}}, {{eventType}}",
    )
    p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible output")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)

    if args.error and args.no_error:
        print("error: --error and --no-error are mutually exclusive", file=sys.stderr)
        return 2

    force_error: bool | None = True if args.error else False if args.no_error else None

    gen_kwargs = {
        "realm_name": args.realm,
        "event_type": args.event_type,
        "resource_type": args.resource_type,
        "operation_type": args.operation_type,
        "error_rate": args.error_rate,
        "force_error": force_error,
        "include_representation": not args.no_representation,
        "include_kc26_fields": not args.no_kc26_fields,
    }

    collected: list[tuple[str, dict[str, Any], str]] = []
    envelopes: list[dict[str, Any]] = []

    for i, (eventkind, payload, eventtype) in enumerate(iter_events(args.kind, args.count, **gen_kwargs)):
        if args.validate:
            errors = validate(payload, eventkind)
            if errors:
                print(f"validation failed for {eventkind}/{eventtype}:", file=sys.stderr)
                for err in errors:
                    print(f"  - {err}", file=sys.stderr)
                return 1

        envelope = {
            "headers": {
                "eventkind": eventkind,
                "eventtype": eventtype,
                "contenttype": "application/json",
            },
            "body": payload,
        }
        collected.append((eventkind, payload, eventtype))
        envelopes.append(envelope)

        if args.nats is None:
            use_ndjson = args.ndjson or (not args.pretty and args.count > 1)
            if use_ndjson:
                print(json.dumps(envelope, ensure_ascii=False))
            # pretty/single handled after loop

        if args.interval > 0 and i < args.count - 1:
            time.sleep(args.interval)

    if args.nats:
        publish_nats(collected, servers=args.nats, subject=args.subject)
        print(f"published {len(collected)} message(s) to {args.nats} subject={args.subject}", file=sys.stderr)
        return 0

    use_ndjson = args.ndjson or (not args.pretty and args.count > 1)
    if not use_ndjson:
        payload_out: Any = envelopes[0] if args.count == 1 else envelopes
        if args.pretty:
            print(json.dumps(payload_out, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(payload_out, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
