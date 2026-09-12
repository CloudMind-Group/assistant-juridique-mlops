import os
os.environ["M5_JWT_SECRET"] = "cle-de-test-pour-les-tests-automatiques-uniquement"

from fastapi.testclient import TestClient
from src.m5_api.main import app

client = TestClient(app)

def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200

def test_chat_without_token_returns_401():
    response = client.post("/chat?question=test")
    assert response.status_code == 401