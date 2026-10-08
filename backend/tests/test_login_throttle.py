"""Abuso, límites de recursos y recuperación legítima sin relojes reales."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.core.login_throttle import LoginThrottle, get_login_throttle


def fail(limiter, account="a@example.com", source="source"):
    with limiter.attempt(account, source):
        pass


def test_simultaneous_initialization_shares_a_single_budget():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        instances = list(pool.map(lambda _: get_login_throttle(request), range(100)))
    assert all(instance is instances[0] for instance in instances)
    for instance in instances[:5]:
        fail(instance)
    with pytest.raises(HTTPException):
        fail(instances[-1])


@pytest.mark.asyncio
async def test_forged_forwarded_headers_do_not_change_source_budget(client):
    for index in range(30):
        response = await client.post(
            "/api/auth/login",
            json={"email": f"missing{index}@example.com", "password": "wrong"},
            headers={
                "X-Forwarded-For": f"192.0.2.{index}",
                "X-Real-IP": f"192.0.2.{index}",
            },
        )
        assert response.status_code == 401
    response = await client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_admin_reset_remains_available_during_throttle(
    client, test_user, admin_auth_headers
):
    from app.main import app

    now = [0.0]
    app.state.login_throttle = LoginThrottle(clock=lambda: now[0])
    for _ in range(5):
        response = await client.post(
            "/api/auth/login", json={"email": test_user.email, "password": "wrong"}
        )
        assert response.status_code == 401
    response = await client.post(
        f"/api/usuarios/{test_user.id}/reset-password",
        headers=admin_auth_headers,
        json={"password": "newpassword123"},
    )
    assert response.status_code == 200
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "newpassword123"},
        )
    ).status_code == 429
    now[0] = 60
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "newpassword123"},
        )
    ).status_code == 200


def test_account_rotating_origins_case_and_automatic_recovery():
    now = [100.0]
    limiter = LoginThrottle(clock=lambda: now[0])
    for index in range(5):
        fail(limiter, " A@Example.com ", str(index))
    now[0] = 120
    with pytest.raises(HTTPException) as exc:
        fail(limiter, source="new")
    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "40"}
    now[0] = 159.5
    with pytest.raises(HTTPException) as exc:
        fail(limiter)
    assert exc.value.headers == {"Retry-After": "1"}
    now[0] = 160
    fail(limiter)


def test_valid_logins_do_not_exhaust_account_and_shared_office():
    limiter = LoginThrottle()
    for index in range(20):
        with limiter.attempt("a@example.com", "office") as result:
            result["success"] = True
    for index in range(10):
        fail(limiter, f"user{index}@example.com", "office")
    with pytest.raises(HTTPException):
        fail(limiter, "another@example.com", "office")
    fail(limiter, "another@example.com", "other-office")


def test_global_budget_and_capacity_preserve_active_entries():
    limiter = LoginThrottle(total_limit=3)
    for index in range(3):
        fail(limiter, f"{index}@example.com", str(index))
    with pytest.raises(HTTPException):
        fail(limiter, "new@example.com", "new")
    now = [0.0]
    limiter = LoginThrottle(clock=lambda: now[0], max_entries=2)
    fail(limiter)
    for _ in range(5):
        with pytest.raises(HTTPException):
            fail(limiter, "other@example.com", "other")
    assert len(limiter._entries) == 2
    now[0] = 60
    fail(limiter, "other@example.com", "other")


def test_parallel_admission_is_atomic_and_exception_releases_slot():
    limiter = LoginThrottle(concurrency=1)
    with limiter.attempt("a@example.com", "office"):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(fail, limiter, str(index), str(index)) for index in range(8)
            ]
            for future in futures:
                with pytest.raises(HTTPException) as exc:
                    future.result()
                assert exc.value.headers["Retry-After"] == "1"
    with pytest.raises(RuntimeError):
        with limiter.attempt("b@example.com", "office"):
            raise RuntimeError("Synthetic failure")
    fail(limiter, "c@example.com")


@pytest.mark.asyncio
async def test_api_blocks_before_bcrypt_ignores_forwarded_headers_and_recovers(
    client, test_user, monkeypatch
):
    from app.main import app
    from app.api import auth

    now = [0.0]
    app.state.login_throttle = LoginThrottle(clock=lambda: now[0])
    for index in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@user.com", "password": "wrong"},
            headers={"X-Forwarded-For": f"192.0.2.{index}"},
        )
        assert response.status_code == 401
    original = auth.verify_password

    def unexpected(*args):
        raise AssertionError("bcrypt must not run for a throttled request")

    monkeypatch.setattr(auth, "verify_password", unexpected)
    response = await client.post(
        "/api/auth/login",
        json={"email": "TEST@USER.COM", "password": "testpassword123"},
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    monkeypatch.setattr(auth, "verify_password", original)
    now[0] = 60
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_nonexistent_accounts_also_have_budget(client):
    for _ in range(5):
        assert (
            await client.post(
                "/api/auth/login",
                json={"email": "absent@example.com", "password": "wrong"},
            )
        ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"email": "absent@example.com", "password": "wrong"}
        )
    ).status_code == 429


@pytest.mark.asyncio
async def test_cancellation_does_not_release_running_password_work(monkeypatch):
    from app.api import auth

    started = asyncio.Event()
    finish = asyncio.Event()

    async def slow_verify(*args):
        started.set()
        await finish.wait()
        return False

    monkeypatch.setattr(auth, "run_in_threadpool", slow_verify)
    limiter = LoginThrottle(concurrency=1)

    async def attempt():
        with limiter.attempt("a@example.com", "office"):
            await auth._verify_password("synthetic", "synthetic")

    task = asyncio.create_task(attempt())
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    with pytest.raises(HTTPException):
        fail(limiter, "b@example.com")
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    fail(limiter, "b@example.com")
