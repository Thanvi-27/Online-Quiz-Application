"""
BACKEND LAYER  -  backend/security.py

Password hashing. Passwords are never stored as plain text: each one is salted and
hashed with PBKDF2-SHA256 and stored as "salt$hash".
"""
import hashlib
import secrets


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)
