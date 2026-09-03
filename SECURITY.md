# Security Policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private
addresses, or logs. Use GitHub's private vulnerability-reporting feature for
this repository. If private reporting is unavailable, open a minimal issue
asking the maintainer to establish a private channel; omit technical details.

Include the affected version/commit, prerequisites, impact, a minimal
reproduction, and suggested remediation. Remove tokens, API keys, cookies,
and SmartHub account credentials.

## Response targets

These are project targets, not an SLA: acknowledge critical/high reports in
three business days, establish severity and containment in seven, and publish
a coordinated fix/advisory as soon as safely validated. Lower-severity issues
are prioritized by exploitability and impact.

## Supported version

Only the latest published release and the default branch receive security
fixes.

## Security boundaries

HA Electric Usage Downloader is a normal Home Assistant integration, not a
sandbox. It stores the configured SmartHub username and password in the
config entry, encrypted at rest the same way Home Assistant encrypts every
other config entry, and it has no additional protection against a malicious
integration running in the same Python process.

The login and usage URLs are user-configurable so the integration can work
against any SmartHub-based cooperative portal, not just Bluebonnet's. The
integration does not verify that a configured URL belongs to a legitimate
SmartHub deployment before posting the username and password to it; entering
an untrusted URL sends those credentials to that URL's server. Use only URLs
you obtained directly from your electric cooperative.
