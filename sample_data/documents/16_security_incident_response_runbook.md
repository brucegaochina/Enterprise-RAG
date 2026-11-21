# Security Incident Response Runbook

Document ID: RB-SEC-007. Owner: Security Operations. Version 3.1.

## Purpose

This runbook describes how Helios Dynamics detects, responds to, and learns from security incidents. It is used by the Security Operations Center (SOC) and anyone who is paged for an incident.

## Severity Levels

| Severity | Definition | Response time | Example |
| SEV1 | Confirmed breach of Restricted data or full outage of Helios Cloud | 15 minutes, 24/7 | Ransomware on production servers |
| SEV2 | Likely compromise or major degradation of a customer-facing service | 30 minutes, 24/7 | Compromised administrator account |
| SEV3 | Limited impact, contained to one system or user | 4 hours, business hours | Malware on a single laptop |
| SEV4 | Low risk, suspicious activity to investigate | 2 business days | Phishing email reported, not clicked |

## Roles

- Incident Commander (IC): leads the response, makes decisions, and assigns tasks. The on-call Security lead is the IC by default.
- Communications Lead: manages updates to executives, employees, and customers.
- Scribe: keeps a timeline of all actions and decisions in the incident document.
- Subject matter experts: engineers who own the affected systems.

## Response Steps

1. Detect and report: alerts come from the SIEM, employees, or customers. Anyone can declare an incident with the /incident command in Slack.
2. Triage: the IC assigns a severity within 15 minutes and opens a Slack channel named inc-YYYYMMDD-short-name.
3. Contain: isolate affected hosts, disable compromised accounts, and block malicious indicators.
4. Eradicate: remove the root cause, such as malware or a vulnerable configuration.
5. Recover: restore systems from clean backups and monitor closely for 72 hours.
6. Post-incident review: a blameless postmortem must be completed within 5 business days for SEV1 and SEV2 incidents.

## Escalation and Paging

The on-call rotation is managed in PagerDuty under the service Security-SOC. SEV1 incidents page the CISO and the VP of Engineering immediately. If the primary on-call does not acknowledge a page within 10 minutes, PagerDuty escalates to the secondary on-call.

## Customer and Regulator Notification

If customer data is affected, Legal and the Communications Lead decide on notification. Contracts require Helios to notify affected customers within 72 hours of confirming a breach of their data. Regulator notification follows the Data Retention and Privacy Policy, HD-PRIV-002.

## Evidence Handling

Preserve evidence before making changes when possible: capture memory and disk images, export logs, and record hashes. Store evidence in the restricted Incident Evidence bucket, which has a 3-year retention period.
