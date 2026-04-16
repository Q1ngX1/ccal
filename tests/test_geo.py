"""Tests for src/input/geo.py — geolocation via IP."""
import json
from unittest.mock import patch, MagicMock

import pytest

from src.input.geo import GeoInfo, get_geo_info


class TestGeoInfo:
    def test_summary_full(self):
        geo = GeoInfo(city="Shanghai", region="Shanghai", country="China", timezone="Asia/Shanghai")
        assert geo.summary() == "Shanghai, Shanghai, China (timezone: Asia/Shanghai)"

    def test_summary_partial(self):
        geo = GeoInfo(city="Tokyo", timezone="Asia/Tokyo")
        assert geo.summary() == "Tokyo (timezone: Asia/Tokyo)"

    def test_summary_empty(self):
        geo = GeoInfo()
        assert geo.summary() == "Unknown (timezone: Unknown)"

    def test_summary_no_timezone(self):
        geo = GeoInfo(city="Paris", country="France")
        assert geo.summary() == "Paris, France (timezone: Unknown)"


class TestGetGeoInfo:
    def test_success(self):
        mock_data = {
            "city": "Shanghai",
            "regionName": "Shanghai",
            "country": "China",
            "timezone": "Asia/Shanghai",
            "lat": 31.2,
            "lon": 121.5,
        }
        # Clear lru_cache between tests
        get_geo_info.cache_clear()

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.input.geo.urllib.request.urlopen", return_value=mock_resp):
            geo = get_geo_info()

        assert geo.city == "Shanghai"
        assert geo.timezone == "Asia/Shanghai"
        assert geo.lat == 31.2

    def test_network_error_returns_empty(self):
        get_geo_info.cache_clear()
        with patch("src.input.geo.urllib.request.urlopen", side_effect=Exception("timeout")):
            geo = get_geo_info()
        assert geo.city is None
        assert geo.timezone is None

    def test_caching(self):
        get_geo_info.cache_clear()
        mock_data = {"city": "Cached", "regionName": "", "country": "", "timezone": "UTC", "lat": 0, "lon": 0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.input.geo.urllib.request.urlopen", return_value=mock_resp) as mock_url:
            geo1 = get_geo_info()
            geo2 = get_geo_info()
            # Should only call once due to lru_cache
            mock_url.assert_called_once()
            assert geo1 is geo2
