from typing import Literal

from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["cloud-face-attendance"] = "cloud-face-attendance"
