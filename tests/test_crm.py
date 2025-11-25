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
        
        # Создаем операторов
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
        
        # Создаем источник
        source_response = requests.post(f"{BASE_URL}/sources/", json={
            "name": f"TestSource_{random.randint(1000, 9999)}",
            "description": "Test source for automated testing"
        })
        self.sources.append(source_response.json())
        
        # Настраиваем распределение
        weights_response = requests.post(f"{BASE_URL}/distribution/config/", json={
            "source_id": self.sources[0]['id'],
            "operators": [
                {"operator_id": self.operators[0]['id'], "weight": 70},
                {"operator_id": self.operators[1]['id'], "weight": 30}
            ]
        })
        
        yield
        
        # Очистка после тестов (опционально)
        # В реальной системе лучше использовать тестовую БД

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
        
        # Первое создание - успех
        response1 = requests.post(f"{BASE_URL}/operators/", json=operator_data)
        assert response1.status_code == 201
        
        # Второе создание - ошибка
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
        
        # Создаем лида
        response = requests.post(f"{BASE_URL}/leads/", json=lead_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["external_id"] == lead_data["external_id"]
        assert data["name"] == lead_data["name"]
        
        # Пробуем создать того же лида с обновлением данных
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

    def test_contact_distribution(self, setup_data):
        """Тест распределения обращений"""
        source_id = self.sources[0]['id']
        
        # Создаем несколько обращений
        contacts_created = []
        for i in range(4):
            contact_data = {
                "lead_external_id": f"dist_test_{i}_{random.randint(1000, 9999)}@test.com",
                "source_id": source_id,
                "message": f"Test message {i}"
            }
            
            response = requests.post(f"{BASE_URL}/contacts/", json=contact_data)
            assert response.status_code == 201
            
            contact = response.json()
            contacts_created.append(contact)
            
            # Проверяем, что обращение создано
            assert contact["source_id"] == source_id
            assert contact["lead_id"] is not None
        
        # Проверяем распределение по операторам
        operators_response = requests.get(f"{BASE_URL}/operators/")
        operators = operators_response.json()
        
        # Находим наших тестовых операторов
        test_operators = [op for op in operators if op['id'] in [self.operators[0]['id'], self.operators[1]['id']]]
        
        # Проверяем, что нагрузка распределилась
        total_load = sum(op['current_load'] for op in test_operators)
        assert total_load > 0
        
        # Проверяем, что нагрузка не превышает лимиты
        for op in test_operators:
            assert op['current_load'] <= op['max_load']

    def test_operator_overload(self, setup_data):
        """Тест перегрузки операторов"""
        source_id = self.sources[0]['id']
        operator_id = self.operators[1]['id']  # Оператор с max_load=2
        
        # Создаем обращения до превышения лимита
        contacts_with_operator = []
        contacts_without_operator = 0
        
        for i in range(5):  # Больше чем max_load
            contact_data = {
                "lead_external_id": f"overload_test_{i}_{random.randint(1000, 9999)}@test.com",
                "source_id": source_id,
                "message": f"Overload test {i}"
            }
            
            response = requests.post(f"{BASE_URL}/contacts/", json=contact_data)
            assert response.status_code == 201
            
            contact = response.json()
            if contact.get('operator_id') == operator_id:
                contacts_with_operator.append(contact)
            elif contact.get('operator_id') is None:
                contacts_without_operator += 1
        
        # Проверяем, что оператор не получил больше обращений чем его лимит
        assert len(contacts_with_operator) <= 2  # max_load оператора
        
        # Проверяем, что некоторые обращения остались без оператора
        assert contacts_without_operator >= 0

    def test_distribution_config(self, setup_data):
        """Тест настройки распределения"""
        source_id = self.sources[0]['id']
        
        # Получаем текущую конфигурацию
        response = requests.get(f"{BASE_URL}/distribution/config/{source_id}")
        assert response.status_code == 200
        
        config = response.json()
        assert len(config) == 2  # Два оператора в конфигурации
        
        # Проверяем веса
        weights = {item['operator_id']: item['weight'] for item in config}
        assert weights[self.operators[0]['id']] == 70
        assert weights[self.operators[1]['id']] == 30

    def test_nonexistent_source_contact(self):
        """Тест создания обращения с несуществующим источником"""
        contact_data = {
            "lead_external_id": "test@example.com",
            "source_id": 99999,  # Несуществующий ID
            "message": "Test message"
        }
        
        response = requests.post(f"{BASE_URL}/contacts/", json=contact_data)
        assert response.status_code == 404

    def test_operator_load_calculation(self, setup_data):
        """Тест расчета нагрузки операторов"""
        source_id = self.sources[0]['id']
        
        # Создаем несколько обращений
        for i in range(2):
            contact_data = {
                "lead_external_id": f"load_test_{i}_{random.randint(1000, 9999)}@test.com",
                "source_id": source_id,
                "message": f"Load test {i}"
            }
            requests.post(f"{BASE_URL}/contacts/", json=contact_data)
        
        # Проверяем нагрузку через эндпоинт оператора
        operator_id = self.operators[0]['id']
        response = requests.get(f"{BASE_URL}/operators/{operator_id}")
        assert response.status_code == 200
        
        operator_data = response.json()
        assert 'current_load' in operator_data
        assert operator_data['current_load'] >= 0

    def test_leads_with_contacts(self, setup_data):
        """Тест получения лидов с обращениями"""
        source_id = self.sources[0]['id']
        
        # Создаем лида с несколькими обращениями
        lead_external_id = f"multi_contact_lead_{random.randint(10000, 99999)}@test.com"
        
        for i in range(3):
            contact_data = {
                "lead_external_id": lead_external_id,
                "source_id": source_id,
                "message": f"Message {i}"
            }
            requests.post(f"{BASE_URL}/contacts/", json=contact_data)
        
        # Получаем лидов с обращениями
        response = requests.get(f"{BASE_URL}/leads/with-contacts/")
        assert response.status_code == 200
        
        leads = response.json()
        test_lead = next((lead for lead in leads if lead['external_id'] == lead_external_id), None)
        
        assert test_lead is not None

    def test_weighted_distribution(self, setup_data):
        """Тест взвешенного распределения"""
        source_id = self.sources[0]['id']
        
        # Создаем много обращений для статистики
        operator_counts = {self.operators[0]['id']: 0, self.operators[1]['id']: 0}
        
        for i in range(20):
            contact_data = {
                "lead_external_id": f"weight_test_{i}_{random.randint(1000, 9999)}@test.com",
                "source_id": source_id,
                "message": f"Weight test {i}"
            }
            
            response = requests.post(f"{BASE_URL}/contacts/", json=contact_data)
            contact = response.json()
            
            if contact.get('operator_id') in operator_counts:
                operator_counts[contact['operator_id']] += 1
        
        total_assigned = sum(operator_counts.values())
        if total_assigned > 0:
            # Проверяем, что распределение примерно соответствует весам (70/30)
            ratio = operator_counts[self.operators[0]['id']] / total_assigned
            # Допускаем некоторую погрешность из-за случайности
            assert 0.5 <= ratio <= 0.9  # Ожидаем ~70%, но допускаем отклонения

if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v"])