## 2024-05-18 - [Add rate limiting to login endpoint]
**Vulnerability:** Missing rate limiting on sensitive login endpoints allows brute-force attacks against user authentication.
**Learning:** The application lacked any rate limiting logic. It was necessary to add Flask-Limiter. The `backend/api/extensions.py` and `__init__.py` provide a clean way to load global Flask extensions like Limiter before applying them to blueprints like auth.py.
**Prevention:** Always implement rate limiting on authentication routes by default to establish basic protection against credential stuffing and brute-force attempts.
