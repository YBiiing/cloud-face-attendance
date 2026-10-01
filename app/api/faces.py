from fastapi import APIRouter,Depends,Request,Query
from fastapi.responses import FileResponse,Response
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from app import clock
from app.models import User,FaceSample,FaceLibraryState
from app.errors import AppError
from app.security import current_user,db_session,rate_limit
from app.services.forms import photo_form
from app.services.uploads import receive_photo,stored_path
from app.services.tasks import validate_key,request_digest,find_replay,new_task,accepted,dispatch

router=APIRouter(prefix='/api/faces',tags=['faces'])


def check_owner(actor,owner):
    if actor.role!='ADMIN' and actor.id!=owner: raise AppError('NOT_FOUND','照片不存在或无权访问',404)


@router.get('')
def list_faces(user_id:int|None=Query(None,gt=0),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),actor=Depends(current_user),session=Depends(db_session)):
    owner=user_id or actor.id;check_owner(actor,owner)
    query=select(FaceSample).where(FaceSample.user_id==owner,FaceSample.status=='ACTIVE')
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.scalars(query.order_by(FaceSample.id).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[{'id':r.id,'user_id':r.user_id,'created_at':r.created_at,'image_url':f'/api/faces/{r.id}/image'} for r in rows],'total':total,'page':page,'page_size':page_size}


@router.get('/{face_id}/image')
def image(face_id:int,request:Request,actor=Depends(current_user),session=Depends(db_session)):
    face=session.get(FaceSample,face_id)
    if not face or face.status!='ACTIVE': raise AppError('NOT_FOUND','照片不存在',404)
    check_owner(actor,face.user_id)
    path=stored_path(request.app.state.settings.storage_dir,face.image_path)
    if not path.is_file(): raise AppError('NOT_FOUND','照片文件不可用',404)
    # Validate format from the file bytes, never from a client-supplied suffix.
    with path.open('rb') as source: is_png=source.read(8)==b'\x89PNG\r\n\x1a\n'
    return FileResponse(path,media_type='image/png' if is_png else 'image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.post('',status_code=202)
async def add_face(request:Request,actor=Depends(current_user),session=Depends(db_session)):
    rate_limit(request,'face-upload')
    key=validate_key(request.headers.get('idempotency-key'))
    form=await photo_form(request,{'photo','replace_id','user_id'})
    uploaded=None;retained=False;settings=request.app.state.settings
    try:
        try:
            owner=int(form.get('user_id',actor.id));replace_id=int(form['replace_id']) if form.get('replace_id') else None
            if owner<1 or (replace_id is not None and replace_id<1): raise ValueError
        except (ValueError,TypeError): raise AppError('INVALID_REQUEST','人员或照片编号不合法',422) from None
        check_owner(actor,owner)
        user=session.get(User,owner)
        if not user or user.status!='ACTIVE': raise AppError('NOT_FOUND','人员不存在或未激活',404)
        uploaded=await receive_photo(form['photo'],settings.storage_dir)
        scope='faces:'+str(actor.id)
        digest=request_digest(settings.app_secret,{'owner':owner,'replace_id':replace_id,'photo':uploaded.digest})
        existing=find_replay(session,scope,key,digest)
        if existing:return accepted(existing,settings.app_secret,key)
        if replace_id:
            old=session.get(FaceSample,replace_id)
            if not old or old.user_id!=owner or old.status!='ACTIVE': raise AppError('NOT_FOUND','被替换照片不存在',404)
        task=new_task(settings.app_secret,scope,key,digest,'FACE',owner,uploaded.path,{'replace_id':replace_id})
        # Preserve the photo once COMMIT starts: a lost acknowledgement is not a rollback.
        session.add(task);session.flush();retained=True;session.commit();dispatch(task.id)
        return accepted(task,settings.app_secret,key)
    except IntegrityError:
        session.rollback();existing=find_replay(session,scope,key,digest)
        if existing:return accepted(existing,settings.app_secret,key)
        raise AppError('CONFLICT','照片更新冲突，请刷新后重试',409) from None
    finally:
        await form.close()
        if uploaded and not retained:stored_path(settings.storage_dir,uploaded.path).unlink(missing_ok=True)


@router.delete('/{face_id}',status_code=204)
def delete_face(face_id:int,actor=Depends(current_user),session=Depends(db_session)):
    state=session.scalar(select(FaceLibraryState).where(FaceLibraryState.id==1).with_for_update())
    face=session.scalar(select(FaceSample).where(FaceSample.id==face_id).with_for_update())
    if not face:raise AppError('NOT_FOUND','照片不存在',404)
    check_owner(actor,face.user_id)
    if face.status=='ACTIVE':
        face.status='DISABLED';state.version+=1;state.updated_at=clock.utc_now()
    session.commit()
    return Response(status_code=204)
