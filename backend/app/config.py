from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./data/valuer.db'
    jwt_secret: str
    data_dir: Path = Path('data')
    allow_registration: bool = True
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    google_maps_api_key: str = ''
    google_maps_signing_secret: str = ''
    map_report_export_allowed: bool = False
    soffice_path: str = 'soffice'


settings = Settings()
if len(settings.jwt_secret) < 32 or settings.jwt_secret.startswith('replace-'):
    raise RuntimeError('Set JWT_SECRET to a unique random secret of at least 32 characters.')
settings.data_dir.mkdir(parents=True, exist_ok=True)
