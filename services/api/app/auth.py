from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import jwt
from fastapi import HTTPException


@dataclass(frozen=True)
class Identity:
    id: str
    email: str
    name: str


class TokenVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.jwks = None if settings.dev_auth else jwt.PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=300, timeout=5)

    def verify(self, token):
        s = self.settings
        try:
            if s.dev_auth:
                key, algorithms, issuer = s.dev_secret, ["HS256"], "constructpm-development"
            else:
                key = self.jwks.get_signing_key_from_jwt(token).key
                algorithms, issuer = ["RS256"], s.issuer
            claims = jwt.decode(token, key, algorithms=algorithms, audience=s.audience, issuer=issuer,
                                options={"require": ["exp", "iat", "sub", "iss", "aud", "email"]})
            if claims.get("email_verified") is not True or not isinstance(claims["sub"], str):
                raise ValueError("Verified email required")
            email = claims["email"].strip().lower()
            if not email or len(email) > 320 or "@" not in email:
                raise ValueError("Invalid email claim")
            return Identity(str(uuid5(NAMESPACE_URL, issuer + "|" + claims["sub"])), email, str(claims.get("name", email))[:160])
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(401, "Invalid or expired identity token", headers={"WWW-Authenticate": "Bearer"})

    def development_token(self, email):
        s = self.settings
        if not s.dev_auth or email not in s.dev_emails:
            raise HTTPException(404, "Local test identity is unavailable")
        now = datetime.now(timezone.utc)
        return jwt.encode({"sub": email, "email": email, "email_verified": True, "name": email.split("@")[0],
                           "iss": "constructpm-development", "aud": s.audience, "iat": now, "exp": now + timedelta(minutes=30)}, s.dev_secret, algorithm="HS256")

