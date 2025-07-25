# 🛡️ Langflow Security Policy & Responsible Disclosure

## Security Policy

This security policy applies to all public projects under the langflow-ai organization on GitHub. We prioritize security and continuously work to safeguard our systems. However, vulnerabilities can still exist. If you identify a security issue, please report it to us so we can address it promptly.

### Security/Bugfix Versions

- Fixes are released either as part of the next minor version (e.g., 1.3.0 → 1.4.0) or as an on-demand patch version (e.g., 1.3.0 → 1.3.1)
- Security fixes are given priority and might be enough to cause a new version to be released

## Reporting a Vulnerability

We encourage responsible disclosure of security vulnerabilities. If you find something suspicious, we encourage and appreciate your report!

### How to Report

Use the "Report a vulnerability" button under the "Security" tab of the [Langflow GitHub repository](https://github.com/langflow-ai/langflow/security). This creates a private communication channel between you and the maintainers.

### Reporting Guidelines

- Provide clear details to help us reproduce and fix the issue quickly
- Include steps to reproduce, potential impact, and any suggested fixes
- Your report will be kept confidential, and your details will not be shared without your consent

### Response Timeline

- We will acknowledge your report within 5 business days
- We will provide an estimated resolution timeline
- We will keep you updated on our progress

### Disclosure Guidelines

- Do not publicly disclose vulnerabilities until we have assessed, resolved, and notified affected users
- If you plan to present your research (e.g., at a conference or in a blog), share a draft with us at least 30 days in advance for review
- Avoid including:
  - Data from any Langflow customer projects
  - Langflow user/customer information
  - Details about Langflow employees, contractors, or partners

We appreciate your efforts in helping us maintain a secure platform and look forward to working together to resolve any issues responsibly.

## Known Vulnerabilities

### Code Execution Vulnerability (Fixed in 1.3.0)

Langflow allows users to define and run **custom code components** through endpoints like `/api/v1/validate/code`. In versions < 1.3.0, this endpoint did not enforce authentication or proper sandboxing, allowing **unauthenticated arbitrary code execution**.

This means an attacker could send malicious code to the endpoint and have it executed on the server—leading to full system compromise, including data theft, remote shell access, or lateral movement within the network.

To address, upgrade to >= 1.3.0.

### No API key required if running Langflow with `LANGFLOW_AUTO_LOGIN=true` and `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true`

In Langflow versions earlier than 1.5, if `LANGFLOW_AUTO_LOGIN=true`, then Langflow automatically logs users in as a superuser without requiring authentication. In this case, API requests don't require a Langflow API key.

In Langflow version 1.5, a Langflow API key is required to authenticate requests.
Setting `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true` and `LANGFLOW_AUTO_LOGIN=true` skips authentication for API requests. However, the `LANGFLOW_SKIP_AUTH_AUTO_LOGIN` option will be removed in v1.6.

`LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true` is the default behavior, so users do not need to change existing workflows in 1.5. To update your workflows to require authentication, set `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=false`.

For more information, see [Authentication](https://docs.langflow.org/configuration-authentication).