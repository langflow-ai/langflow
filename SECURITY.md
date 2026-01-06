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

### Server-Side Request Forgery (SSRF) in API Request Component (Fixed in 1.7.1)

Langflow's [API Request component](https://docs.langflow.org/api-request) allows arbitrary HTTP requests within a flow. In versions < 1.7.1, this component did not block private IP ranges (`127.0.0.1`, `10/172/192` ranges) or cloud metadata endpoints (`169.254.169.254`), enabling Server-Side Request Forgery (SSRF) attacks.

**Potential security impact:**
- Attackers with API key access can access internal administrative endpoints, metadata services, and internal databases/services
- Foothold for attacking internal services by abusing inter-service trust
- Non-blind SSRF: Response bodies are returned to the client, enabling immediate data exfiltration

**CVE**: [CVE-2025-68477](https://nvd.nist.gov/vuln/detail/CVE-2025-68477)
**GitHub Advisory**: [GHSA-5993-7p27-66g5](https://github.com/langflow-ai/langflow/security/advisories/GHSA-5993-7p27-66g5)
**Fixed in**: Langflow >= 1.7.1

### External Control of File Name or Path (Fixed in 1.7.1)

When creating a flow through the [`/api/v1/flows/`](https://docs.langflow.org/api-flows) endpoint, if an arbitrary path is specified in the request body's `fs_path`, the server serializes the flow object into JSON and creates/overwrites a file at that path. In versions < 1.7.1, there is no path restriction, normalization, or allowed directory enforcement, so absolute paths (e.g., `/etc/poc.txt`) are interpreted as-is.

**Potential security impact:**
- Authenticated arbitrary file write (within server permission scope): Risk of corrupting configuration/log/task files, disrupting application behavior, and tampering with files read by other components
- Both absolute and relative paths are allowed, enabling base directory traversal
- Risk of overwriting system files increases in environments with root privileges or weak mount/permission settings
- File content is limited to Flow JSON, but impact is severe if the target file is parsed by a JSON parser or subject to subsequent processing

**CVE**: [CVE-2025-68478](https://nvd.nist.gov/vuln/detail/CVE-2025-68478)
**GitHub Advisory**: [GHSA-f43r-cc68-gpx4](https://github.com/langflow-ai/langflow/security/advisories/GHSA-f43r-cc68-gpx4)
**Fixed in**: Langflow >= 1.7.1

### Environment Variable Loading Bug (Fixed in 1.6.4)

Langflow versions `1.6.0` through `1.6.3` have a critical bug where environment variables from `.env` files are not being read. This affects all deployments using environment variables for configuration, including security settings.

**Potential security impact:**
- Environment variables from `.env` files are not read.
- Security configurations like `AUTO_LOGIN=false` may not be applied, potentially allowing users to log in as the default superuser.
- Database credentials, API keys, and other sensitive configuration may not be loaded.

**DO NOT** upgrade to Langflow versions `1.6.0` through `1.6.3` if you use `.env` files for configuration. Instead, upgrade to version `1.6.4`, which includes a fix for this bug.

**Fixed in**: Langflow >= 1.6.4

### Code Execution Vulnerability (Fixed in 1.3.0)

Langflow allows users to define and run **custom code components** through endpoints like `/api/v1/validate/code`. In versions < 1.3.0, this endpoint did not enforce authentication or proper sandboxing, allowing **unauthenticated arbitrary code execution**.

This means an attacker could send malicious code to the endpoint and have it executed on the server—leading to full system compromise, including data theft, remote shell access, or lateral movement within the network.

**CVE**: [CVE-2025-3248](https://nvd.nist.gov/vuln/detail/CVE-2025-3248)
**Fixed in**: Langflow >= 1.3.0

### Privilege Escalation via CLI Superuser Creation (Fixed in 1.5.1)

A privilege escalation vulnerability exists in Langflow containers where an authenticated user with RCE access can invoke the internal CLI command `langflow superuser` to create a new administrative user. This results in full superuser access, even if the user initially registered through the UI as a regular (non-admin) account.

**CVE**: [CVE-2025-57760](https://github.com/langflow-ai/langflow/security/advisories/GHSA-4gv9-mp8m-592r)
**Fixed in**: Langflow >= 1.5.1

### No API key required if running Langflow with `LANGFLOW_AUTO_LOGIN=true` and `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true`

In Langflow versions earlier than 1.5, if `LANGFLOW_AUTO_LOGIN=true`, then Langflow automatically logs users in as a superuser without requiring authentication. In this case, API requests don't require a Langflow API key.

In Langflow version 1.5, a Langflow API key is required to authenticate requests.
Setting `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true` and `LANGFLOW_AUTO_LOGIN=true` skips authentication for API requests. However, the `LANGFLOW_SKIP_AUTH_AUTO_LOGIN` option will be removed in v1.6.

`LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true` is the default behavior, so users do not need to change existing workflows in 1.5. To update your workflows to require authentication, set `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=false`.

For more information, see [API keys and authentication](https://docs.langflow.org/api-keys-and-authentication).

## Security Configuration Guidelines

### Superuser Creation Security

The `langflow superuser` CLI command can present a privilege escalation risk if not properly secured.

#### Security Measures

1. **Authentication Required in Production**
   - When `LANGFLOW_AUTO_LOGIN=false`, superuser creation requires authentication
   - Use `--auth-token` parameter with a valid superuser API key or JWT token

2. **Disable CLI Superuser Creation**
   - Set `LANGFLOW_ENABLE_SUPERUSER_CLI=false` to disable the command entirely
   - Strongly recommended for production environments

3. **Secure AUTO_LOGIN Setting**
   - Default is `true` for <=1.5. This may change in a future release.
   - When `true`, creates default superuser `langflow/langflow` - **ONLY USE IN DEVELOPMENT**

#### Production Security Configuration

```bash
# Recommended production settings
export LANGFLOW_AUTO_LOGIN=false
export LANGFLOW_ENABLE_SUPERUSER_CLI=false
export LANGFLOW_SUPERUSER="<your-superuser-username>"
export LANGFLOW_SUPERUSER_PASSWORD="<your-superuser-password>"
export LANGFLOW_DATABASE_URL="<your-production-database-url>" # e.g. "postgresql+psycopg://langflow:secure_pass@db.internal:5432/langflow"
export LANGFLOW_SECRET_KEY="your-strong-random-secret-key"
```