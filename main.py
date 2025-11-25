from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine, Base
from schemas import (OperatorCreate, OperatorResponse, LeadCreate, LeadResponse, 
                    SourceCreate, SourceResponse, ContactCreate, ContactResponse,
                    DistributionConfig, OperatorSourceWeightResponse, ErrorResponse)
from crud import (create_operator, get_operators, get_operators_load_map, create_lead, 
                 create_source, get_sources, set_distribution_config, get_distribution_config,
                 create_contact, get_contacts, get_leads_with_contacts, 
                 get_operator, get_operator_load)

# Создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Mini-CRM Lead Distribution System",
    description="Система распределения лидов между операторами по источникам",
    version="9.0.0",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Вспомогательные функции для преобразования
def operator_to_response(operator, load: int = 0) -> OperatorResponse:
    """Преобразовать оператора в Response с нагрузкой"""
    return OperatorResponse(
        id=operator.id,
        name=operator.name,
        is_active=operator.is_active,
        max_load=operator.max_load,
        created_at=operator.created_at,
        current_load=load
    )

# Операторы
@app.post("/operators/", response_model=OperatorResponse, status_code=201)
def create_operator_endpoint(operator: OperatorCreate, db: Session = Depends(get_db)):
    operator_obj = create_operator(db, operator)
    return operator_to_response(operator_obj, 0)

@app.get("/operators/", response_model=List[OperatorResponse])
def read_operators(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    operators = get_operators(db, skip=skip, limit=limit)
    operator_ids = [op.id for op in operators]
    loads_map = get_operators_load_map(db, operator_ids)
    
    return [operator_to_response(op, loads_map.get(op.id, 0)) for op in operators]

@app.get("/operators/{operator_id}", response_model=OperatorResponse)
def read_operator(operator_id: int, db: Session = Depends(get_db)):
    operator = get_operator(db, operator_id)
    load = get_operator_load(db, operator_id)
    return operator_to_response(operator, load)

# Лиды
@app.post("/leads/", response_model=LeadResponse, status_code=201)
def create_lead_endpoint(lead: LeadCreate, db: Session = Depends(get_db)):
    lead_obj = create_lead(db, lead)
    return LeadResponse.from_orm(lead_obj)

# Источники
@app.post("/sources/", response_model=SourceResponse, status_code=201)
def create_source_endpoint(source: SourceCreate, db: Session = Depends(get_db)):
    source_obj = create_source(db, source)
    return SourceResponse.from_orm(source_obj)

@app.get("/sources/", response_model=List[SourceResponse])
def read_sources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sources = get_sources(db, skip=skip, limit=limit)
    return [SourceResponse.from_orm(source) for source in sources]

# Распределение
@app.post("/distribution/config/", response_model=List[OperatorSourceWeightResponse], status_code=201)
def set_distribution_config_endpoint(config: DistributionConfig, db: Session = Depends(get_db)):
    weights = set_distribution_config(db, config)
    return [OperatorSourceWeightResponse.from_orm(weight) for weight in weights]

@app.get("/distribution/config/{source_id}", response_model=List[OperatorSourceWeightResponse])
def get_distribution_config_endpoint(source_id: int, db: Session = Depends(get_db)):
    weights = get_distribution_config(db, source_id)
    return [OperatorSourceWeightResponse.from_orm(weight) for weight in weights]

# Обращения
@app.post("/contacts/", response_model=ContactResponse, status_code=201)
def create_contact_endpoint(contact: ContactCreate, db: Session = Depends(get_db)):
    contact_obj = create_contact(db, contact)
    return ContactResponse.from_orm(contact_obj)

@app.get("/contacts/", response_model=List[ContactResponse])
def read_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    contacts = get_contacts(db, skip=skip, limit=limit)
    return [ContactResponse.from_orm(contact) for contact in contacts]

@app.get("/leads/with-contacts/", response_model=List[LeadResponse])
def read_leads_with_contacts(db: Session = Depends(get_db)):
    leads = get_leads_with_contacts(db)
    return [LeadResponse.from_orm(lead) for lead in leads]

# Система
@app.get("/")
def read_root():
    return {"message": "Mini-CRM Lead Distribution System"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}