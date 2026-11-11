from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import os

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import TokenVerifier
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url


def test_production_verifier_uses_configured_signing_key_and_claims(settings):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    config=replace(settings,dev_auth=False,issuer="https://identity.example.test",jwks_url="https://identity.example.test/keys")
    config.validate()
    verifier=TokenVerifier(config)
    verifier.jwks=SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key()))
    now=datetime.now(timezone.utc)
    claims={"sub":"user-1","iss":config.issuer,"aud":config.audience,"iat":now,"exp":now+timedelta(minutes=5),"email":"user@example.test","email_verified":True}
    token=jwt.encode(claims,key,algorithm="RS256",headers={"kid":"provider-key"})
    assert verifier.verify(token).email=="user@example.test"
    foreign=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    with pytest.raises(HTTPException) as error:
        verifier.verify(jwt.encode(claims,foreign,algorithm="RS256"))
    assert error.value.status_code==401
    with pytest.raises(HTTPException):
        verifier.verify(jwt.encode(claims,"attacker-secret"*4,algorithm="HS256"))


def test_startup_rejects_privileged_database_identity(settings):
    # Only the dedicated synthetic database is used, even for the failure check.
    url=make_url(settings.database_url).set(username="postgres",password=os.getenv("TEST_ADMIN_PASSWORD"))
    app=create_app(replace(settings,database_url=url.render_as_string(hide_password=False)))
    try:
        with pytest.raises(RuntimeError,match="Unsafe database identity"):
            with TestClient(app):
                pass
    finally:
        app.state.factory.kw["bind"].dispose()
