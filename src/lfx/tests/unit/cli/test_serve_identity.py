"""Tests for per-user identity forwarding in ``lfx serve`` (verified JWT / header).

Crypto is exercised with locally generated RSA and EC P-256 keypairs and an
in-memory fake JWKS endpoint — no network. See ``lfx.cli.serve_identity``.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from lfx.cli.common import execute_graph_with_capture
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app, create_serve_app
from lfx.cli.serve_identity import (
    IdentityConfig,
    IdentityConfigError,
    IdentityVerifier,
    _fetch_json,
    build_identity_verifier,
)
from lfx.graph import Graph

ISSUER = "https://accounts.example.com"
AUDIENCE = "my-oauth-client-id"
KID = "test-key-1"
EC_KID = "test-key-ec"


# ---------------------------------------------------------------------------
# Crypto / JWKS test helpers (no network)
# ---------------------------------------------------------------------------


def _make_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_for(public_key, kid: str = KID) -> dict:
    """Build a JWKS document exposing an RSA ``public_key`` under ``kid``."""
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def _make_ec_keypair() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _ec_jwks_for(public_key, kid: str = EC_KID) -> dict:
    """Build a JWKS document exposing an EC P-256 ``public_key`` under ``kid``."""
    jwk = json.loads(ECAlgorithm.to_jwk(public_key))
    jwk.update({"kid": kid, "use": "sig", "alg": "ES256"})
    return {"keys": [jwk]}


def _sign(private_key, claims: dict, *, kid: str = KID, alg: str = "RS256") -> str:
    payload = {"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, private_key, algorithm=alg, headers={"kid": kid})


def _alg_none_token(claims: dict, *, kid: str = KID) -> str:
    """Hand-craft an ``alg: none`` token (unsigned)."""

    def b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    payload = {"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600, **claims}
    return f"{b64({'alg': 'none', 'typ': 'JWT', 'kid': kid})}.{b64(payload)}."


class _CountingFetcher:
    """A fake JWKS fetcher that counts calls and can be flipped to fail."""

    def __init__(self, jwks: dict) -> None:
        self.jwks = jwks
        self.calls = 0
        self.fail = False

    def __call__(self, _url: str) -> dict:
        self.calls += 1
        if self.fail:
            msg = "simulated JWKS endpoint down"
            raise OSError(msg)
        return self.jwks


@pytest.fixture
def keypair():
    return _make_keypair()


@pytest.fixture
def jwks(keypair):
    return _jwks_for(keypair.public_key())


@pytest.fixture
def fetcher(jwks):
    return _CountingFetcher(jwks)


@pytest.fixture
def jwt_config():
    # Explicit jwks_url avoids OIDC discovery so the fake fetcher serves the JWKS directly.
    return IdentityConfig(
        mode="jwt",
        jwt_issuer=ISSUER,
        jwt_audience=AUDIENCE,
        jwt_jwks_url="https://accounts.example.com/jwks",
        claim="email",
    )


@pytest.fixture
def verifier(jwt_config, fetcher):
    v = IdentityVerifier(jwt_config, jwks_fetcher=fetcher)
    v.prefetch()
    return v


# ---------------------------------------------------------------------------
# IdentityConfig
# ---------------------------------------------------------------------------


class TestIdentityConfig:
    def test_off_is_default_and_disabled(self):
        cfg = IdentityConfig()
        assert cfg.mode == "off"
        assert cfg.enabled is False
        assert cfg.to_env() == {"LFX_SERVE_IDENTITY_MODE": "off"}

    def test_jwt_requires_issuer_and_audience(self):
        with pytest.raises(IdentityConfigError):
            IdentityConfig(mode="jwt", jwt_audience=AUDIENCE)
        with pytest.raises(IdentityConfigError):
            IdentityConfig(mode="jwt", jwt_issuer=ISSUER)

    def test_unknown_mode_rejected(self):
        with pytest.raises(IdentityConfigError):
            IdentityConfig(mode="bogus")  # type: ignore[arg-type]

    def test_non_http_jwks_url_rejected_offline(self):
        # A bad scheme must fail fast at config construction, not at first fetch.
        with pytest.raises(IdentityConfigError):
            IdentityConfig(mode="jwt", jwt_issuer=ISSUER, jwt_audience=AUDIENCE, jwt_jwks_url="file:///etc/passwd")

    def test_http_jwks_url_rejected_by_default(self):
        # Plaintext http:// is MITM-able (forged JWKS), so HTTPS is required by default.
        with pytest.raises(IdentityConfigError):
            IdentityConfig(
                mode="jwt", jwt_issuer=ISSUER, jwt_audience=AUDIENCE, jwt_jwks_url="http://issuer.test/jwks.json"
            )

    def test_http_jwks_url_allowed_with_insecure_flag(self):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="http://issuer.test/jwks.json",
            allow_insecure_http=True,
        )
        assert cfg.jwt_jwks_url == "http://issuer.test/jwks.json"

    def test_http_issuer_for_discovery_rejected_by_default(self):
        # No explicit jwks_url → the issuer is fetched for OIDC discovery, so its
        # scheme is subject to the same HTTPS policy.
        with pytest.raises(IdentityConfigError):
            IdentityConfig(mode="jwt", jwt_issuer="http://accounts.example.com", jwt_audience=AUDIENCE, claim="email")

    def test_http_issuer_for_discovery_allowed_with_insecure_flag(self):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer="http://accounts.example.com",
            jwt_audience=AUDIENCE,
            claim="email",
            allow_insecure_http=True,
        )
        assert cfg.jwt_issuer == "http://accounts.example.com"

    def test_insecure_http_flag_still_rejects_non_http_schemes(self):
        # The escape hatch widens to http:// only — it must not re-open file://.
        with pytest.raises(IdentityConfigError):
            IdentityConfig(
                mode="jwt",
                jwt_issuer=ISSUER,
                jwt_audience=AUDIENCE,
                jwt_jwks_url="file:///etc/passwd",
                allow_insecure_http=True,
            )

    def test_allow_insecure_http_env_round_trip(self):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="http://issuer.test/jwks.json",
            claim="email",
            allow_insecure_http=True,
        )
        assert IdentityConfig.from_env(cfg.to_env()) == cfg

    def test_env_round_trip_preserves_all_fields(self):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="https://example.com/jwks",
            claim="email",
            jwt_header="X-Auth-Request-Access-Token",
            trusted_header="X-Consumer-Username",
        )
        assert IdentityConfig.from_env(cfg.to_env()) == cfg

    def test_env_round_trip_header_mode(self):
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        assert IdentityConfig.from_env(cfg.to_env()) == cfg

    def test_from_env_absent_is_off(self):
        assert IdentityConfig.from_env({}) == IdentityConfig(mode="off")


# ---------------------------------------------------------------------------
# IdentityVerifier — JWT mode
# ---------------------------------------------------------------------------


class TestIdentityVerifierJwt:
    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_valid_token_returns_identity_claim(self, verifier, keypair):
        token = _sign(keypair, {"email": "alice@example.com"})
        assert verifier.authenticate(self._headers(token)) == "alice@example.com"

    def test_missing_token_rejected(self, verifier):
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate({})
        assert exc.value.status_code == 401

    def test_bad_signature_rejected(self, verifier):
        other_key = _make_keypair()
        token = _sign(other_key, {"email": "mallory@example.com"})  # signed by wrong key, valid kid
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_wrong_issuer_rejected(self, verifier, keypair):
        token = jwt.encode(
            {"iss": "https://evil.example.com", "aud": AUDIENCE, "exp": int(time.time()) + 3600, "email": "a@b.c"},
            keypair,
            algorithm="RS256",
            headers={"kid": KID},
        )
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_wrong_audience_rejected(self, verifier, keypair):
        token = jwt.encode(
            {"iss": ISSUER, "aud": "some-other-client", "exp": int(time.time()) + 3600, "email": "a@b.c"},
            keypair,
            algorithm="RS256",
            headers={"kid": KID},
        )
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_expired_token_rejected(self, verifier, keypair):
        token = jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) - 3600, "email": "a@b.c"},
            keypair,
            algorithm="RS256",
            headers={"kid": KID},
        )
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_alg_none_rejected(self, verifier):
        token = _alg_none_token({"email": "a@b.c"})
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_hs256_alg_confusion_rejected(self, verifier, keypair):
        # Attacker signs with HMAC using the PUBLIC key bytes as the shared secret.
        # pyjwt refuses to use an asymmetric key for HMAC, so hand-craft the token.
        import hashlib
        import hmac

        from cryptography.hazmat.primitives import serialization

        public_pem = keypair.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        def b64(raw: bytes) -> str:
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
        payload = b64(
            json.dumps(
                {"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600, "email": "mallory@example.com"}
            ).encode()
        )
        signing_input = f"{header}.{payload}".encode()
        signature = b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())
        forged = f"{header}.{payload}.{signature}"

        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(forged))
        assert exc.value.status_code == 401

    def test_missing_claim_rejected(self, verifier, keypair):
        token = _sign(keypair, {"sub": "no-email-here"})  # claim is 'email'
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n "])
    def test_blank_claim_rejected(self, verifier, keypair, blank):
        # An empty or whitespace-only claim must not become a (blank) user_id.
        token = _sign(keypair, {"email": blank})
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401

    def test_missing_kid_rejected(self, verifier, keypair):
        # Token with no `kid` in its header — distinct from an unknown kid.
        token = jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600, "email": "a@b.c"},
            keypair,
            algorithm="RS256",  # no headers={"kid": ...}
        )
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401
        assert "key id" in exc.value.detail.lower()

    def test_unknown_kid_triggers_one_rate_limited_refresh_then_401(self, verifier, fetcher, keypair):
        assert fetcher.calls == 1  # prefetch
        token = _sign(keypair, {"email": "a@b.c"}, kid="rotated-kid-not-in-jwks")

        with pytest.raises(HTTPException) as exc:
            verifier.authenticate(self._headers(token))
        assert exc.value.status_code == 401
        assert fetcher.calls == 2  # one refresh attempt on the unknown kid

        # A second immediate unknown-kid request is rate-limited: no extra fetch.
        with pytest.raises(HTTPException):
            verifier.authenticate(self._headers(token))
        assert fetcher.calls == 2

    def test_cold_cache_fetch_is_rate_limited_during_outage(self, jwt_config, fetcher, keypair):
        # Prefetch fails and the issuer stays down: a flood of requests must NOT each
        # trigger its own (blocking) fetch — the cooldown floors bound it to a few.
        fetcher.fail = True
        v = IdentityVerifier(jwt_config, jwks_fetcher=fetcher)
        v.prefetch()  # fails; cache stays empty
        headers = self._headers(_sign(keypair, {"email": "a@b.c"}))

        for _ in range(10):
            with pytest.raises(HTTPException) as exc:
                v.authenticate(headers)
            assert exc.value.status_code == 401

        # 1 prefetch + at most one fetch per path before both cooldown floors engage.
        assert fetcher.calls <= 4

    def test_jwks_down_with_warm_cache_still_verifies(self, verifier, fetcher, keypair):
        assert fetcher.calls == 1
        fetcher.fail = True  # endpoint goes down
        token = _sign(keypair, {"email": "alice@example.com"})
        # Known kid is already cached → verifies without re-fetching.
        assert verifier.authenticate(self._headers(token)) == "alice@example.com"
        assert fetcher.calls == 1

    def test_custom_jwt_header_with_bearer_prefix(self, fetcher, keypair):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="https://accounts.example.com/jwks",
            claim="email",
            jwt_header="X-Auth-Request-Access-Token",
        )
        v = IdentityVerifier(cfg, jwks_fetcher=fetcher)
        v.prefetch()
        token = _sign(keypair, {"email": "alice@example.com"})
        assert v.authenticate({"X-Auth-Request-Access-Token": f"Bearer {token}"}) == "alice@example.com"
        # Raw token without Bearer prefix also accepted.
        assert v.authenticate({"X-Auth-Request-Access-Token": token}) == "alice@example.com"


# ---------------------------------------------------------------------------
# IdentityVerifier — ES256 (the second accepted algorithm)
# ---------------------------------------------------------------------------


class TestIdentityVerifierEs256:
    """ES256 (ECDSA P-256) is accepted alongside RS256; keys are matched by ``kid``."""

    def _verifier(self, jwks_doc: dict) -> IdentityVerifier:
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="https://accounts.example.com/jwks",
            claim="email",
        )
        v = IdentityVerifier(cfg, jwks_fetcher=lambda _u: jwks_doc)
        v.prefetch()
        return v

    def test_valid_es256_token_returns_identity_claim(self):
        ec_key = _make_ec_keypair()
        v = self._verifier(_ec_jwks_for(ec_key.public_key()))
        token = _sign(ec_key, {"email": "ec-alice@example.com"}, kid=EC_KID, alg="ES256")
        assert v.authenticate({"Authorization": f"Bearer {token}"}) == "ec-alice@example.com"

    def test_es256_bad_signature_rejected(self):
        ec_key = _make_ec_keypair()
        other = _make_ec_keypair()  # advertised key differs from the signer
        v = self._verifier(_ec_jwks_for(ec_key.public_key()))
        token = _sign(other, {"email": "mallory@example.com"}, kid=EC_KID, alg="ES256")
        with pytest.raises(HTTPException) as exc:
            v.authenticate({"Authorization": f"Bearer {token}"})
        assert exc.value.status_code == 401

    def test_es256_wrong_audience_rejected(self):
        ec_key = _make_ec_keypair()
        v = self._verifier(_ec_jwks_for(ec_key.public_key()))
        token = jwt.encode(
            {"iss": ISSUER, "aud": "some-other-client", "exp": int(time.time()) + 3600, "email": "a@b.c"},
            ec_key,
            algorithm="ES256",
            headers={"kid": EC_KID},
        )
        with pytest.raises(HTTPException) as exc:
            v.authenticate({"Authorization": f"Bearer {token}"})
        assert exc.value.status_code == 401

    def test_mixed_jwks_verifies_both_rs256_and_es256_by_kid(self):
        # A single JWKS carrying one RSA and one EC key; the verifier picks by kid.
        rsa_key = _make_keypair()
        ec_key = _make_ec_keypair()
        jwks_doc = {"keys": _jwks_for(rsa_key.public_key())["keys"] + _ec_jwks_for(ec_key.public_key())["keys"]}
        v = self._verifier(jwks_doc)
        rs_token = _sign(rsa_key, {"email": "rs@example.com"})  # RS256, kid=test-key-1
        es_token = _sign(ec_key, {"email": "es@example.com"}, kid=EC_KID, alg="ES256")
        assert v.authenticate({"Authorization": f"Bearer {rs_token}"}) == "rs@example.com"
        assert v.authenticate({"Authorization": f"Bearer {es_token}"}) == "es@example.com"


# ---------------------------------------------------------------------------
# Startup prefetch
# ---------------------------------------------------------------------------


class TestJwksSourceResolution:
    """OIDC discovery (when no explicit jwks_url) and the SSRF scheme guard."""

    def _disco_config(self):
        # No jwt_jwks_url → the verifier must discover it from the issuer.
        return IdentityConfig(mode="jwt", jwt_issuer=ISSUER, jwt_audience=AUDIENCE, claim="email")

    def test_oidc_discovery_resolves_jwks_uri_then_verifies(self, jwks, keypair):
        seen = {}

        def openid_fetch(url):
            seen["openid"] = url
            return {"jwks_uri": "https://accounts.example.com/discovered-jwks"}

        def jwks_fetch(url):
            seen["jwks"] = url
            return jwks

        v = IdentityVerifier(self._disco_config(), jwks_fetcher=jwks_fetch, openid_fetcher=openid_fetch)
        v.prefetch()
        token = _sign(keypair, {"email": "alice@example.com"})
        assert v.authenticate({"Authorization": f"Bearer {token}"}) == "alice@example.com"
        # Discovery hit the well-known doc, then fetched the URL it advertised.
        assert seen["openid"] == "https://accounts.example.com/.well-known/openid-configuration"
        assert seen["jwks"] == "https://accounts.example.com/discovered-jwks"

    def test_oidc_discovery_without_jwks_uri_degrades_to_401(self, keypair):
        # Discovery doc missing jwks_uri → IdentityConfigError, swallowed at fetch,
        # cache stays empty, prefetch does not raise, requests fail closed (401).
        v = IdentityVerifier(self._disco_config(), jwks_fetcher=lambda _u: {"keys": []}, openid_fetcher=lambda _u: {})
        v.prefetch()
        token = _sign(keypair, {"email": "a@b.c"})
        with pytest.raises(HTTPException) as exc:
            v.authenticate({"Authorization": f"Bearer {token}"})
        assert exc.value.status_code == 401

    def test_fetch_json_rejects_non_http_scheme(self):
        # The SSRF guard: a file:// (or other non-http) URL must be refused.
        with pytest.raises(IdentityConfigError):
            _fetch_json("file:///etc/passwd")

    def _assert_fails_closed(self, verifier, keypair):
        """A malformed external shape must not raise out of prefetch/auth — 401."""
        assert verifier.prefetch() is False  # empty cache, no AttributeError/500
        token = _sign(keypair, {"email": "a@b.c"})
        with pytest.raises(HTTPException) as exc:
            verifier.authenticate({"Authorization": f"Bearer {token}"})
        assert exc.value.status_code == 401

    def test_jwks_non_object_fails_closed(self, keypair):
        # A JWKS endpoint returning a JSON array (not an object) must fail closed,
        # not raise AttributeError out of PyJWKSet.from_dict.
        cfg = IdentityConfig(
            mode="jwt", jwt_issuer=ISSUER, jwt_audience=AUDIENCE, jwt_jwks_url="https://x/jwks", claim="email"
        )
        v = IdentityVerifier(cfg, jwks_fetcher=lambda _u: [])
        self._assert_fails_closed(v, keypair)

    def test_oidc_discovery_non_object_fails_closed(self, keypair):
        # Discovery doc that is a JSON array (no .get) must fail closed, not raise.
        v = IdentityVerifier(self._disco_config(), jwks_fetcher=lambda _u: {"keys": []}, openid_fetcher=lambda _u: [])
        self._assert_fails_closed(v, keypair)

    def test_oidc_discovery_non_string_jwks_uri_fails_closed(self, keypair):
        # jwks_uri present but not a string must fail closed, not slip through to
        # a later AttributeError when the non-string is fetched.
        v = IdentityVerifier(
            self._disco_config(),
            jwks_fetcher=lambda _u: {"keys": []},
            openid_fetcher=lambda _u: {"jwks_uri": 123},
        )
        self._assert_fails_closed(v, keypair)

    def test_oidc_discovery_http_jwks_uri_rejected_by_default(self, keypair):
        # A discovered jwks_uri over plaintext http:// is refused under the default
        # HTTPS policy (defense-in-depth even when the issuer itself was https).
        v = IdentityVerifier(
            self._disco_config(),
            jwks_fetcher=lambda _u: {"keys": []},
            openid_fetcher=lambda _u: {"jwks_uri": "http://accounts.example.com/jwks"},
        )
        self._assert_fails_closed(v, keypair)


class TestStartupPrefetch:
    def test_prefetch_fetches_before_first_request(self, jwt_config, fetcher, keypair):
        v = IdentityVerifier(jwt_config, jwks_fetcher=fetcher)
        assert fetcher.calls == 0
        assert v.prefetch() is True  # warm cache reported so callers can stay quiet
        assert fetcher.calls == 1  # JWKS fetched at startup, not on first request
        token = _sign(keypair, {"email": "alice@example.com"})
        assert v.authenticate({"Authorization": f"Bearer {token}"}) == "alice@example.com"
        assert fetcher.calls == 1  # first request paid no fetch round-trip

    def test_failed_prefetch_does_not_raise_and_recovers(self, jwt_config, fetcher, keypair):
        fetcher.fail = True
        v = IdentityVerifier(jwt_config, jwks_fetcher=fetcher)
        assert v.prefetch() is False  # empty cache reported so the caller can warn loudly
        assert fetcher.calls == 1

        fetcher.fail = False  # issuer recovers
        token = _sign(keypair, {"email": "alice@example.com"})
        # First real request re-fetches (cache was empty) and now succeeds.
        assert v.authenticate({"Authorization": f"Bearer {token}"}) == "alice@example.com"
        assert fetcher.calls == 2


# ---------------------------------------------------------------------------
# Header mode
# ---------------------------------------------------------------------------


class TestIdentityVerifierHeader:
    def test_reads_configured_header(self):
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        v = IdentityVerifier(cfg)
        assert v.authenticate({"X-Consumer-Username": "kong-user-7"}) == "kong-user-7"

    def test_missing_header_rejected(self):
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        v = IdentityVerifier(cfg)
        with pytest.raises(HTTPException) as exc:
            v.authenticate({})
        assert exc.value.status_code == 401

    def test_header_mode_emits_startup_warning(self):
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        registry = FlowRegistry()
        with patch("lfx.cli.serve_app.logger") as mock_logger:
            create_multi_serve_app(registry=registry, identity_config=cfg)
        assert mock_logger.warning.called
        warned = " ".join(str(c.args[0]) for c in mock_logger.warning.call_args_list)
        assert "X-Consumer-Username" in warned
        assert "topology" in warned.lower()

    def test_header_mode_warns_on_guaranteed_console_channel(self):
        # The structlog logger is not reliably surfaced on the serve stdout path, so the
        # header trust warning must also reach the operator via the stderr console.
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        registry = FlowRegistry()
        with patch("lfx.cli.serve_app._startup_console") as mock_console:
            create_multi_serve_app(registry=registry, identity_config=cfg)
        assert mock_console.print.called
        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "X-Consumer-Username" in printed


# ---------------------------------------------------------------------------
# Startup notices on the guaranteed (stderr console) channel
# ---------------------------------------------------------------------------


class TestStartupConsoleNotices:
    def _jwt_config(self):
        return IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="https://accounts.example.com/jwks.json",
            claim="email",
        )

    def test_failed_jwt_prefetch_warns_on_console(self):
        # A failed prefetch must not abort startup, but it must warn loudly on the
        # guaranteed channel so the operator knows every request will 401.
        stub = MagicMock()
        stub.prefetch.return_value = False
        with (
            patch("lfx.cli.serve_app.build_identity_verifier", return_value=stub),
            patch("lfx.cli.serve_app._startup_console") as mock_console,
        ):
            create_multi_serve_app(registry=FlowRegistry(), identity_config=self._jwt_config())
        assert stub.prefetch.called
        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "JWKS prefetch failed" in printed
        assert "401" in printed

    def test_successful_jwt_prefetch_is_quiet_on_console(self):
        stub = MagicMock()
        stub.prefetch.return_value = True
        with (
            patch("lfx.cli.serve_app.build_identity_verifier", return_value=stub),
            patch("lfx.cli.serve_app._startup_console") as mock_console,
        ):
            create_multi_serve_app(registry=FlowRegistry(), identity_config=self._jwt_config())
        assert stub.prefetch.called
        assert not mock_console.print.called


# ---------------------------------------------------------------------------
# Token never logged
# ---------------------------------------------------------------------------


class TestTokenNeverLogged:
    def test_token_absent_from_all_log_calls(self, jwt_config, fetcher, keypair):
        v = IdentityVerifier(jwt_config, jwks_fetcher=fetcher)
        v.prefetch()
        token = _sign(keypair, {"email": "alice@example.com"})
        headers = {"Authorization": f"Bearer {token}"}

        with patch("lfx.cli.serve_identity.logger") as mock_logger:
            v.authenticate(headers)  # success path
            with pytest.raises(HTTPException):
                v.authenticate({"Authorization": "Bearer not.a.jwt"})  # malformed
            fetcher.fail = True
            bad_kid = _sign(keypair, {"email": "a@b.c"}, kid="rotated")
            with pytest.raises(HTTPException):
                v.authenticate({"Authorization": f"Bearer {bad_kid}"})  # forces failing refresh + logging

        logged = " ".join(str(a) for call in mock_logger.mock_calls if call.args for a in call.args)
        assert token not in logged
        assert "not.a.jwt" not in logged


# ---------------------------------------------------------------------------
# Endpoint integration (run/stream + serve-key floor)
# ---------------------------------------------------------------------------

API_KEY = "test-api-key"  # pragma: allowlist secret
FLOW_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def real_graph():
    data_dir = Path(__file__).parent.parent.parent / "data"
    with (data_dir / "simple_chat_no_llm.json").open() as f:
        payload = json.load(f)
    return Graph.from_payload(payload, flow_id=FLOW_ID)


@pytest.fixture(autouse=True)
def _allow_custom_components(monkeypatch):
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)


def _client_with_verifier(real_graph, verifier_obj) -> TestClient:
    """Build a serve app (off mode) and swap in a test verifier on app.state."""
    registry = FlowRegistry()
    registry.add(real_graph, FlowMeta(id=FLOW_ID, relative_path="t.json", title="t", description=None))
    app = create_multi_serve_app(registry=registry)
    app.state.identity_verifier = verifier_obj  # None ⇒ off
    return TestClient(app)


class TestServeCli:
    """The identity options are reachable through the real ``lfx serve`` CLI."""

    def test_serve_help_lists_identity_options(self):
        from lfx.__main__ import app
        from typer.testing import CliRunner

        # Force a wide terminal so rich does not wrap long option names across lines.
        with patch.dict(os.environ, {"COLUMNS": "200"}):
            result = CliRunner().invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        # Strip ANSI styling: rich colorizes each hyphen-segment of an option name
        # (``-``/``-identity``/``-mode``), so the raw output never holds the literal
        # ``--identity-mode`` substring when color is forced (as it is in CI).
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "--identity-mode" in plain
        assert "--identity-jwt-issuer" in plain

    def test_jwt_mode_without_issuer_fails_fast(self):
        from lfx.__main__ import app
        from typer.testing import CliRunner

        env = {k: v for k, v in os.environ.items() if not k.startswith("LFX_SERVE_")}
        env["LANGFLOW_API_KEY"] = API_KEY
        with patch.dict(os.environ, env, clear=True):
            result = CliRunner().invoke(app, ["serve", "--identity-mode", "jwt"])
        assert result.exit_code != 0
        assert "identity-jwt-issuer" in result.output


class TestWorkerEnvRoundTrip:
    """Identity config must survive the env-var round-trip into uvicorn workers."""

    def _clean_serve_env(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if not k.startswith("LFX_SERVE_")}

    def test_header_mode_round_trips_through_create_serve_app(self):
        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        env = {**self._clean_serve_env(), "LANGFLOW_API_KEY": API_KEY, **cfg.to_env()}
        with patch.dict(os.environ, env, clear=True):
            app = create_serve_app()
        assert app.state.identity_config == cfg
        assert app.state.identity_verifier is not None

    def test_jwt_mode_round_trips_through_create_serve_app(self, jwks):
        cfg = IdentityConfig(
            mode="jwt",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_jwks_url="https://accounts.example.com/jwks",
            claim="email",
            jwt_header="X-Auth-Request-Access-Token",
        )
        env = {**self._clean_serve_env(), "LANGFLOW_API_KEY": API_KEY, **cfg.to_env()}
        # Patch the network fetcher so the worker's startup prefetch stays offline.
        with (
            patch.dict(os.environ, env, clear=True),
            patch("lfx.cli.serve_identity._fetch_json", return_value=jwks),
        ):
            app = create_serve_app()
        # Every field reconstructed identically in the worker.
        assert app.state.identity_config == cfg
        assert app.state.identity_verifier is not None


class TestServeAppIdentityEndpoints:
    def test_off_mode_requires_no_identity_and_threads_none(self, real_graph):
        captured: dict = {}

        async def mock_execute(graph, input_value, session_id=None, user_id=None):  # noqa: ARG001
            captured["user_id"] = user_id
            return [], ""

        client = _client_with_verifier(real_graph, None)
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute),
        ):
            resp = client.post(f"/flows/{FLOW_ID}/run", json={"input_value": "hi"}, headers={"x-api-key": API_KEY})
        assert resp.status_code != 401
        assert captured["user_id"] is None  # off mode ⇒ no identity threaded

    def test_jwt_valid_token_threads_identity_into_run(self, real_graph, verifier, keypair):
        captured: dict = {}

        async def mock_execute(graph, input_value, session_id=None, user_id=None):  # noqa: ARG001
            captured["user_id"] = user_id
            return [], ""

        token = _sign(keypair, {"email": "alice@example.com"})
        client = _client_with_verifier(real_graph, verifier)
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute),
        ):
            resp = client.post(
                f"/flows/{FLOW_ID}/run",
                json={"input_value": "hi"},
                headers={"x-api-key": API_KEY, "Authorization": f"Bearer {token}"},
            )
        assert resp.status_code != 401
        assert captured["user_id"] == "alice@example.com"

    def test_jwt_valid_token_threads_identity_into_stream(self, real_graph, verifier, keypair):
        captured: dict = {}

        async def mock_execute(graph, input_value, session_id=None, user_id=None):  # noqa: ARG001
            captured["user_id"] = user_id
            return [], ""

        token = _sign(keypair, {"email": "bob@example.com"})
        client = _client_with_verifier(real_graph, verifier)
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute),
            client.stream(
                "POST",
                f"/flows/{FLOW_ID}/stream",
                json={"input_value": "hi"},
                headers={"x-api-key": API_KEY, "Authorization": f"Bearer {token}"},
            ) as resp,
        ):
            assert resp.status_code == 200
            for _ in resp.iter_bytes():
                pass
        assert captured["user_id"] == "bob@example.com"

    def test_jwt_invalid_token_rejected_before_execution(self, real_graph, verifier):
        execute = MagicMock()
        client = _client_with_verifier(real_graph, verifier)
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", execute),
        ):
            resp = client.post(
                f"/flows/{FLOW_ID}/run",
                json={"input_value": "hi"},
                headers={"x-api-key": API_KEY, "Authorization": "Bearer garbage.token.here"},
            )
        assert resp.status_code == 401
        execute.assert_not_called()

    def test_serve_key_floor_enforced_even_with_valid_token(self, real_graph, verifier, keypair):
        """A valid identity token must NOT bypass the serve API key."""
        execute = MagicMock()
        token = _sign(keypair, {"email": "alice@example.com"})
        client = _client_with_verifier(real_graph, verifier)
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", execute),
        ):
            resp = client.post(
                f"/flows/{FLOW_ID}/run",
                json={"input_value": "hi"},
                headers={"Authorization": f"Bearer {token}"},  # no x-api-key
            )
        assert resp.status_code == 401
        execute.assert_not_called()

    def test_header_mode_threads_identity(self, real_graph):
        captured: dict = {}

        async def mock_execute(graph, input_value, session_id=None, user_id=None):  # noqa: ARG001
            captured["user_id"] = user_id
            return [], ""

        cfg = IdentityConfig(mode="header", trusted_header="X-Consumer-Username")
        client = _client_with_verifier(real_graph, build_identity_verifier(cfg))
        with (
            patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}),
            patch("lfx.cli.serve_app.execute_graph_with_capture", mock_execute),
        ):
            resp = client.post(
                f"/flows/{FLOW_ID}/run",
                json={"input_value": "hi"},
                headers={"x-api-key": API_KEY, "X-Consumer-Username": "kong-user-7"},
            )
        assert resp.status_code != 401
        assert captured["user_id"] == "kong-user-7"


class TestExecuteGraphUserIdThreading:
    """The user_id contract in execute_graph_with_capture.

    Covers the off-mode preservation the docstrings describe: None keeps the
    graph's existing user_id, a verified value overwrites it. async_start is
    stubbed so only the apply_run_defaults stamping logic runs, not a full flow.
    """

    @staticmethod
    def _stub_async_start(real_graph):
        async def _no_results(*_args, **_kwargs):
            return
            yield  # make it an (empty) async generator

        real_graph.async_start = _no_results

    async def test_none_user_id_preserves_existing_graph_user_id(self, real_graph):
        self._stub_async_start(real_graph)
        real_graph.user_id = "preexisting-user"
        await execute_graph_with_capture(real_graph, "hi", user_id=None)
        assert real_graph.user_id == "preexisting-user"

    async def test_verified_user_id_overwrites_graph_user_id(self, real_graph):
        self._stub_async_start(real_graph)
        real_graph.user_id = "preexisting-user"
        await execute_graph_with_capture(real_graph, "hi", user_id="alice@example.com")
        assert real_graph.user_id == "alice@example.com"
