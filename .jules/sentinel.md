## 2025-02-12 - Defense-in-Depth: Adding Security Headers
**Vulnerability:** The application was missing standard security headers (e.g., X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security), leaving it vulnerable to minor classes of attacks like MIME-sniffing and clickjacking.
**Learning:** Even if a backend is primarily acting as an API, it is best practice to inject baseline security headers into every response.
**Prevention:** Added a global `@app.after_request` handler in `backend/api/__init__.py` to automatically append security headers to all responses.
