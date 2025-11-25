import random
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from models import Operator, Contact, OperatorSourceWeight, Source
from typing import Optional, List

class DistributionError(Exception):
    """Базовое исключение для ошибок распределения"""
    pass

class SourceNotFoundError(DistributionError):
    """Источник не найден"""
    pass

class DistributionEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def validate_source(self, source_id: int) -> Source:
        """Проверить существование источника"""
        source = self.db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise SourceNotFoundError(f"Source with id {source_id} not found")
        return source
    
    def get_available_operators(self, source_id: int) -> List[dict]:
        """Получить доступных операторов для источника одним оптимизированным запросом"""
        # Валидируем источник
        self.validate_source(source_id)
        
        # Подзапрос для подсчета нагрузки по операторам
        load_subquery = self.db.query(
            Contact.operator_id,
            func.count(Contact.id).label('current_load')
        ).filter(
            Contact.status.in_(["new", "in_progress"])
        ).group_by(Contact.operator_id).subquery()
        
        # Основной запрос: операторы с весами и нагрузкой
        operators_data = self.db.query(
            Operator,
            OperatorSourceWeight.weight,
            func.coalesce(load_subquery.c.current_load, 0).label('current_load')
        ).join(
            OperatorSourceWeight, Operator.id == OperatorSourceWeight.operator_id
        ).outerjoin(
            load_subquery, Operator.id == load_subquery.c.operator_id
        ).filter(
            OperatorSourceWeight.source_id == source_id,
            Operator.is_active == True
        ).all()
        
        # Фильтруем операторов по нагрузке
        available_operators = []
        for operator, weight, current_load in operators_data:
            if current_load < operator.max_load:
                available_operators.append({
                    'operator': operator,
                    'weight': weight,
                    'current_load': current_load
                })
        
        return available_operators
    
    def select_operator(self, source_id: int) -> Optional[Operator]:
        """Выбрать оператора по весовому распределению"""
        try:
            available_operators = self.get_available_operators(source_id)
        except SourceNotFoundError:
            # Пробрасываем специфические ошибки
            raise
        except Exception as e:
            # Логируем ошибку и возвращаем None
            print(f"Error in select_operator: {e}")
            return None
        
        if not available_operators:
            return None
        
        # Взвешенный случайный выбор
        total_weight = sum(op['weight'] for op in available_operators)
        if total_weight <= 0:
            return available_operators[0]['operator']
        
        random_value = random.uniform(0, total_weight)
        current_weight = 0
        
        for op_data in available_operators:
            current_weight += op_data['weight']
            if random_value <= current_weight:
                return op_data['operator']
        
        return available_operators[0]['operator']