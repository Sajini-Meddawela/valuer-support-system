"""Create local configuration without overwriting existing settings."""
from pathlib import Path
import secrets
import shutil

root = Path(__file__).resolve().parents[1]
target = root / 'backend' / '.env'
if target.exists():
    print('Keeping existing backend/.env.')
else:
    content = target.with_name('.env.example').read_text()
    content = content.replace('replace-with-at-least-32-random-characters', secrets.token_urlsafe(48))
    candidates = [Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                  Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe')]
    converter = shutil.which('soffice') or next((str(p) for p in candidates if p.is_file()), None)
    if converter:
        content = content.replace('SOFFICE_PATH=soffice', 'SOFFICE_PATH="' + Path(converter).as_posix() + '"')
    target.write_text(content, encoding='utf-8')
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print('Created backend/.env with a random secret; the secret is not printed.')
(root / 'backend' / 'data').mkdir(exist_ok=True)
print('Configuration ready. Follow README.md to start the application.')
