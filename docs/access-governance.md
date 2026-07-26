# Access governance record

This is the review template to complete before real clinical data is allowed.

| Control | Owner | Evidence | Review cadence |
|---|---|---|---|
| OIDC application and redirect URIs | Identity team | Provider configuration export | On change |
| Group-to-role mapping | Data steward + security | Approved RBAC matrix | Quarterly |
| API/Orthanc secret rotation | Platform team | Secret-manager rotation log | At least quarterly |
| Certificate issuance and renewal | Platform team | CA inventory and alert test | Monthly |
| SIEM delivery and alerting | Security operations | Ingestion/query test | Monthly |
| Dataset provenance and license | Research lead | Dataset approval record | Per dataset |
| Artifact retention/deletion | Data-protection owner | Deletion evidence | Per policy |
| Vulnerability and image scan | Platform security | Signed scan report | Per release |
| Clinical/privacy review | Institutional review owner | Signed approval or exemption | Before clinical use |

The release owner must record the deployment name, data classification,
approved users/groups, retention period, incident contact, rollback plan, and
date of next review. A local Compose startup is not evidence that these
controls have been approved.
