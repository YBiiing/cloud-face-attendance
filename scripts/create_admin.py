from getpass import getpass
from sqlalchemy import select
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.models import User
from app.security import hash_password
from app.schemas.accounts import LoginInput


def main():
    number=input('管理员学号/账号: ').strip()
    name=input('姓名: ').strip()
    password=getpass('密码（10–128 字符）: ')
    if password != getpass('再次输入密码: '): raise SystemExit('两次密码不一致')
    LoginInput(student_no=number,password=password)
    if not 1 <= len(name) <= 50: raise SystemExit('姓名长度不合法')
    engine=make_engine(Settings.from_env())
    try:
        with make_session_factory(engine).begin() as session:
            if session.scalar(select(User.id).where(User.student_no==number)):
                raise SystemExit('账号已存在，未修改任何资料')
            session.add(User(student_no=number,name=name,password_hash=hash_password(password),role='ADMIN',status='ACTIVE'))
        print('管理员创建成功')
    finally: engine.dispose()


if __name__=='__main__': main()
