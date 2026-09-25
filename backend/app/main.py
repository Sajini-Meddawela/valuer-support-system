from contextlib import asynccontextmanager

from io import BytesIO

from pathlib import Path

import shutil

import warnings

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse, Response

from PIL import Image, ImageOps, UnidentifiedImageError

from sqlalchemy import delete, select

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session

from sqlalchemy.orm.exc import StaleDataError

from .config import settings

from .models import (

    Base,

    engine,

    get_db,

    User,

    Report,

    Bank,

    Asset,

    Event,

    DriveConnection,

    now,

    uid,

)

from .schemas import Credentials, Valuer, BankData, ReportData, SaveReport, Approval, Revision

from .security import current_user, hasher, dummy_hash, token_for, throttle

from .calculations import calculate, review_issues

from .maps import map_image

from .reporting import docx_bytes, pdf_bytes, archive

import jwt

from googleapiclient.discovery import build

from googleapiclient.errors import HttpError

from .google_drive import (

    oauth_flow,

    create_oauth_state,

    read_oauth_state,

    encrypt_refresh_token,

    decrypt_refresh_token,

    create_root_folder,

    drive_service,

    create_drive_folder,

    ensure_report_folder,

    DriveUploadError,

    upload_bytes,

    upload_jpeg,

    find_file_id,

    download_file_bytes,

    delete_drive_file,

)

@asynccontextmanager

async def lifespan(app):

    Base.metadata.create_all(engine)

    yield

app = FastAPI(title='Valuer Support API', version='1.0.0', lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,

                   allow_methods=['GET', 'POST', 'PUT', 'DELETE'],

                   allow_headers=['Authorization', 'Content-Type'])

@app.middleware('http')

async def private_responses(request: Request, call_next):

    length = request.headers.get('content-length')

    if length and (not length.isdigit() or int(length) > 12 * 1024 * 1024):

        return JSONResponse({'detail': 'Request is too large.'}, status_code=413)

    response = await call_next(request)

    response.headers['Cache-Control'] = 'no-store'

    response.headers['X-Content-Type-Options'] = 'nosniff'

    response.headers['Referrer-Policy'] = 'no-referrer'

    return response

@app.exception_handler(StaleDataError)

async def stale_handler(request, exc):

    return JSONResponse({'detail': 'This report changed in another tab. Reload before editing.'}, status_code=409)

def owned(db, report_id, user):

    report = db.get(Report, report_id)

    if not report or report.owner_id != user.id:

        raise HTTPException(404, 'Report not found.')

    return report

def editable(report, revision):

    if report.status == 'final':

        raise HTTPException(409, 'Final reports are locked. Create a revised copy.')

    if report.revision != revision:

        raise HTTPException(409, 'This report changed. Reload before saving.')

def log_event(db, report, user, action):

    db.add(Event(report_id=report.id, actor_id=user.id, action=action,

                 revision=report.revision, snapshot=report.data))

def result(report):

    return {'id': report.id, 'status': report.status, 'revision': report.revision,

            'updated_at': report.updated_at, 'data': report.data}

def assets_for(db, report_id):

    return list(db.scalars(select(Asset).where(Asset.report_id == report_id).order_by(Asset.id)))

def connected_drive(db: Session, user: User):

    connection = db.get(DriveConnection, user.id)

    if (

        not connection

        or not connection.encrypted_refresh_token

        or not connection.root_folder_id

    ):

        raise HTTPException(

            409,

            'Connect Google Drive before using report file storage.'

        )

    try:

        refresh_token = decrypt_refresh_token(

            connection.encrypted_refresh_token

        )

        service = drive_service(refresh_token)

    except Exception as exc:

        raise HTTPException(

            409,

            'Google Drive authorization is unavailable. Reconnect Google Drive.'

        ) from exc

    return service, connection

def photo_loader_for(service):

    cache: dict[str, bytes] = {}

    def load(file_id: str):

        if file_id not in cache:

            try:

                cache[file_id] = download_file_bytes(

                    service,

                    file_id,

                )

            except HttpError as exc:

                if exc.resp.status == 404:

                    raise HTTPException(

                        404,

                        'A report photograph is missing from Google Drive.'

                    ) from exc

                raise HTTPException(

                    502,

                    'Could not retrieve a photograph from Google Drive.'

                ) from exc

        return cache[file_id]

    return load

@app.get('/api/health')

