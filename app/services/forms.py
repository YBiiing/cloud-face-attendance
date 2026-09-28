from starlette.datastructures import UploadFile
from app.errors import AppError


async def photo_form(request,allowed):
    form=await request.form(max_files=1,max_fields=10,max_part_size=4096)
    keys=list(form.keys())
    if set(keys)-allowed or any(len(form.getlist(key))!=1 for key in keys):
        await form.close()
        raise AppError('INVALID_REQUEST','上传字段不合法',422)
    if not isinstance(form.get('photo'),UploadFile):
        await form.close()
        raise AppError('INVALID_REQUEST','请选择照片',422)
    return form
