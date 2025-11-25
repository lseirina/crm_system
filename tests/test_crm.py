import pytest
import requests
import time
from typing import Dict, List
import random

BASE_URL = "http://localhost:8000"

class TestCRMSystem:
    """Тесты для CRM системы распределения лидов"""
    
    @pytest.fixture
    def setup_data(self):
        """Фикстура для подготовки тестовых данных"""
        self.operators = []
        self.sources = []
        self.contacts = []
        
        op1_response = requests.post(f"{BASE_URL}/operators/", json={
            "name": f"TestOperator1_{random.randint(1000, 9999)}",
            "max_load": 3,
            "is_active": True
        })
        op2_response = requests.post(f"{BASE_URL}/operators/", json={
            "name": f"TestOperator2_{random.randint(1000, 9999)}",
            "max_load": 2,
            "is_active": True
        })
        
        self.operators.append(op1_response.json())
        self.operators.append(op2_response.json())
        
        source_response = requests.post(f"{BASE_URL}/sources/", json={
            "name": f"TestSource_{random.randint(1000, 9999)}",
            "description": "Test source for automated testing"
        })
        self.sources.append(source_response.json())
    
        weights_response = requests.post(f"{BASE_URL}/distribution/config/", json={
            "source_id": self.sources[0]['id'],
            "operators": [
                {"operator_id": self.operators[0]['id'], "weight": 70},
                {"operator_id": self.operators[1]['id'], "weight": 30}
            ]
        })
        
        yield

    def test_health_check(self):
        """Тест проверки здоровья приложения"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_create_operator(self):
        """Тест создания оператора"""
        operator_data = {
            "name": f"NewOperator_{random.randint(1000, 9999)}",
            "max_load": 5,
            "is_active": True
        }
        
        response = requests.post(f"{BASE_URL}/operators/", json=operator_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == operator_data["name"]
        assert data["max_load"] == operator_data["max_load"]
        assert data["is_active"] == operator_data["is_active"]
        assert "id" in data

    def test_create_duplicate_operator(self):
        """Тест создания дублирующего оператора"""
        operator_data = {
            "name": f"UniqueOperator_{random.randint(1000, 9999)}",
            "max_load": 5
        }
        
        response1 = requests.post(f"{BASE_URL}/operators/", json=operator_data)
        assert response1.status_code == 201
        
        response2 = requests.post(f"{BASE_URL}/operators/", json=operator_data)
        assert response2.status_code == 400

    def test_create_source(self):
        """Тест создания источника"""
        source_data = {
            "name": f"NewSource_{random.randint(1000, 9999)}",
            "description": "Test source description"
        }
        
        response = requests.post(f"{BASE_URL}/sources/", json=source_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == source_data["name"]
        assert data["description"] == source_data["description"]
        assert "id" in data

    def test_lead_creation_and_lookup(self):
        """Тест создания и поиска лида"""
        lead_data = {
            "external_id": f"test_lead_{random.randint(10000, 99999)}@test.com",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1234567890"
        }
        
        response = requests.post(f"{BASE_URL}/leads/", json=lead_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["external_id"] == lead_data["external_id"]
        assert data["name"] == lead_data["name"]
        
        updated_lead_data = {
            "external_id": lead_data["external_id"],
            "name": "Updated Test User",
            "phone": "+0987654321"
        }
        
        response2 = requests.post(f"{BASE_URL}/leads/", json=updated_lead_data)
        assert response2.status_code == 201
        data2 = response2.json()
        assert data2["name"] == "Updated Test User"
        assert data2["phone"] == "+0987654321"


    def test_distribution_config(self, setup_data):
        """Тест настройки распределения"""
        source_id = self.sources[0]['id']
        
        response = requests.get(f"{BASE_URL}/distribution/config/{source_id}")
        assert response.status_code == 200
        
        config = response.json()
        assert len(config) == 2 
        
        weights = {item['operator_id']: item['weight'] for item in config}
        assert weights[self.operators[0]['id']] == 70
        assert weights[self.operators[1]['id']] == 30

    def test_nonexistent_source_contact(self):
        """Тест создания обращения с несуществующим источником"""
        contact_data = {
            "lead_external_id": "test@example.com",
            "source_id": 99999,
            "message": "Test message"
        }
        
        response = requests.post(f"{BASE_URL}/contacts/", json=contact_data)
        assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v"])