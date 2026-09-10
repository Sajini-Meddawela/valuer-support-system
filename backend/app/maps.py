import base64
import hashlib
import hmac
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException
from .config import settings
from .schemas import Property


def map_image(p: Property):
    if not settings.google_maps_api_key:
        raise HTTPException(503, 'Map service is not configured. Ask your administrator to configure Google Maps.')
    if p.latitude is None or p.longitude is None:
        raise HTTPException(422, 'Enter and save both coordinates first.')
    point = f'{p.latitude},{p.longitude}'
    params = {'center': point, 'zoom': p.zoom, 'size': '640x360', 'scale': 2,
              'maptype': p.map_type, 'markers': f'color:red|{point}', 'key': settings.google_maps_api_key}
    if p.access_path:
        params['path'] = 'color:0x2454ddff|weight:4|' + '|'.join(f'{lat},{lng}' for lat, lng in p.access_path)
    path = '/maps/api/staticmap?' + urlencode(params)
    if settings.google_maps_signing_secret:
        secret = settings.google_maps_signing_secret
        try:
            secret_bytes = base64.urlsafe_b64decode(secret + '=' * (-len(secret) % 4))
            signature = base64.urlsafe_b64encode(hmac.new(secret_bytes, path.encode(), hashlib.sha1).digest()).decode()
        except (ValueError, TypeError):
            raise HTTPException(503, 'Invalid map signing configuration.')
        path += '&signature=' + signature
    try:
        response = httpx.get('https://maps.googleapis.com' + path, timeout=20)
        if response.status_code != 200 or not response.headers.get('content-type', '').startswith('image/'):
            raise HTTPException(502, 'Google Maps could not return the map. Check API access, billing and key restrictions.')
        if response.headers.get('x-staticmap-api-warning'):
            raise HTTPException(502, 'Google returned an incomplete map. Review the coordinates and access path.')
        return response.content
    except httpx.HTTPError:
        # Never return/log exception URLs: they contain API keys and coordinates.
        raise HTTPException(502, 'Map service is temporarily unavailable.')
