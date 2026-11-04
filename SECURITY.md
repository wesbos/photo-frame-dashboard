# Security

Read [Frame security](docs/security.md) before network access or adding private photos, accounts
or dashboard credentials. Device reports describe tested units; they do not certify other
firmware or promise vendor security support.

## Reporting vulnerabilities

For a vulnerability in this repository's scripts, kiosk or dashboard, use GitHub's
**Security → Advisories → Report a vulnerability** if available. Otherwise, ask the maintainers
for a private security contact without posting exploit details or secrets. A `SECURITY.md` file
does not enable private reporting; see [GitHub's instructions](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

Report vendor-firmware issues through the vendor's security channel where available. Link
publicly disclosed findings from the device report and [known-risk index](docs/security.md#known-risks-and-advisories).
Keep vendor issues distinct from this project's software; do not invent CVEs, affected-version
ranges or malware classifications.

Include the component/version, expected and observed behavior, minimal reproducer, impact and
tested mitigation. Redact identifiers, account details and credentials. Keep firmware dumps,
vendor binaries and personal photos out of public issues and PRs.
