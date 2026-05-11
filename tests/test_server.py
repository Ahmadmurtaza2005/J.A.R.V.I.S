"""Smoke tests for the Railway / Docker HTTP entrypoint (no mic or OpenCV)."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from server import app


class TestServerRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

    def test_root_is_jarvis_hud(self) -> None:
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))
        self.assertIn("JARVIS", r.text)
        self.assertIn("CLOUD CORE ONLINE", r.text)

    def test_api_status_json(self) -> None:
        r = self.client.get("/api/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get("status"), "online")
        self.assertEqual(body.get("service"), "Jarvis")
        self.assertIn("timestamp_utc", body)
        self.assertIn("newsapi_configured", body)
        self.assertIsInstance(body.get("newsapi_configured"), bool)

    def test_ui(self) -> None:
        r = self.client.get("/ui")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))
        self.assertIn("JARVIS", r.text)


if __name__ == "__main__":
    unittest.main()
