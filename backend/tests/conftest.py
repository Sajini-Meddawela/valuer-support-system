import os
from tempfile import TemporaryDirectory
import pytest

tmp = TemporaryDirectory(prefix='valuer-tests-')
os.environ['JWT_SECRET'] = 'test-only-secret-not-for-deployment-' + 'x' * 32
os.environ['DATA_DIR'] = tmp.name
os.environ['DATABASE_URL'] = 'sqlite:///' + tmp.name + '/test.db'
os.environ['ALLOW_REGISTRATION'] = 'true'
os.environ['GOOGLE_MAPS_API_KEY'] = ''
os.environ['MAP_REPORT_EXPORT_ALLOWED'] = 'false'

from fastapi.testclient import TestClient
from app.main import app
from app.models import Base, engine
from app.security import hits


@pytest.fixture
def client():
    Base.metadata.drop_all(engine); hits.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    res = client.post('/api/auth/register', json={'email':'valuer@example.test','password':'sample-password-123'})
    assert res.status_code == 201
    return {'Authorization':'Bearer ' + res.json()['access_token']}
