"""Password hashing and password rules.

Stored formats (both verify):
  current: pbkdf2_sha256$<iterations>$<salt>$<hex digest>   e.g. pbkdf2_sha256$600000$…$…
  legacy:  pbkdf2_sha256$<salt>$<hex digest>                 (seed users; 120,000 iterations)

PBKDF2-HMAC-SHA256 with a random per-user salt (used as UTF-8 text, matching the seed).
New hashes use 600,000 iterations (OWASP's current guidance). Because the iteration count is
stored in the hash, it can be raised later; needs_rehash() tells login to upgrade old hashes.
"""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128  # long inputs make PBKDF2 slower; no real password needs more

# Small blocklist of the most-used passwords (plus shop-specific guesses).
COMMON_PASSWORDS = {
    "password", "password1", "password12", "password123", "password1234", "passw0rd",
    "123456", "1234567", "12345678", "123456789", "1234567890", "qwerty", "qwerty123",
    "qwertyuiop", "abc123", "abcd1234", "111111", "000000", "iloveyou", "letmein",
    "welcome", "welcome1", "welcome123", "admin", "admin123", "monkey", "dragon",
    "football", "baseball", "sunshine", "princess", "trustno1", "superman", "starwars",
    "yale", "yale1701", "yaleuniversity", "bulldog", "bulldogs", "gobulldogs", "boolaboola",
    "handsomedan", "campuscustoms", "newhaven",
}


def _digest(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_digest(password, salt, ITERATIONS)}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 3 and parts[0] == ALGORITHM:
        return LEGACY_ITERATIONS, parts[1], parts[2]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored)
    if parsed is None or len(password) > MAX_PASSWORD_LENGTH:
        return False
    iterations, salt, expected = parsed
    # Constant-time comparison so response timing doesn't leak how much matched.
    return hmac.compare_digest(_digest(password, salt, iterations), expected)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or parsed[0] < ITERATIONS


def password_problem(password: str, email: str = "", first: str = "", last: str = "") -> str | None:
    """Returns a message the shopper can act on, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or lowered.rstrip("0123456789!") in COMMON_PASSWORDS:
        return "That password is too common. Please choose something harder to guess."
    if len(set(password)) < 4:
        return "Password is too repetitive. Please mix in more characters."
    local = email.split("@")[0].lower()
    for part in (email.lower(), local, first.lower(), last.lower()):
        if part and len(part) >= 3 and part in lowered:
            return "Password can't contain your name or email."
    return None


# Checked against when the email is unknown, so a login for a missing account
# takes as long as one with a wrong password (no account enumeration by timing).
DUMMY_HASH = hash_password(secrets.token_hex(16))
