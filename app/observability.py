import logging
import time
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from app.errors import AppError
from app.face.types import FaceError
from sqlalchemy.exc import DBAPIError,TimeoutError as PoolTimeout

logger = logging.getLogger("attendance.requests")


def database_unavailable(error):
    if isinstance(error,PoolTimeout):return True
    if isinstance(error,DBAPIError):
        code=error.orig.args[0] if getattr(error.orig,'args',()) else None
        return error.connection_invalidated or code in {1040,1042,1043,1047,1081,1129,1130,1158,1159,1160,1161,2002,2003,2005,2006,2013,2055}
    return False


def error_response(request, code, message, status):
    return JSONResponse({"error": {"code": code, "message": message,
                                   "request_id": request.state.request_id}}, status_code=status)


def install_handlers(app):
    @app.exception_handler(FaceError)
    async def invalid_image(request, exc):
        messages={'IMAGE_TOO_LARGE':'照片超过大小限制','UNSUPPORTED_IMAGE':'请上传 JPEG 或 PNG 照片','INVALID_IMAGE':'图片损坏或无法读取'}
        status={'IMAGE_TOO_LARGE':413,'UNSUPPORTED_IMAGE':415}.get(exc.code,422)
        return error_response(request,exc.code,messages.get(exc.code,'照片不符合要求'),status)

    @app.exception_handler(AppError)
    async def business_error(request, exc):
        response=error_response(request, exc.code, exc.message, exc.status)
        if exc.retry_after is not None:response.headers['Retry-After']=str(exc.retry_after)
        return response

    @app.exception_handler(DBAPIError)
    @app.exception_handler(PoolTimeout)
    async def database_error(request,exc):
        unavailable=database_unavailable(exc)
        logger.error('database_request_failed request_id=%s exception_type=%s',request.state.request_id,type(exc).__name__)
        return error_response(request,'SERVICE_UNAVAILABLE' if unavailable else 'INTERNAL_ERROR','服务暂时不可用，请稍后重试',503 if unavailable else 500)

    @app.middleware("http")
    async def trace_request(request, call_next):
        request.state.request_id = uuid4().hex
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Do not log bodies, URLs, exception messages, SQL or credentials.
            logger.error("request_failed request_id=%s", request.state.request_id)
            response = error_response(request, "INTERNAL_ERROR", "服务暂时不可用", 500)
        response.headers["X-Request-ID"] = request.state.request_id
        route = request.scope.get("route")
        route_name = getattr(route, "name", "unmatched")
        logger.info("request_id=%s route=%s method=%s status=%s duration_ms=%.2f",
                    request.state.request_id, route_name, request.method,
                    response.status_code, (time.monotonic() - started) * 1000)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error_response(request, "INVALID_REQUEST", "请求字段不合法", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        messages = {401: "请先登录", 403: "无权访问", 404: "资源不存在", 405: "请求方法不支持"}
        return error_response(request, codes.get(exc.status_code, "REQUEST_FAILED"),
                              messages.get(exc.status_code, "请求未完成"), exc.status_code)
