from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.errors import AppError
from app.models import ClassRoom, User
from app.security import db_session, admin_user
from app.schemas.accounts import ClassInput, user_data

router = APIRouter(prefix='/api', tags=['classes'])


@router.get('/classes')
def classes(page: int=Query(1,ge=1), page_size: int=Query(20,ge=1,le=100), session=Depends(db_session)):
    query=select(ClassRoom).where(ClassRoom.status=='ACTIVE')
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.scalars(query.order_by(ClassRoom.id).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[{'id':r.id,'name':r.name} for r in rows], 'total':total, 'page':page,'page_size':page_size}


@router.post('/classes',status_code=201)
def create_class(data: ClassInput, admin=Depends(admin_user), session=Depends(db_session)):
    if session.scalar(select(ClassRoom.id).where(ClassRoom.name==data.name)) is not None:
        raise AppError('CLASS_NAME_EXISTS','班级名称已存在，请使用不同名称',409)
    row=ClassRoom(name=data.name); session.add(row)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if 'uq_classes_name' in str(error.orig):
            raise AppError('CLASS_NAME_EXISTS','班级名称已存在，请使用不同名称',409) from None
        raise
    return {'id':row.id,'name':row.name,'status':row.status}


@router.get('/users')
def users(class_id: int|None=Query(None,gt=0), page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100), admin=Depends(admin_user), session=Depends(db_session)):
    query=select(User)
    if class_id: query=query.where(User.class_id==class_id)
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.scalars(query.order_by(User.id).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[user_data(r) for r in rows], 'total':total,'page':page,'page_size':page_size}
