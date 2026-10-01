import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import app as api


async def request(path, method="GET", body=None, headers=None):
    parsed = urlsplit(path)
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    request_headers = [(b"host", b"testserver")]
    if body is not None:
        request_headers.append((b"content-type", b"application/json"))
    request_headers.extend(
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    )
    incoming = [{
        "type": "http.request",
        "body": body_bytes,
        "more_body": False,
    }]
    outgoing = []

    async def receive():
        return incoming.pop(0) if incoming else {"type": "http.disconnect"}

    async def send(message):
        outgoing.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": unquote(parsed.path),
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "headers": request_headers,
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "root_path": "",
    }
    await api.app(scope, receive, send)
    status = next(message["status"] for message in outgoing if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"")
        for message in outgoing
        if message["type"] == "http.response.body"
    )
    return status, json.loads(response_body) if response_body else None


class AdminModeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.credentials_path = Path(self.temp_dir.name) / "teachers.json"
        self.salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", b"correct horse battery staple", self.salt, 100_000
        ).hex()
        self.credentials_path.write_text(json.dumps({
            "teachers": [{
                "username": "teacher1",
                "password_hash": f"pbkdf2_sha256$100000${self.salt.hex()}${password_hash}",
            }]
        }), encoding="utf-8")
        self.previous_credentials_path = os.environ.get("TEACHER_CREDENTIALS_FILE")
        os.environ["TEACHER_CREDENTIALS_FILE"] = str(self.credentials_path)
        api.teacher_sessions.clear()

    async def asyncTearDown(self):
        api.teacher_sessions.clear()
        if self.previous_credentials_path is None:
            os.environ.pop("TEACHER_CREDENTIALS_FILE", None)
        else:
            os.environ["TEACHER_CREDENTIALS_FILE"] = self.previous_credentials_path
        self.temp_dir.cleanup()

    async def test_roster_is_public_but_mutations_require_teacher(self):
        status, activities = await request("/activities")
        self.assertEqual(status, 200)
        self.assertIn("Chess Club", activities)

        signup_status, _ = await request(
            "/activities/Chess%20Club/signup?email=new-student@mergington.edu",
            method="POST",
        )
        unregister_status, _ = await request(
            "/activities/Chess%20Club/unregister?email=michael%40mergington.edu",
            method="DELETE",
        )
        self.assertEqual(signup_status, 401)
        self.assertEqual(unregister_status, 401)

    async def test_teacher_can_login_manage_roster_and_logout(self):
        status, _ = await request(
            "/auth/login",
            method="POST",
            body={"username": "teacher1", "password": "wrong"},
        )
        self.assertEqual(status, 401)

        status, login = await request(
            "/auth/login",
            method="POST",
            body={
                "username": "teacher1",
                "password": "correct horse battery staple",
            },
        )
        self.assertEqual(status, 200)
        headers = {"authorization": f"Bearer {login['access_token']}"}

        status, _ = await request(
            "/activities/Chess%20Club/signup?email=new-student%40mergington.edu",
            method="POST",
            headers=headers,
        )
        self.assertEqual(status, 200)

        status, _ = await request(
            "/activities/Chess%20Club/unregister?email=new-student%40mergington.edu",
            method="DELETE",
            headers=headers,
        )
        self.assertEqual(status, 200)

        status, _ = await request("/auth/logout", method="POST", headers=headers)
        self.assertEqual(status, 200)
        status, _ = await request(
            "/activities/Chess%20Club/signup?email=after-logout%40mergington.edu",
            method="POST",
            headers=headers,
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()