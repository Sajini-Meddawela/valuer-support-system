"""Run from backend: python -m scripts.create_user. Used when registration is closed."""
import getpass
from app.models import Base, engine, Session, User
from app.schemas import Credentials, Valuer
from app.security import hasher
from sqlalchemy.exc import IntegrityError

credentials = Credentials(email=input('Email: '), password=getpass.getpass('Password (12+ characters): '))
Base.metadata.create_all(engine)
with Session() as db:
    db.add(User(email=credentials.email, password_hash=hasher.hash(credentials.password), profile=Valuer().model_dump()))
    try:
        db.commit(); print('User created.')
    except IntegrityError:
        db.rollback(); raise SystemExit('An account already exists for that email.')
