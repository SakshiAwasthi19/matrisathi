from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _seed_staff(db_session, *, username="coordinator1", password="synthetic-password-123", active=True):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, username=username, password=password, active=active)
    make_membership(db_session, staff, facility)
    return staff, facility


def test_login_success_sets_cookies(client, db_session):
    _seed_staff(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


def test_no_session_is_rejected(client, db_session):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_malformed_access_token_is_rejected(client, db_session):
    client.cookies.set("access_token", "this-is-not-a-valid-jwt")
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_access_token_signed_with_wrong_secret_is_rejected(client, db_session):
    import jwt as pyjwt

    forged = pyjwt.encode({"sub": "00000000-0000-0000-0000-000000000000"}, "wrong-secret", algorithm="HS256")
    client.cookies.set("access_token", forged)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_login_wrong_password_is_generic(client, db_session):
    _seed_staff(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "wrong"}, headers=CSRF_HEADERS)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_login_unknown_username_is_same_generic_error(client, db_session):
    _seed_staff(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever"}, headers=CSRF_HEADERS)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_disabled_user_cannot_login(client, db_session):
    _seed_staff(db_session, active=False)
    resp = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_login_throttled_after_repeated_failures(client, db_session):
    # LOGIN_THROTTLE_MAX_ATTEMPTS is set to 3 for the test env (conftest.py).
    _seed_staff(db_session)
    for _ in range(3):
        r = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "wrong"}, headers=CSRF_HEADERS)
        assert r.status_code == 401

    # Even the CORRECT password is now rejected, with the identical generic
    # message/status — throttling state is never distinguishable from a
    # plain wrong-credentials response.
    r = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_disabled_user_loses_access_mid_session(client, db_session):
    staff, _ = _seed_staff(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    assert resp.status_code == 200

    # The access token is still unexpired, but the user is disabled in the DB.
    staff.active = False
    db_session.add(staff)
    db_session.commit()

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_logout_requires_csrf_header(client, db_session):
    _seed_staff(db_session)
    client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 403  # missing CSRF header


def test_logout_revokes_refresh_token(client, db_session):
    _seed_staff(db_session)
    client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    resp = client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    assert resp.status_code == 204

    # The refresh cookie the client still holds is now revoked server-side.
    resp = client.post("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    assert resp.status_code == 401


def test_refresh_rotates_token_and_old_one_stops_working(client, db_session):
    _seed_staff(db_session)
    client.post("/api/v1/auth/login", json={"username": "coordinator1", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    old_refresh_cookie = client.cookies.get("refresh_token")

    resp = client.post("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    assert resp.status_code == 200
    new_refresh_cookie = client.cookies.get("refresh_token")
    assert new_refresh_cookie != old_refresh_cookie

    # Replaying the OLD refresh token (reuse of an already-rotated token) is
    # rejected and revokes the whole session, not just that one token.
    client.cookies.set("refresh_token", old_refresh_cookie)
    resp = client.post("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    assert resp.status_code == 401

    # The session-wide revocation triggered by reuse detection means even the
    # latest, legitimately-issued refresh token no longer works either.
    client.cookies.set("refresh_token", new_refresh_cookie)
    resp = client.post("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    assert resp.status_code == 401
