from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
StudentNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[A-Za-z0-9]{1,32}$')]
Password = Annotated[str, StringConstraints(min_length=6, max_length=128)]


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    student_no: StudentNumber
    password: Password


class ClassInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def user_data(user):
    return {key: getattr(user, key) for key in ('id','name','student_no','class_id','role','status')}