def health():

    return {'status': 'ok'}

@app.get('/api/config')

def config():

    return {'registration': settings.allow_registration, 'maps_configured': bool(settings.google_maps_api_key),

            'map_export_allowed': settings.map_report_export_allowed,

            'pdf_available': bool(shutil.which(settings.soffice_path))}

@app.post('/api/auth/register', status_code=201)

def register(body: Credentials, request: Request, db: Session = Depends(get_db)):

    if not settings.allow_registration:

        raise HTTPException(403, 'Registration is closed. Contact your administrator.')

    throttle('register:' + request.client.host, 5, 3600)

    user = User(email=body.email, password_hash=hasher.hash(body.password), profile=Valuer().model_dump())

    db.add(user)

    try:

        db.commit()

    except IntegrityError:

        db.rollback()

        raise HTTPException(409, 'An account already exists for this email.')

    return {'access_token': token_for(user), 'token_type': 'bearer'}

@app.post('/api/auth/login')

def login(body: Credentials, request: Request, db: Session = Depends(get_db)):

    throttle('login-ip:' + request.client.host, 30, 300)

    throttle('login-email:' + body.email, 10, 300)

    user = db.scalar(select(User).where(User.email == body.email))

    valid = hasher.verify(body.password, user.password_hash if user else dummy_hash)

    if not user or not valid:

        raise HTTPException(401, 'Incorrect email or password.')

    return {'access_token': token_for(user), 'token_type': 'bearer'}

@app.get('/api/profile')

def profile(user: User = Depends(current_user)):

    return user.profile

@app.put('/api/profile')

def save_profile(body: Valuer, user: User = Depends(current_user), db: Session = Depends(get_db)):

    user.profile = body.model_dump(mode='json'); db.commit()

    return user.profile

@app.get('/api/banks')

def banks(user: User = Depends(current_user), db: Session = Depends(get_db)):

    return [{'id': x.id, **x.data} for x in db.scalars(select(Bank).where(Bank.owner_id == user.id))]

@app.post('/api/banks', status_code=201)

def add_bank(body: BankData, user: User = Depends(current_user), db: Session = Depends(get_db)):

    bank = Bank(owner_id=user.id, data=body.model_dump(mode='json')); db.add(bank); db.commit()

    return {'id': bank.id, **bank.data}

@app.put('/api/banks/{bank_id}')

def edit_bank(bank_id: str, body: BankData, user: User = Depends(current_user), db: Session = Depends(get_db)):

    bank = db.get(Bank, bank_id)

    if not bank or bank.owner_id != user.id:

        raise HTTPException(404, 'Bank profile not found.')

    bank.data = body.model_dump(mode='json'); db.commit()

    return {'id': bank.id, **bank.data}

@app.get('/api/reports')

def reports(user: User = Depends(current_user), db: Session = Depends(get_db)):

    return [result(x) for x in db.scalars(select(Report).where(Report.owner_id == user.id).order_by(Report.updated_at.desc()).limit(200))]

@app.post('/api/reports', status_code=201)

def new_report(user: User = Depends(current_user), db: Session = Depends(get_db)):

    data = ReportData(valuer=Valuer(**user.profile))

    report = Report(owner_id=user.id, data=data.model_dump(mode='json'))

    db.add(report); db.flush(); log_event(db, report, user, 'created'); db.commit()

    return result(report)

@app.get('/api/reports/{report_id}')

