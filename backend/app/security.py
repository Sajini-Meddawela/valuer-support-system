from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .models import User, get_db

hasher = PasswordHash.recommended()
dummy_hash = hasher.hash('not-a-real-user-password')
bearer = HTTPBearer(auto_error=False)
hits = defaultdict(deque)
lock = Lock()


def throttle(key, limit, seconds=60):
    # Single-process limiter. Deploy one API worker; use a gateway/shared limiter to scale.
    with lock:
        now = monotonic()
        if len(hits) > 10000:
            hits.clear()
        q = hits[key]
        while q and q[0] <= now - seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, 'Too many requests. Please try again later.')
        q.append(now)


def token_for(user):
    return jwt.encode({'sub': user.id, 'exp': datetime.now(timezone.utc) + timedelta(minutes=60),
                       'iat': datetime.now(timezone.utc), 'iss': 'valuer-support'}, settings.jwt_secret, algorithm='HS256')


def current_user(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    try:
        if auth is None:
            raise ValueError()
        payload = jwt.decode(auth.credentials, settings.jwt_secret, algorithms=['HS256'],
                             issuer='valuer-support', options={'require': ['exp', 'sub', 'iat']})
        user = db.get(User, payload['sub'])
        if not user:
            raise ValueError()
        return user
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, 'Please sign in again.')
