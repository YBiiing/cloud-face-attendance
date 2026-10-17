class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retry_after: int | None = None):
        self.code, self.message, self.status = code, message, status
        self.retry_after = retry_after
        super().__init__(code)
