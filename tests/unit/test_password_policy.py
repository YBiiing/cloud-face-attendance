import pytest
from pydantic import ValidationError
from app.schemas.accounts import LoginInput
from app.api.registration import RegistrationInput


@pytest.mark.parametrize('length,valid',[(5,False),(6,True),(128,True),(129,False)])
def test_six_character_password_boundary(length,valid):
    data={'student_no':'TEST001','password':'a'*length}
    for model,values in [(LoginInput,data),(RegistrationInput,{**data,'name':'测试','class_id':1})]:
        if valid:assert model(**values).password=='a'*length
        else:
            with pytest.raises(ValidationError):model(**values)
