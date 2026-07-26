# SIEM and audit forwarding

UPUB emits two structured streams:

- Caddy JSON access logs for TLS-edge requests.
- `audit.jsonl` for API route, status, and rejected-key events.

The production host should collect both with the organization-approved agent
(Vector, Fluent Bit, Filebeat, or equivalent), add a host/service/environment
field, encrypt transport, and forward to the central SIEM. The agent must be
configured with a durable local queue and back-pressure policy so a temporary
SIEM outage does not silently discard events.

Minimum event fields:

| Field | Requirement |
|---|---|
| timestamp | UTC, synchronized host clock |
| service | `upub-api`, `upub-edge`, or `orthanc` |
| environment | `research`, `staging`, or approved production name |
| actor | Verified enterprise subject or service identity; never an API key |
| action | HTTP method and normalized route |
| outcome | Status code and allow/deny decision |
| correlation_id | Shared across edge, API, worker, and DICOMweb logs |

Do not forward request bodies, DICOM pixels, patient names, access tokens, API
keys, or raw query strings. Define retention with the data-protection owner;
the repository’s default local log is not a regulated records system.
