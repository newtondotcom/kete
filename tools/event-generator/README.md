# KETE Event Generator

Python CLI that generates realistic **Keycloak `Event`** and **`AdminEvent`** JSON payloads in the same shape as KETE's JSON serializer, including the NATS headers (`eventkind`, `eventtype`, `contenttype`).

Schemas: [`schemas/json/event.json`](../../schemas/json/event.json) and [`schemas/json/admin_event.json`](../../schemas/json/admin_event.json).

## Requirements

- Python 3.10+
- Optional extras for validation / NATS publish:

```bash
pip install -r tools/event-generator/requirements.txt
```

## Usage

```bash
# One random event of each kind (pretty JSON)
python3 tools/event-generator/generate_events.py --kind both --count 2 --pretty

# Stream NDJSON user events
python3 tools/event-generator/generate_events.py --kind EVENT --count 20 --ndjson

# Force a LOGIN success
python3 tools/event-generator/generate_events.py --kind EVENT --type LOGIN --no-error --pretty

# Admin USER_CREATE with representation
python3 tools/event-generator/generate_events.py \
  --kind ADMIN_EVENT --resource-type USER --operation-type CREATE --pretty

# Validate against schemas/json/*.json
python3 tools/event-generator/generate_events.py --kind both --count 10 --validate --ndjson

# Publish to NATS (headers match KETE)
python3 tools/event-generator/generate_events.py \
  --kind both --count 5 \
  --nats nats://localhost:4222 \
  --subject 'events.{{realm}}.{{kind}}'
```

## Output envelope

Stdout wraps each message so consumers can see both headers and body:

```json
{
  "headers": {
    "eventkind": "EVENT",
    "eventtype": "LOGIN",
    "contenttype": "application/json"
  },
  "body": {
    "id": "...",
    "time": 1704816000000,
    "type": "LOGIN",
    "realmId": "demo-realm-id",
    "realmName": "demo",
    "clientId": "my-app",
    "userId": "...",
    "sessionId": "...",
    "ipAddress": "10.1.2.3",
    "error": null,
    "details": { "username": "alice", "...": "..." }
  }
}
```

When publishing with `--nats`, only the **body** is sent as the message payload; the three headers are set on the NATS message (same as KETE).

## Subject templates

`--subject` supports:

| Token | Value |
|-------|--------|
| `{{realm}}` | `realmName` from the payload |
| `{{kind}}` | `EVENT` or `ADMIN_EVENT` |
| `{{eventType}}` | e.g. `LOGIN` or `USER_CREATE` |

## Flags

| Flag | Description |
|------|-------------|
| `--kind` | `EVENT`, `ADMIN_EVENT`, or `both` |
| `--count` | Number of events |
| `--realm` | Force realm name |
| `--type` | Force user event type (`LOGIN`, …) |
| `--resource-type` / `--operation-type` | Force admin resource/operation |
| `--error-rate` | Probability of error events (default `0.1`) |
| `--error` / `--no-error` | Force error or success |
| `--no-representation` | Omit admin `representation` |
| `--no-kc26-fields` | Omit `details` / `resourceId` on admin events |
| `--interval` | Delay between events (seconds) |
| `--pretty` / `--ndjson` | Output format |
| `--validate` | Validate against JSON Schema |
| `--nats` / `--subject` | Publish to NATS |
| `--seed` | Reproducible RNG seed |
