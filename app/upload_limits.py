from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    """Bound incoming bodies before multipart parsing, including chunked uploads."""
    def __init__(self,app,max_bytes=9*1024*1024):
        self.app=app;self.max_bytes=max_bytes

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in {'POST','PUT','PATCH'}:
            return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        try: advertised=int(headers.get(b'content-length',b'0'))
        except ValueError: advertised=self.max_bytes+1
        async def reject():
            response=JSONResponse({'error':{'code':'IMAGE_TOO_LARGE','message':'请求内容超过大小限制','request_id':scope.get('state',{}).get('request_id','')}},status_code=413)
            await response(scope,receive,send)
        if advertised>self.max_bytes: return await reject()
        chunks=[];total=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            total+=len(message.get('body',b''))
            if total>self.max_bytes: return await reject()
            chunks.append(message.get('body',b''))
            if not message.get('more_body',False): break
        body=b''.join(chunks);del chunks
        consumed=False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