def get_report(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    return result(owned(db, report_id, user))

@app.delete('/api/reports/{report_id}', status_code=204)
def delete_report(
    report_id: str,
    revision: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = owned(db, report_id, user)

    if report.status != 'draft':
        raise HTTPException(
            409,
            'Only draft reports can be deleted. Final or review reports must be kept.',
        )

    if report.revision != revision:
        raise HTTPException(
            409,
            'This report changed. Reload before deleting it.',
        )

    drive_file_ids = [
        asset.filename
        for asset in assets_for(db, report_id)
    ]

    db.execute(
        delete(Event).where(Event.report_id == report_id)
    )
    db.execute(
        delete(Asset).where(Asset.report_id == report_id)
    )
    db.delete(report)
    db.commit()

    # Remove Drive files only if no other report still references them.
    connection = db.get(DriveConnection, user.id)
    service = None

    if connection and connection.encrypted_refresh_token:
        try:
            service = drive_service(
                decrypt_refresh_token(
                    connection.encrypted_refresh_token
                )
            )
        except Exception:
            service = None

    if service:
        for drive_file_id in set(drive_file_ids):
            still_referenced = db.scalar(
                select(Asset.id)
                .where(Asset.filename == drive_file_id)
                .limit(1)
            )

            if not still_referenced:
                try:
                    delete_drive_file(
                        service,
                        drive_file_id,
                    )
                except Exception:
                    # DB deletion already succeeded; Drive cleanup is best-effort.
                    pass

    return Response(status_code=204)

@app.put('/api/reports/{report_id}')

def save_report(report_id: str, body: SaveReport, user: User = Depends(current_user), db: Session = Depends(get_db)):

    report = owned(db, report_id, user); editable(report, body.revision)

    report.data = body.data.model_dump(mode='json')

    report.status = 'draft'; report.revision += 1; report.updated_at = now()

    log_event(db, report, user, 'saved'); db.commit()

    return result(report)

@app.post('/api/reports/{report_id}/calculate')

def calculate_report(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    data = ReportData(**owned(db, report_id, user).data)

    try:

        return {'calculation': calculate(data), 'issues': review_issues(data)}

    except ValueError as exc:

        raise HTTPException(422, str(exc))

@app.post('/api/reports/{report_id}/review')

def review(report_id: str, body: Revision, user: User = Depends(current_user), db: Session = Depends(get_db)):

    report = owned(db, report_id, user); editable(report, body.revision)

    issues = review_issues(ReportData(**report.data))

    if issues:

        raise HTTPException(422, {'message': 'Complete these fields before review.', 'issues': issues})

    report.status = 'review'; report.revision += 1; report.updated_at = now()

    log_event(db, report, user, 'submitted for review'); db.commit()

    return result(report)

@app.post('/api/reports/{report_id}/finalise')
def finalise(
    report_id: str,
    body: Approval,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    throttle('final:' + user.id, 5)

    report = owned(db, report_id, user)
    editable(report, body.revision)

    if report.status != 'review':
        raise HTTPException(
            409,
            'Submit the saved report for review before approving it.',
        )

    data = ReportData(**report.data)

    if review_issues(data):
        raise HTTPException(
            422,
            'Report validation failed.',
        )

    original_revision = report.revision
    user_id = user.id

    assets = assets_for(db, report.id)

    connection = db.get(
        DriveConnection,
        user_id,
    )

    if (
        not connection
        or not connection.encrypted_refresh_token
        or not connection.root_folder_id
    ):
        raise HTTPException(
            409,
            'Connect Google Drive before finalising a report.',
        )

    encrypted_refresh_token = connection.encrypted_refresh_token
    root_folder_id = connection.root_folder_id

    # End the PostgreSQL transaction before slow LibreOffice/Drive work.
    # This prevents Supabase from closing an idle checked-out connection.
    db.commit()

    try:
        service = drive_service(
            decrypt_refresh_token(
                encrypted_refresh_token
            )
        )
    except Exception as exc:
        raise HTTPException(
            409,
            (
                'Google Drive authorization is unavailable. '
                'Reconnect Google Drive.'
            ),
        ) from exc

    photo_loader = (
        photo_loader_for(service)
        if assets
        else None
    )

    final_folder_id = None

    try:
        artifacts = archive(
            data,
            assets,
            photo_loader=photo_loader,
        )

        report_folder_id = ensure_report_folder(
            service,
            root_folder_id,
            report_id,
        )

        final_folder_id = create_drive_folder(
            service,
            report_folder_id,
            'Final',
        )

        upload_bytes(
            service,
            final_folder_id,
            'report.docx',
            artifacts['docx'],
            (
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )

        upload_bytes(
            service,
            final_folder_id,
            'report.pdf',
            artifacts['pdf'],
            'application/pdf',
        )

        upload_bytes(
            service,
            final_folder_id,
            'manifest.json',
            artifacts['manifest'],
            'application/json',
        )

    except DriveUploadError as exc:
        if final_folder_id:
            try:
                delete_drive_file(
                    service,
                    final_folder_id,
                )
            except Exception:
                pass

        raise HTTPException(
            504,
            (
                'The report was generated, but Google Drive upload '
                'timed out. Please try Approve & lock again.'
            ),
        ) from exc

    except HttpError as exc:
        if final_folder_id:
            try:
                delete_drive_file(
                    service,
                    final_folder_id,
                )
            except Exception:
                pass

        raise HTTPException(
            502,
            'Could not save the final report files to Google Drive.',
        ) from exc

    except Exception:
        if final_folder_id:
            try:
                delete_drive_file(
                    service,
                    final_folder_id,
                )
            except Exception:
                pass
        raise

    # Reacquire the report using a fresh Supabase connection.
    report = db.get(
        Report,
        report_id,
    )

    if (
        not report
        or report.owner_id != user_id
    ):
        try:
            delete_drive_file(
                service,
                final_folder_id,
            )
        except Exception:
            pass

        raise HTTPException(
            404,
            'Report not found.',
        )

    if (
        report.status != 'review'
        or report.revision != original_revision
    ):
        try:
            delete_drive_file(
                service,
                final_folder_id,
            )
        except Exception:
            pass

        try:
            db.rollback()
        except Exception:
            pass

        raise HTTPException(
            409,
            (
                'This report changed while the final files were being '
                'generated. Reload and approve the latest version.'
            ),
        )

    try:
        report.status = 'final'
        report.revision += 1
        report.updated_at = now()
        report.final_key = final_folder_id

        fresh_user = db.get(
            User,
            user_id,
        )

        if not fresh_user:
            raise HTTPException(
                404,
                'User not found.',
            )

        log_event(
            db,
            report,
            fresh_user,
            'approved and archived',
        )

        db.commit()

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

        try:
            delete_drive_file(
                service,
                final_folder_id,
            )
        except Exception:
            pass

        raise

    return result(report)

@app.post('/api/reports/{report_id}/copy', status_code=201)

def copy_report(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    source = owned(db, report_id, user)

    data = ReportData(**source.data)

    # A revision of the SAME property. UI explicitly distinguishes this from a new property.

    data.assignment.reference += ' / revision'

    data.assignment.report_date = None

    report = Report(owner_id=user.id, data=data.model_dump(mode='json'))

    db.add(report); db.flush()

    for asset in assets_for(db, source.id):

        db.add(Asset(report_id=report.id, caption=asset.caption, filename=asset.filename))

    log_event(db, report, user, 'revision copied from ' + source.id); db.commit()

    return result(report)

@app.get('/api/reports/{report_id}/history')

def history(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    owned(db, report_id, user)

    return [{'id': x.id, 'action': x.action, 'revision': x.revision, 'created_at': x.created_at}

            for x in db.scalars(select(Event).where(Event.report_id == report_id).order_by(Event.created_at.desc()))]

@app.get('/api/reports/{report_id}/history/{event_id}')

def history_data(report_id: str, event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    owned(db, report_id, user)

    event = db.get(Event, event_id)

    if not event or event.report_id != report_id:

        raise HTTPException(404, 'Version not found.')

    return event.snapshot

@app.get('/api/reports/{report_id}/map')

def map_preview(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    throttle('map:' + user.id, 10)

    report = owned(db, report_id, user)

    return Response(map_image(ReportData(**report.data).property), media_type='image/png')

@app.get('/api/reports/{report_id}/photos')

def photos(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):

    owned(db, report_id, user)

    return [{'id': x.id, 'caption': x.caption} for x in assets_for(db, report_id)]

@app.post('/api/reports/{report_id}/photos', status_code=201)
async def upload_photo(
    report_id: str,
    revision: int = Form(...),
    caption: str = Form(''),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = owned(db, report_id, user)
    editable(report, revision)

    if len(assets_for(db, report_id)) >= 12:
        raise HTTPException(
            422,
            'A report may contain up to 12 photographs.',
        )

    if len(caption) > 300:
        raise HTTPException(
            422,
            'Caption must be 300 characters or fewer.',
        )

    raw = await file.read(10 * 1024 * 1024 + 1)
    await file.close()

    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(
            413,
            'Photographs must be 10 MB or smaller.',
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                'error',
                Image.DecompressionBombWarning,
            )

            with Image.open(BytesIO(raw)) as opened:
                if (
                    opened.format not in ['JPEG', 'PNG']
                    or opened.width * opened.height > 25_000_000
                ):
                    raise ValueError()

                im = ImageOps.exif_transpose(opened).convert('RGB')
                im.thumbnail((2000, 2000))

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            422,
            'Upload a valid JPEG/PNG photograph under 25 megapixels.',
        )

    output = BytesIO()

    try:
        im.save(
            output,
            'JPEG',
            quality=90,
        )
        photo_bytes = output.getvalue()
    finally:
        im.close()

    service, connection = connected_drive(
        db,
        user,
    )

    drive_file_id = None

    try:
        report_folder_id = ensure_report_folder(
            service,
            connection.root_folder_id,
            report.id,
        )

        drive_filename = uid() + '.jpg'

        drive_file_id = upload_jpeg(
            service,
            report_folder_id,
            drive_filename,
            photo_bytes,
        )

    except HttpError as exc:
        raise HTTPException(
            502,
            'Could not upload the photograph to Google Drive.',
        ) from exc

    asset = Asset(
        report_id=report_id,
        caption=caption,
        # Step 7: filename now stores the Google Drive file ID.
        filename=drive_file_id,
    )
    db.add(asset)

    report.status = 'draft'
    report.revision += 1
    report.updated_at = now()

    log_event(
        db,
        report,
        user,
        'photo added',
    )

    try:
        db.commit()

    except Exception:
        db.rollback()

        if drive_file_id:
            try:
                delete_drive_file(
                    service,
                    drive_file_id,
                )
            except Exception:
                pass

        raise

    return result(report)

@app.get('/api/reports/{report_id}/photos/{asset_id}')
def get_photo(
    report_id: str,
    asset_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    owned(
        db,
        report_id,
        user,
    )

    asset = db.get(
        Asset,
        asset_id,
    )

    if not asset or asset.report_id != report_id:
        raise HTTPException(
            404,
            'Photograph not found.',
        )

    service, _ = connected_drive(
        db,
        user,
    )

    try:
        raw = download_file_bytes(
            service,
            asset.filename,
        )

    except HttpError as exc:
        if exc.resp.status == 404:
            raise HTTPException(
                404,
                'Photograph file is missing from Google Drive.',
            ) from exc

        raise HTTPException(
            502,
            'Could not retrieve the photograph from Google Drive.',
        ) from exc

    return Response(
        raw,
        media_type='image/jpeg',
    )

@app.delete('/api/reports/{report_id}/photos/{asset_id}')

def delete_photo(report_id: str, asset_id: str, revision: int,

                 user: User = Depends(current_user), db: Session = Depends(get_db)):

    report = owned(db, report_id, user); editable(report, revision)

    asset = db.get(Asset, asset_id)

    if not asset or asset.report_id != report_id:

        raise HTTPException(404, 'Photograph not found.')

    db.delete(asset)

    report.status = 'draft'; report.revision += 1; report.updated_at = now()

    log_event(db, report, user, 'photo removed'); db.commit()

    # Physical files may be referenced by older revisions; retention cleanup is an operator task.

    return result(report)

@app.get('/api/reports/{report_id}/export/{kind}')
def export(
    report_id: str,
    kind: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    throttle(
        'export:' + user.id,
        10,
    )

    if kind not in ('docx', 'pdf'):
        raise HTTPException(
            404,
            'Unknown export format.',
        )

    report = owned(
        db,
        report_id,
        user,
    )

    report_status = report.status
    report_data = dict(report.data)
    final_key = report.final_key
    user_id = user.id

    media = (
        'application/pdf'
        if kind == 'pdf'
        else (
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document'
        )
    )

    filename = (
        f'valuation-{report.id[:8]}-'
        f'{report_status}.{kind}'
    )

    assets = assets_for(
        db,
        report_id,
    )

    encrypted_refresh_token = None

    if report_status == 'final' or assets:
        connection = db.get(
            DriveConnection,
            user_id,
        )

        if (
            not connection
            or not connection.encrypted_refresh_token
            or not connection.root_folder_id
        ):
            raise HTTPException(
                409,
                'Connect Google Drive before exporting this report.',
            )

        encrypted_refresh_token = (
            connection.encrypted_refresh_token
        )

    # Do not hold a Supabase transaction open while downloading Drive
    # photos/files or while LibreOffice converts the DOCX to PDF.
    db.commit()

    service = None

    if encrypted_refresh_token:
        try:
            service = drive_service(
                decrypt_refresh_token(
                    encrypted_refresh_token
                )
            )
        except Exception as exc:
            raise HTTPException(
                409,
                (
                    'Google Drive authorization is unavailable. '
                    'Reconnect Google Drive.'
                ),
            ) from exc

    if report_status == 'final':
        if not final_key:
            raise HTTPException(
                404,
                'Final report files are unavailable.',
            )

        try:
            drive_file_id = find_file_id(
                service,
                final_key,
                f'report.{kind}',
            )

            if not drive_file_id:
                raise HTTPException(
                    404,
                    (
                        'The final report file is missing '
                        'from Google Drive.'
                    ),
                )

            raw = download_file_bytes(
                service,
                drive_file_id,
            )

        except HttpError as exc:
            if exc.resp.status == 404:
                raise HTTPException(
                    404,
                    (
                        'The final report file is missing '
                        'from Google Drive.'
                    ),
                ) from exc

            raise HTTPException(
                502,
                'Could not retrieve the final report from Google Drive.',
            ) from exc

        return Response(
            raw,
            media_type=media,
            headers={
                'Content-Disposition': (
                    f'attachment; filename="{filename}"'
                )
            },
        )

    photo_loader = (
        photo_loader_for(service)
        if assets
        else None
    )

    try:
        raw = docx_bytes(
            ReportData(**report_data),
            report_status,
            assets,
            photo_loader=photo_loader,
        )
    except ValueError as exc:
        raise HTTPException(
            422,
            str(exc),
        )

    if kind == 'pdf':
        raw = pdf_bytes(raw)

    return Response(
        raw,
        media_type=media,
        headers={
            'Content-Disposition': (
                f'attachment; filename="{filename}"'
            )
        },
    )

@app.get('/api/google-drive/status')

def google_drive_status(

    user: User = Depends(current_user),

    db: Session = Depends(get_db),

):

    connection = db.get(DriveConnection, user.id)

    return {

        'connected': bool(

            connection

            and connection.encrypted_refresh_token

            and connection.root_folder_id

        )

    }

@app.get('/api/google-drive/connect')

def google_drive_connect(

    user: User = Depends(current_user),

):

    state = create_oauth_state(user.id)

    flow = oauth_flow(state)

    authorization_url, _ = flow.authorization_url(

        access_type='offline',

        include_granted_scopes='true',

        prompt='consent',

    )

    return {

        'authorization_url': authorization_url

    }

@app.get('/api/google/callback')

def google_drive_callback(

    request: Request,

    code: str,

    state: str,

    db: Session = Depends(get_db),

):

    # Validate the OAuth state and recover the Valuer Support user.

    try:

        user_id = read_oauth_state(state)

    except jwt.InvalidTokenError:

        raise HTTPException(

            400,

            'Invalid or expired Google authorization request.'

        )

    user = db.get(User, user_id)

    if not user:

        raise HTTPException(

            404,

            'User not found.'

        )

    # IMPORTANT: create the OAuth flow before fetch_token().

    flow = oauth_flow(state)

    try:

        flow.fetch_token(

            authorization_response=str(request.url)

        )

    except Exception as exc:

        print("GOOGLE OAUTH ERROR:", repr(exc))

        raise HTTPException(

            400,

            'Google authorization could not be completed.'

        )

    credentials = flow.credentials

    if not credentials.refresh_token:

        raise HTTPException(

            400,

            'Google did not provide a refresh token. Reconnect Google Drive.'

        )

    # Create an authenticated Google Drive client.

    service = build(

        'drive',

        'v3',

        credentials=credentials,

        cache_discovery=False,

    )

    connection = db.get(DriveConnection, user.id)

    if connection is None:

        # First connection: create the main Drive folder.

        folder_id = create_root_folder(service)

        connection = DriveConnection(

            owner_id=user.id,

            encrypted_refresh_token=encrypt_refresh_token(

                credentials.refresh_token

            ),

            root_folder_id=folder_id,

        )

        db.add(connection)

    else:

        # Reconnecting the same account.

        connection.encrypted_refresh_token = encrypt_refresh_token(

            credentials.refresh_token

        )

        if not connection.root_folder_id:

            connection.root_folder_id = create_root_folder(service)

    db.commit()

    return {

        'connected': True,

        'message': (

            'Google Drive connected successfully. '

            'You may close this tab.'

        )

    }

from fastapi.staticfiles import StaticFiles

frontend_dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'

if (frontend_dist / 'index.html').is_file():

    app.mount('/', StaticFiles(directory=frontend_dist, html=True), name='frontend')