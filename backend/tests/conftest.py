import importlib
import os
from itertools import count
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


tmp = TemporaryDirectory(
    prefix='valuer-tests-',
    ignore_cleanup_errors=True,
)

# Test-only application configuration.
# These are set before importing the FastAPI app so Settings reads them.
os.environ['JWT_SECRET'] = (
    'test-only-secret-not-for-deployment-'
    + 'x' * 32
)
os.environ['DATA_DIR'] = tmp.name
os.environ['DATABASE_URL'] = (
    'sqlite:///'
    + tmp.name
    + '/test.db'
)
os.environ['ALLOW_REGISTRATION'] = 'true'
os.environ['GOOGLE_MAPS_API_KEY'] = ''
os.environ['MAP_REPORT_EXPORT_ALLOWED'] = 'false'

# The production app requires a Google Drive connection for report files.
# CI must not contact real Google services, so the tests use a completely
# in-memory fake Drive implementation.
os.environ['GOOGLE_DRIVE_CLIENT_ID'] = 'test-client-id'
os.environ['GOOGLE_DRIVE_CLIENT_SECRET'] = 'test-client-secret'
os.environ['GOOGLE_DRIVE_REDIRECT_URI'] = (
    'http://127.0.0.1:8000/api/google/callback'
)

main_module = importlib.import_module('app.main')

from app.main import app
from app.models import (
    Base,
    DriveConnection,
    Session,
    User,
    engine,
)
from app.security import hits


class FakeDrive:
    def __init__(self):
        self.reset()

    def reset(self):
        self.files: dict[str, bytes] = {}
        self.names: dict[tuple[str, str], str] = {}
        self.report_folders: dict[str, str] = {}
        self.folders: set[str] = {'test-root'}
        self._ids = count(1)

    def new_id(self, prefix: str):
        return f'{prefix}-{next(self._ids)}'


fake_drive = FakeDrive()
fake_service = object()


def fake_decrypt_refresh_token(token: str):
    return token


def fake_drive_service(refresh_token: str):
    return fake_service


def fake_ensure_report_folder(
    service,
    root_folder_id: str,
    report_id: str,
    report_reference: str | None = None,
):
    folder_id = fake_drive.report_folders.get(
        report_id
    )

    if folder_id:
        return folder_id

    folder_id = fake_drive.new_id(
        'report-folder'
    )

    fake_drive.report_folders[
        report_id
    ] = folder_id

    fake_drive.folders.add(
        folder_id
    )

    return folder_id


def fake_sync_report_folder_name(
    service,
    root_folder_id: str,
    report_id: str,
    report_reference: str | None = None,
):
    return fake_drive.report_folders.get(
        report_id
    )


def fake_create_drive_folder(
    service,
    parent_folder_id: str,
    name: str,
):
    folder_id = fake_drive.new_id(
        'folder'
    )

    fake_drive.folders.add(
        folder_id
    )

    return folder_id


def fake_upload_bytes(
    service,
    folder_id: str,
    filename: str,
    content: bytes,
    mimetype: str,
):
    file_id = fake_drive.new_id(
        'file'
    )

    fake_drive.files[
        file_id
    ] = bytes(content)

    fake_drive.names[
        (folder_id, filename)
    ] = file_id

    return file_id


def fake_upload_jpeg(
    service,
    folder_id: str,
    filename: str,
    content: bytes,
):
    return fake_upload_bytes(
        service,
        folder_id,
        filename,
        content,
        'image/jpeg',
    )


def fake_find_file_id(
    service,
    folder_id: str,
    filename: str,
):
    return fake_drive.names.get(
        (folder_id, filename)
    )


def fake_download_file_bytes(
    service,
    file_id: str,
):
    if file_id not in fake_drive.files:
        raise RuntimeError(
            'Fake Drive file does not exist.'
        )

    return fake_drive.files[
        file_id
    ]


def fake_delete_drive_file(
    service,
    file_id: str,
):
    if file_id in fake_drive.files:
        fake_drive.files.pop(
            file_id,
            None,
        )

        for key, stored_id in list(
            fake_drive.names.items()
        ):
            if stored_id == file_id:
                fake_drive.names.pop(
                    key,
                    None,
                )

        return

    if file_id in fake_drive.folders:
        fake_drive.folders.discard(
            file_id
        )

        for key, stored_id in list(
            fake_drive.names.items()
        ):
            folder_id, _ = key

            if folder_id == file_id:
                fake_drive.files.pop(
                    stored_id,
                    None,
                )
                fake_drive.names.pop(
                    key,
                    None,
                )


@pytest.fixture(
    scope='session',
    autouse=True,
)
def cleanup_test_environment():
    """
    Close SQLAlchemy's SQLite connection pool before Windows tries to
    remove the temporary test database.
    """
    yield

    engine.dispose()

    try:
        tmp.cleanup()
    except (PermissionError, NotADirectoryError):
        # Windows can briefly retain a file handle during interpreter
        # shutdown. The database is already isolated in the OS temp folder.
        pass


@pytest.fixture
def client(monkeypatch):
    fake_drive.reset()
    hits.clear()

    Base.metadata.drop_all(
        engine
    )

    monkeypatch.setattr(
        main_module,
        'decrypt_refresh_token',
        fake_decrypt_refresh_token,
    )
    monkeypatch.setattr(
        main_module,
        'drive_service',
        fake_drive_service,
    )
    monkeypatch.setattr(
        main_module,
        'ensure_report_folder',
        fake_ensure_report_folder,
    )
    monkeypatch.setattr(
        main_module,
        'sync_report_folder_name',
        fake_sync_report_folder_name,
    )
    monkeypatch.setattr(
        main_module,
        'create_drive_folder',
        fake_create_drive_folder,
    )
    monkeypatch.setattr(
        main_module,
        'upload_bytes',
        fake_upload_bytes,
    )
    monkeypatch.setattr(
        main_module,
        'upload_jpeg',
        fake_upload_jpeg,
    )
    monkeypatch.setattr(
        main_module,
        'find_file_id',
        fake_find_file_id,
    )
    monkeypatch.setattr(
        main_module,
        'download_file_bytes',
        fake_download_file_bytes,
    )
    monkeypatch.setattr(
        main_module,
        'delete_drive_file',
        fake_delete_drive_file,
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    email = 'valuer@example.test'

    res = client.post(
        '/api/auth/register',
        json={
            'email': email,
            'password': 'sample-password-123',
        },
    )

    assert res.status_code == 201

    with Session() as db:
        user = db.scalar(
            select(User).where(
                User.email == email
            )
        )

        assert user is not None

        db.add(
            DriveConnection(
                owner_id=user.id,
                encrypted_refresh_token='test-refresh-token',
                root_folder_id='test-root',
            )
        )

        db.commit()

    return {
        'Authorization': (
            'Bearer '
            + res.json()['access_token']
        )
    }