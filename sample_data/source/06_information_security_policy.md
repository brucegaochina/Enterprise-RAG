# Information Security Policy

Document ID: HD-SEC-001. Policy owner: Chief Information Security Officer. Version 4.0, approved January 15, 2026.

## Scope

This policy applies to all employees, contractors, and third parties who access Helios Dynamics systems or data, on any device and from any location.

## Passwords and Authentication

Passwords must be at least 14 characters long and must not be reused across systems. Use the company password manager, 1Password, to generate and store passwords. Passwords are not rotated on a schedule, but must be changed immediately if a compromise is suspected.

Multi-factor authentication (MFA) is mandatory for every company application. Approved MFA methods are Okta Verify push notifications and YubiKey hardware keys. SMS codes are not an approved MFA method. Administrators of production systems must use a YubiKey.

## Data Classification

| Classification | Examples | Handling requirements |
| Public | Marketing website, press releases | No restrictions |
| Internal | Org charts, internal wiki, policies | Share only with employees and contractors |
| Confidential | Customer contracts, source code, financial forecasts | Need-to-know access, encrypted in transit and at rest |
| Restricted | Customer telemetry data, employee health and payroll data, encryption keys | Named access only, approved systems only, access logged |

When in doubt, treat data as Confidential.

## Encryption

All company laptops must use full-disk encryption: FileVault on macOS and BitLocker on Windows. Data at rest in production systems must be encrypted with AES-256. Data in transit must use TLS 1.2 or higher.

## Devices

- Screens must lock automatically after 5 minutes of inactivity.
- Operating system and browser updates must be installed within 14 days of release. Critical security patches must be installed within 72 hours.
- USB mass storage devices are blocked on company laptops.
- Only devices enrolled in Jamf (macOS) or Intune (Windows) may access company systems.

## Access Management

Access is granted according to least privilege. Managers must review their team's access every quarter in the Access Review tool. Access for departing employees is revoked within 4 hours of their last working day.

## Security Awareness

Every employee must complete security awareness training within 30 days of joining and annually afterward. The Security team runs monthly phishing simulations. Employees who click on two simulations in a quarter must complete additional training.

## Reporting Security Incidents

Suspected security incidents, including lost devices, phishing emails, and accidental data disclosure, must be reported within 1 hour to security@heliosdynamics.example or in the #sec-incidents Slack channel. Incidents are handled according to the Security Incident Response Runbook, RB-SEC-007.

## Exceptions and Violations

Exceptions to this policy must be approved in writing by the CISO and are valid for a maximum of 12 months. Violations may lead to disciplinary action up to and including termination.
