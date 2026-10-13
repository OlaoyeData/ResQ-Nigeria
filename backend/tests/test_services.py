import asyncio
from app.services.ai_service import ai_service
from app.services.nipost_service import MockPostcodeProvider

def test_ai_classification_and_missing_information():
    result=ai_service.classify_incident("My brother has collapsed and is not responding")
    assert result["incident_type"]=="medical"
    assert result["urgency"]=="high"
    assert result["confidence"]<=1
    assert "exact_location" in result["missing_information"]

def test_ai_extracts_location_without_resolving_it():
    assert ai_service.extract_location("Accident beside the old secretariat on Ondo Road")

def test_mock_postcode_checks_format_without_fake_location():
    provider=MockPostcodeProvider()
    valid=asyncio.run(provider.lookup("EK-01-A03-FK-01"))
    invalid=asyncio.run(provider.lookup("12345"))
    assert valid["verification_status"]=="PENDING" and valid["verified"] is False
    assert "state" not in valid and invalid["verification_status"]=="FAILED"
