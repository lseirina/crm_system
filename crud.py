from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import List, Dict
from models import Operator, Lead, Source, Contact, OperatorSourceWeight
from schemas import (OperatorCreate, LeadCreate, SourceCreate, 
                    ContactCreate, OperatorSourceWeightCreate)
from distribution import DistributionEngine, SourceNotFoundError

def create_operator(db: Session, operator: OperatorCreate) -> Operator:
    db_operator = Operator(**operator.dict())
    
    try:
        db.add(db_operator)
        db.commit()
        db.refresh(db_operator)
        return db_operator
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator with this name already exists"
        )

def get_operators(db: Session, skip: int = 0, limit: int = 100) -> List[Operator]:
    return db.query(Operator).offset(skip).limit(limit).all()

def get_operators_load_map(db: Session, operator_ids: List[int]) -> Dict[int, int]:
    """Получить карту нагрузок для операторов одним запросом"""
    if not operator_ids:
        return {}
    
    result = db.query(
        Contact.operator_id,
        func.count(Contact.id).label('load')
    ).filter(
        Contact.operator_id.in_(operator_ids),
        Contact.status.in_(["new", "in_progress"])
    ).group_by(Contact.operator_id).all()
    
    return {op_id: load for op_id, load in result}

def create_lead(db: Session, lead: LeadCreate) -> Lead:
    """Создать лида с защитой от дубликатов"""
    # Сначала пытаемся найти существующий лид
    existing_lead = db.query(Lead).filter(Lead.external_id == lead.external_id).first()
    if existing_lead:
        # Обновляем существующий лид
        update_data = lead.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field != 'external_id' and value is not None and str(value).strip():
                setattr(existing_lead, field, value)
        db.commit()
        db.refresh(existing_lead)
        return existing_lead
    
    # Создаем новый лид
    db_lead = Lead(**lead.dict())
    
    try:
        db.add(db_lead)
        db.commit()
        db.refresh(db_lead)
        return db_lead
    except IntegrityError:
        db.rollback()
        # Если произошел конфликт, находим существующий лид
        existing_lead = db.query(Lead).filter(Lead.external_id == lead.external_id).first()
        if existing_lead:
            return existing_lead
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create lead"
            )

def get_or_create_lead(db: Session, external_id: str, **kwargs) -> Lead:
    """Найти или создать лида"""
    # Сначала пытаемся найти существующий лид
    existing_lead = db.query(Lead).filter(Lead.external_id == external_id).first()
    if existing_lead:
        # Обновляем данные если нужно
        update_data = {k: v for k, v in kwargs.items() if v is not None and str(v).strip()}
        for field, value in update_data.items():
            setattr(existing_lead, field, value)
        db.commit()
        db.refresh(existing_lead)
        return existing_lead
    
    # Создаем новый лид
    lead_data = {k: v for k, v in kwargs.items() if v is not None and str(v).strip()}
    lead_data['external_id'] = external_id
    
    try:
        lead_create = LeadCreate(**lead_data)
        return create_lead(db, lead_create)
    except Exception:
        # Если не удалось создать с полными данными, создаем с минимальными
        minimal_data = {'external_id': external_id}
        lead_create = LeadCreate(**minimal_data)
        return create_lead(db, lead_create)

def create_source(db: Session, source: SourceCreate) -> Source:
    db_source = Source(**source.dict())
    
    try:
        db.add(db_source)
        db.commit()
        db.refresh(db_source)
        return db_source
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source with this name already exists"
        )

def get_sources(db: Session, skip: int = 0, limit: int = 100) -> List[Source]:
    return db.query(Source).offset(skip).limit(limit).all()

def set_distribution_config(db: Session, config) -> List[OperatorSourceWeight]:
    source = db.query(Source).filter(Source.id == config.source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    operator_ids = [op.operator_id for op in config.operators]
    existing_operators = db.query(Operator.id).filter(Operator.id.in_(operator_ids)).all()
    existing_operator_ids = {op.id for op in existing_operators}
    
    missing_operators = set(operator_ids) - existing_operator_ids
    if missing_operators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operators not found: {missing_operators}"
        )
    
    try:
        # Удаляем старые настройки
        db.query(OperatorSourceWeight).filter(
            OperatorSourceWeight.source_id == config.source_id
        ).delete()
        
        # Создаем новые настройки
        weights = []
        for op_weight in config.operators:
            db_weight = OperatorSourceWeight(**op_weight.dict())
            db.add(db_weight)
            weights.append(db_weight)
        
        db.commit()
        
        # Обновляем объекты
        for weight in weights:
            db.refresh(weight)
        
        return weights
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set distribution config: {str(e)}"
        )

def get_distribution_config(db: Session, source_id: int) -> List[OperatorSourceWeight]:
    return db.query(OperatorSourceWeight).filter(
        OperatorSourceWeight.source_id == source_id
    ).all()

def create_contact(db: Session, contact: ContactCreate) -> Contact:
    """Создать обращение с распределением оператора"""
    # Проверяем существование источника
    source = db.query(Source).filter(Source.id == contact.source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    try:
        # Находим или создаем лида
        lead = get_or_create_lead(db, contact.lead_external_id)
        
        # Выбираем оператора
        distribution_engine = DistributionEngine(db)
        operator = distribution_engine.select_operator(contact.source_id)
        
        # Создаем обращение (может быть без оператора)
        db_contact = Contact(
            lead_id=lead.id,
            source_id=contact.source_id,
            operator_id=operator.id if operator else None,
            message=contact.message
        )
        
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        return db_contact
        
    except SourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contact: {str(e)}"
        )

def get_contacts(db: Session, skip: int = 0, limit: int = 100) -> List[Contact]:
    return db.query(Contact).options(
        selectinload(Contact.lead),
        selectinload(Contact.source),
        selectinload(Contact.operator)
    ).offset(skip).limit(limit).all()

def get_leads_with_contacts(db: Session) -> List[Lead]:
    return db.query(Lead).options(selectinload(Lead.contacts)).all()

def get_operator(db: Session, operator_id: int) -> Operator:
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found"
        )
    return operator

def get_operator_load(db: Session, operator_id: int) -> int:
    """Получить нагрузку конкретного оператора"""
    return db.query(Contact).filter(
        Contact.operator_id == operator_id,
        Contact.status.in_(["new", "in_progress"])
    ).count()