from datetime import datetime, timedelta, timezone
from io import BytesIO
import secrets

import jwt

from cryptography.fernet import Fernet
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from .config import settings


DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
SCOPES = [DRIVE_SCOPE]

TOKEN_URI = 'https://oauth2.googleapis.com/token'
FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'

UPLOAD_CHUNK_SIZE = 1024 * 1024
UPLOAD_RETRIES = 5


class DriveUploadError(RuntimeError):
    pass



def check_configuration():
    required = [
        settings.google_drive_client_id,
        settings.google_drive_client_secret,
        settings.google_drive_redirect_uri,
        settings.google_drive_token_key,
    ]

    if not all(required):
        raise RuntimeError(
            'Google Drive integration is not configured.'
        )


def oauth_flow(state: str | None = None):
    check_configuration()

    client_config = {
        'web': {
            'client_id': settings.google_drive_client_id,
            'client_secret': settings.google_drive_client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': TOKEN_URI,
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        autogenerate_code_verifier=False,
    )

    flow.redirect_uri = settings.google_drive_redirect_uri

    return flow


def create_oauth_state(user_id: str):
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            'sub': user_id,
            'purpose': 'google-drive-oauth',
            'jti': secrets.token_urlsafe(16),
            'iat': now,
            'exp': now + timedelta(minutes=10),
            'iss': 'valuer-support-drive',
        },
        settings.jwt_secret,
        algorithm='HS256',
    )


def read_oauth_state(state: str):
    payload = jwt.decode(
        state,
        settings.jwt_secret,
        algorithms=['HS256'],
        issuer='valuer-support-drive',
        options={'require': ['sub', 'exp', 'iat']},
    )

    if payload.get('purpose') != 'google-drive-oauth':
        raise jwt.InvalidTokenError()

    return payload['sub']


def encrypt_refresh_token(token: str):
    check_configuration()

    fernet = Fernet(
        settings.google_drive_token_key.encode()
    )

    return fernet.encrypt(
        token.encode()
    ).decode()


def decrypt_refresh_token(token: str):
    check_configuration()

    fernet = Fernet(
        settings.google_drive_token_key.encode()
    )

    return fernet.decrypt(
        token.encode()
    ).decode()


def credentials_from_refresh_token(
    refresh_token: str,
):
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_drive_client_id,
        client_secret=settings.google_drive_client_secret,
        scopes=SCOPES,
    )

    credentials.refresh(
        GoogleRequest()
    )

    return credentials


def drive_service(refresh_token: str):
    credentials = credentials_from_refresh_token(
        refresh_token
    )

    return build(
        'drive',
        'v3',
        credentials=credentials,
        cache_discovery=False,
    )


def _escape_query_value(value: str):
    return (
        value
        .replace('\\', '\\\\')
        .replace("'", "\\'")
    )


def create_root_folder(service):
    metadata = {
        'name': 'Valuer Support',
        'mimeType': FOLDER_MIME_TYPE,
    }

    folder = service.files().create(
        body=metadata,
        fields='id',
    ).execute()

    return folder['id']


def create_drive_folder(
    service,
    parent_folder_id: str,
    name: str,
):
    folder = service.files().create(
        body={
            'name': name,
            'mimeType': FOLDER_MIME_TYPE,
            'parents': [parent_folder_id],
        },
        fields='id',
    ).execute()

    return folder['id']


def ensure_report_folder(
    service,
    root_folder_id: str,
    report_id: str,
):
    folder_name = f'Report {report_id}'

    safe_root = _escape_query_value(
        root_folder_id
    )
    safe_name = _escape_query_value(
        folder_name
    )

    query = (
        f"'{safe_root}' in parents and "
        f"name = '{safe_name}' and "
        f"mimeType = '{FOLDER_MIME_TYPE}' and "
        "trashed = false"
    )

    result = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id)',
        pageSize=1,
    ).execute()

    files = result.get(
        'files',
        [],
    )

    if files:
        return files[0]['id']

    return create_drive_folder(
        service,
        root_folder_id,
        folder_name,
    )


def upload_bytes(
    service,
    folder_id: str,
    filename: str,
    content: bytes,
    mimetype: str,
):
    """Upload using resumable 1 MiB chunks with retries."""
    media = MediaIoBaseUpload(
        BytesIO(content),
        mimetype=mimetype,
        chunksize=UPLOAD_CHUNK_SIZE,
        resumable=True,
    )

    request = service.files().create(
        body={
            'name': filename,
            'parents': [folder_id],
        },
        media_body=media,
        fields='id',
    )

    response = None

    try:
        while response is None:
            _, response = request.next_chunk(
                num_retries=UPLOAD_RETRIES
            )
    except Exception as exc:
        raise DriveUploadError(
            f'Google Drive upload failed for {filename}.'
        ) from exc

    if not response or not response.get('id'):
        raise DriveUploadError(
            f'Google Drive did not return a file ID for {filename}.'
        )

    return response['id']


def upload_jpeg(
    service,
    folder_id: str,
    filename: str,
    content: bytes,
):
    return upload_bytes(
        service,
        folder_id,
        filename,
        content,
        'image/jpeg',
    )


def find_file_id(
    service,
    folder_id: str,
    filename: str,
):
    safe_folder = _escape_query_value(
        folder_id
    )
    safe_filename = _escape_query_value(
        filename
    )

    query = (
        f"'{safe_folder}' in parents and "
        f"name = '{safe_filename}' and "
        "trashed = false"
    )

    result = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id)',
        pageSize=1,
    ).execute()

    files = result.get(
        'files',
        [],
    )

    if not files:
        return None

    return files[0]['id']


def download_file_bytes(
    service,
    file_id: str,
):
    request = service.files().get_media(
        fileId=file_id
    )

    output = BytesIO()

    downloader = MediaIoBaseDownload(
        output,
        request,
    )

    done = False

    while not done:
        _, done = downloader.next_chunk(num_retries=3)

    return output.getvalue()


def delete_drive_file(
    service,
    file_id: str,
):
    service.files().delete(
        fileId=file_id
    ).execute(num_retries=3)