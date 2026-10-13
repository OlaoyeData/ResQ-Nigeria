import re

import httpx

from app.core.config import settings


# The new postcode has five segments (2-2-3-2-2 characters). The hyphens are
# presentation separators; the underlying code is 11 alphanumeric characters.
CODE_RE = re.compile(r"^[A-Z0-9]{2}-[A-Z0-9]{2}-[A-Z0-9]{3}-[A-Z0-9]{2}-[A-Z0-9]{2}$", re.I)
COMPACT_RE = re.compile(r"^[A-Z0-9]{11}$", re.I)

# Clearly synthetic sample fixture for the local portfolio demo. This is not
# an official postcode-to-coordinate record from NIPOST.
DEMO_LOCATIONS = {
    "FC02A09DB09": {
        "latitude": 9.0765,
        "longitude": 7.3986,
        "state": "FCT (demo fixture)",
        "lga": "Abuja Municipal (demo fixture)",
        "city": "Demo location",
    }
}


def normalize_postcode(code: str) -> str:
    compact = re.sub(r"[\s-]", "", code or "").upper()
    if not COMPACT_RE.fullmatch(compact):
        return ""
    return "-".join((compact[:2], compact[2:4], compact[4:7], compact[7:9], compact[9:11]))


def _coordinates(payload: dict) -> tuple[float | None, float | None]:
    location = payload.get("location") or payload.get("coordinates") or {}
    lat = payload.get("latitude", location.get("latitude", location.get("lat")))
    lon = payload.get("longitude", location.get("longitude", location.get("lon", location.get("lng"))))
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


class PostcodeProvider:
    async def lookup(self, code: str) -> dict:
        raise NotImplementedError


class MockPostcodeProvider(PostcodeProvider):
    async def lookup(self, code: str) -> dict:
        normalized = normalize_postcode(code)
        compact = normalized.replace("-", "")
        fixture = DEMO_LOCATIONS.get(compact)
        if fixture:
            return {
                "valid": True,
                "verified": False,
                "verification_status": "PENDING",
                "postcode": normalized,
                "latitude": fixture["latitude"],
                "longitude": fixture["longitude"],
                "state": fixture["state"],
                "lga": fixture["lga"],
                "city": fixture["city"],
                "provider": "mock-demo-fixture",
                "demo": True,
                "message": "Synthetic demo fixture only; this is not an official NIPOST lookup.",
            }
        valid = bool(normalized)
        return {
            "valid": valid,
            "verified": False,
            "verification_status": "PENDING" if valid else "FAILED",
            "postcode": normalized or code.strip().upper(),
            "provider": "mock",
            "demo": True,
            "message": "Code format accepted; no location is available in mock mode. Add GPS or use the published demo fixture." if valid else "Enter an 11-character digital postcode.",
        }


class NipostPostcodeProvider(PostcodeProvider):
    async def lookup(self, code: str) -> dict:
        normalized = normalize_postcode(code)
        if not normalized:
            return {"valid": False, "verified": False, "verification_status": "FAILED", "message": "Enter an 11-character digital postcode."}
        headers = {"X-API-Key": settings.nipost_api_key} if settings.nipost_api_key else {}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    f"{settings.nipost_api_base_url.rstrip('/')}/v1/lookup",
                    params={"code": normalized.replace("-", ""), "level": 1},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json().get("data", {})
            valid = payload.get("valid") is True
            latitude, longitude = _coordinates(payload)
            address = payload.get("administrative_address") or {}
            has_location = latitude is not None and longitude is not None
            return {
                "valid": valid,
                # A valid code without coordinates cannot support nearest-team matching.
                "verified": valid and has_location,
                "verification_status": "VERIFIED" if valid and has_location else ("PENDING" if valid else "FAILED"),
                "postcode": normalize_postcode(payload.get("postcode", normalized)) or normalized,
                "latitude": latitude,
                "longitude": longitude,
                "state": address.get("state_name", ""),
                "lga": address.get("lga_name", ""),
                "city": address.get("locality_name", ""),
                "provider": "nipost",
                "message": "Postcode is valid but the lookup did not return coordinates." if valid and not has_location else "",
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "valid": True,
                "verified": False,
                "verification_status": "PENDING",
                "postcode": normalized,
                "provider": "nipost",
                "message": "NIPOST lookup unavailable; location remains unverified.",
            }


def get_postcode_provider() -> PostcodeProvider:
    return NipostPostcodeProvider() if settings.nipost_provider.lower() == "nipost" else MockPostcodeProvider()
