import logging
import time
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger("attendance.requests")


def error_response(request, code, message, status):
    return JSONResponse({"error": {"code": code, "message": message,
                                   "request_id": request.state.request_id}}, status_code=status)


def install_handlers(app):
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
