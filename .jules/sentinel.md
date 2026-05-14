## 2024-05-24 - [Fix Dynamic SQL and Hardcoded Secrets]
**Vulnerability:** Dynamic SQL used `string.join` instead of parameterized `psycopg2.sql` components. Default hardcoded `SECRET_KEY`, `JWT_SECRET_KEY` and `ENCRYPTION_KEY` fallback without checking if in production.
**Learning:** `psycopg2.sql.SQL` should be used to protect table schema references from injection. Flask production configurations should raise `ValueError` if important secrets are missing rather than falling back on insecure default strings.
**Prevention:** Use `psycopg2.sql` for query generation with dynamic table/column references. Assert environments variables with fallbacks do not pass without warnings or errors in production environments.
