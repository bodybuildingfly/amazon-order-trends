## 2024-05-24 - [Fix Dynamic SQL and Hardcoded Secrets]
**Vulnerability:** Dynamic SQL used `string.join` instead of parameterized `psycopg2.sql` components. Default hardcoded `SECRET_KEY`, `JWT_SECRET_KEY` and `ENCRYPTION_KEY` fallback without checking if in production.
**Learning:** `psycopg2.sql.SQL` should be used to protect table schema references from injection. Flask production configurations should raise `ValueError` if important secrets are missing rather than falling back on insecure default strings.
**Prevention:** Use `psycopg2.sql` for query generation with dynamic table/column references. Assert environments variables with fallbacks do not pass without warnings or errors in production environments.
## 2024-05-24 - [Fix Server-Side Request Forgery vulnerabilities (SSRF)]
**Vulnerability:** Several endpoints like /api/settings/test-webhook and /api/tracked-items allowed unsanitized user-provided URLs to be used for server-side outbound HTTP requests.
**Learning:** URL parameters intended for webhooks or external data scraping must be strictly validated against allowlists, especially when using requests.post or requests.get.
**Prevention:** Implement validation helpers using libraries like urllib.parse and enforcing strict domain and scheme checks.
## 2026-06-03 - [Fix SSRF vulnerability in webhook validation]
**Vulnerability:** The discord webhook URL was validated using `startswith` instead of parsing the URL, which could lead to SSRF bypasses via maliciously crafted URLs.
**Learning:** URL validation with simple string prefixes can be bypassed and relies on fragile conditions. Using `urllib.parse` to check the `scheme`, `netloc`, and `path` is a much safer approach.
**Prevention:** Always use a proper URL parsing library to validate URLs before making server-side requests.
