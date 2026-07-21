"""
test_01_health.py — Tests for GET / (root health check endpoint).
"""

import pytest


def test_root_returns_200(client):
    """Root endpoint must return HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_root_response_has_status_online(client):
    """Root endpoint must include status: 'online'."""
    response = client.get("/")
    data = response.json()
    assert data.get("status") == "online"


def test_root_response_has_service_name(client):
    """Root endpoint must include a 'service' field with a non-empty string."""
    response = client.get("/")
    data = response.json()
    assert "service" in data
    assert isinstance(data["service"], str)
    assert len(data["service"]) > 0


def test_root_response_has_version(client):
    """Root endpoint must include a 'version' field."""
    response = client.get("/")
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0
