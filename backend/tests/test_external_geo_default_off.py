"""No visitor IP reaches a third party unless the operator switched it on.

Higashi is sold and documented as self-hosted analytics that keeps a customer's
data on their own server. `services/geo.py` resolves an IP by calling ip-api.com
- a third party, in the United States, over plain HTTP, because the free tier has
no TLS. An IP address is personal data, so that call cannot be the default and
cannot be silent.

Each test names the promise it holds; remove the matching hook and it must fail.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import asyncio  # noqa: E402

from config import Settings, get_settings  # noqa: E402
from services import geo  # noqa: E402


class ExternalGeoIsOffByDefault(unittest.TestCase):
    def test_the_setting_defaults_to_off(self):
        """A fresh install does not contact a geolocation provider."""
        self.assertFalse(Settings(_env_file=None).external_geo)

    def test_no_http_call_is_made_when_off(self):
        """Off means no request leaves the machine - not a request that is discarded."""
        called = []

        class Boom:
            def __init__(self, *a, **k):
                called.append(True)

            async def __aenter__(self):
                raise AssertionError("resolve_geo made an HTTP call while external_geo was off")

            async def __aexit__(self, *a):
                return False

        settings = Settings(_env_file=None)
        self.assertFalse(settings.external_geo)
        with patch.object(geo, "get_settings", lambda: settings), \
             patch.object(geo.httpx, "AsyncClient", Boom):
            result = asyncio.run(geo.resolve_geo("203.0.113.7"))
        self.assertEqual(result, {})
        self.assertEqual(called, [], "an AsyncClient was constructed while external_geo was off")

    def test_there_is_no_second_route_to_the_provider(self):
        """One gate only works if one module can reach the provider.

        Three call sites reach geolocation - the log importer, the log-import
        script and the browser collector - and the gate lives inside resolve_geo
        so all three are covered at once. That holds only while resolve_geo is
        the single place that knows the endpoint.
        """
        offenders = []
        for path in BACKEND.rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            if path == BACKEND / "services" / "geo.py":
                continue
            # Comments are stripped: config.py DESCRIBES the provider in the
            # note explaining why the setting defaults to off, and documenting a
            # thing is not a route to it.
            code = "\n".join(
                line for line in path.read_text(errors="ignore").splitlines()
                if not line.lstrip().startswith("#")
            )
            if "ip-api.com" in code or "GEO_API" in code:
                offenders.append(str(path.relative_to(BACKEND)))
        self.assertEqual(
            offenders, [],
            "only services/geo.py may know the geolocation endpoint; found it in: %s" % offenders,
        )

    def test_turning_it_on_is_what_permits_the_call(self):
        """The gate reads the setting; it is not hardcoded off."""
        settings = Settings(_env_file=None)
        settings.external_geo = True
        seen = {}

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"countryCode": "CA", "regionName": "QC", "city": "Montreal",
                        "as": "AS1", "timezone": "America/Toronto"}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url):
                seen["url"] = url
                return FakeResponse()

        with patch.object(geo, "get_settings", lambda: settings), \
             patch.object(geo.httpx, "AsyncClient", FakeClient):
            result = asyncio.run(geo.resolve_geo("203.0.113.7"))
        self.assertEqual(result["country"], "CA")
        self.assertIn("203.0.113.7", seen["url"])


if __name__ == "__main__":
    unittest.main()
