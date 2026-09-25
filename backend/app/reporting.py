from io import BytesIO
from copy import deepcopy
import re
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import shutil
import subprocess
from urllib.parse import urlencode
from datetime import datetime, timezone

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from jinja2 import Environment, StrictUndefined
import qrcode
from PIL import Image
from fastapi import HTTPException

from .config import settings
from .calculations import calculate, money, words
from .maps import map_image
from .schemas import ReportData
from .reference_layout import layout_context, longdate, shortdate


TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / 'templates'
    / 'valuation-reference-v2.docx'
)


def asset_image(
    doc,
    source,
    max_width=155,
    max_height=90,
):
    stream = None

    if isinstance(source, (bytes, bytearray)):
        stream = BytesIO(source)
        image_source = stream
    else:
        image_source = source

    with Image.open(image_source) as im:
        width, height = im.size

    factor = min(
        max_width / width,
        max_height / height,
    )

    if stream is not None:
        stream.seek(0)

        return InlineImage(
            doc,
            stream,
            width=Mm(width * factor),
            height=Mm(height * factor),
        )

    return InlineImage(
        doc,
        str(source),
        width=Mm(width * factor),
        height=Mm(height * factor),
    )


def docx_bytes(
    data: ReportData,
    status: str,
    assets,
    photo_loader=None,
):
    if not TEMPLATE.exists():
        raise HTTPException(
            503,
            (
                'Report template is missing. Restore '
                'backend/templates/valuation-reference-v2.docx '
                'from the template update package.'
            ),
        )

    doc = DocxTemplate(str(TEMPLATE))
    ctx = data.model_dump(mode='json')

    ctx['status'] = (
        'FINAL — APPROVED BY VALUER'
        if status == 'final'
        else 'DRAFT — NOT APPROVED'
    )

    ctx['calc'] = calculate(data)

    ctx['template_version'] = (
        'valuation-reference-v2 / '
        + hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()[:12]
    )

    ctx.update(
        layout_context(
            data,
            ctx['calc'],
        )
    )

    ctx['is_final'] = status == 'final'
    ctx['map_image'] = 'Map not included.'
    ctx['map_note'] = 'Map not included.'
    ctx['qr_image'] = ''

    # Keep map/QR in-memory streams alive until rendering completes.
    buffers = []

    def photo_source(asset):
        if photo_loader is not None:
            return photo_loader(asset.filename)

        return (
            settings.data_dir
            / 'photos'
            / asset.filename
        )

    if data.property.include_map:
        if not settings.map_report_export_allowed:
            raise HTTPException(
                409,
                (
                    'Map export is disabled until the operator confirms '
                    'export and retention rights. Disable Include map '
                    'to export without it.'
                ),
            )

        content = BytesIO(
            map_image(data.property)
        )
        buffers.append(content)

        ctx['map_image'] = InlineImage(
            doc,
            content,
            width=Mm(158),
        )

        ctx['map_note'] = (
            'Location map — not a survey plan; imagery is not live. '
            'Retrieved '
            + datetime.now(timezone.utc).strftime(
                '%Y-%m-%d %H:%M UTC'
            )
            + (
                '. Blue access path supplied by the valuer.'
                if data.property.access_path
                else '.'
            )
        )

    if data.property.latitude is not None:
        url = (
            'https://www.google.com/maps/search/?'
            + urlencode(
                {
                    'api': 1,
                    'query': (
                        f'{data.property.latitude},'
                        f'{data.property.longitude}'
                    ),
                }
            )
        )

        buf = BytesIO()

        qrcode.make(url).save(
            buf,
            format='PNG',
        )

        buf.seek(0)
        buffers.append(buf)

        ctx['qr_image'] = InlineImage(
            doc,
            buf,
            width=Mm(43),
        )

    ctx['photos'] = [
        {
            'caption': x.caption,
            'image': asset_image(
                doc,
                photo_source(x),
            ),
        }
        for x in assets
    ]

    roles = {
        'cover': [],
        'access': [],
        'interior': [],
    }

    for asset in assets:
        role = 'interior'
        caption = asset.caption or ''

        for candidate in roles:
            if caption.lower().startswith(
                '[' + candidate + ']'
            ):
                role = candidate
                break

        roles[role].append(asset)

    ctx['cover_image'] = (
        asset_image(
            doc,
            photo_source(roles['cover'][0]),
            134,
            100,
        )
        if roles['cover']
        else 'Cover photograph not supplied.'
    )

    ctx['access_image'] = (
        asset_image(
            doc,
            photo_source(roles['access'][0]),
            71,
            43,
        )
        if roles['access']
        else ''
    )

    ctx['interior_left'] = (
        asset_image(
            doc,
            photo_source(roles['interior'][0]),
            58,
            44,
        )
        if roles['interior']
        else ''
    )

    ctx['interior_right'] = (
        asset_image(
            doc,
            photo_source(roles['interior'][1]),
            58,
            44,
        )
        if len(roles['interior']) > 1
        else ''
    )

    extra = (
        roles['cover'][1:]
        + roles['access'][1:]
        + (
            roles['interior'][2:]
            if data.property.kind == 'land_building'
            else roles['interior']
        )
    )

    ctx['extra_photos'] = [
        {
            'image': asset_image(
                doc,
                photo_source(x),
            ),
            'caption': (
                x.caption.split(']', 1)[-1].strip()
                if x.caption.startswith('[')
                else x.caption
            ),
        }
        for x in extra
    ]

    env = Environment(
        undefined=StrictUndefined,
        autoescape=True,
    )

    env.filters['longdate'] = longdate
    env.filters['shortdate'] = shortdate
    env.filters['money'] = money
    env.filters['words'] = words
    env.filters['blank'] = (
        lambda v: (
            v
            if v not in ('', None)
            else 'Not supplied'
        )
    )

    doc.render(
        ctx,
        jinja_env=env,
        autoescape=True,
    )

    rendered = doc.docx

    for node in rendered.element.xpath('.//w:p'):
        para = Paragraph(
            node,
            rendered,
        )

        for run in list(para.runs):
            if not re.search(
                r'\d(?:st|nd|rd|th) [A-Z][a-z]+ \d{4}',
                run.text,
            ):
                continue

            chunks = re.split(
                r'(?<=\d)(st|nd|rd|th)(?= [A-Z][a-z]+ \d{4})',
                run.text,
            )

            for i, chunk in enumerate(chunks):
                replacement = OxmlElement('w:r')

                if run._r.rPr is not None:
                    replacement.append(
                        deepcopy(run._r.rPr)
                    )

                item = Run(
                    replacement,
                    para,
                )
                item.text = chunk

                if i % 2:
                    item.font.superscript = True

                run._r.addprevious(replacement)

            run._r.getparent().remove(run._r)

    if roles['cover']:
        for para in rendered.paragraphs:
            if para._p.xpath('.//wp:inline'):
                for shape in para._p.xpath('.//pic:spPr'):
                    line = OxmlElement('a:ln')
                    line.set('w', '25400')

                    fill = OxmlElement('a:solidFill')
                    color = OxmlElement('a:srgbClr')
                    color.set('val', '000000')

                    fill.append(color)
                    line.append(fill)
                    shape.append(line)

                break

    result = BytesIO()
    rendered.save(result)

    return result.getvalue()


def pdf_bytes(docx):
    executable = shutil.which(
        settings.soffice_path
    )

    if not executable:
        raise HTTPException(
            503,
            (
                'PDF conversion needs LibreOffice. Install it and '
                'configure SOFFICE_PATH; DOCX draft export still works.'
            ),
        )

    with TemporaryDirectory(
        prefix='valuer-pdf-'
    ) as folder:
        root = Path(folder)

        (
            root
            / 'report.docx'
        ).write_bytes(docx)

        try:
            result = subprocess.run(
                [
                    executable,
                    (
                        '-env:UserInstallation='
                        + (root / 'profile').as_uri()
                    ),
                    '--headless',
                    '--convert-to',
                    'pdf',
                    '--outdir',
                    str(root),
                    str(root / 'report.docx'),
                ],
                capture_output=True,
                timeout=90,
                check=False,
            )

        except subprocess.TimeoutExpired:
            raise HTTPException(
                503,
                'PDF conversion timed out. Please try again.',
            )

        output = root / 'report.pdf'

        if (
            result.returncode != 0
            or not output.exists()
        ):
            raise HTTPException(
                503,
                (
                    'PDF conversion failed. Check the server '
                    'LibreOffice installation and template.'
                ),
            )

        return output.read_bytes()


def archive(
    data,
    assets,
    photo_loader=None,
):
    """
    Build the immutable final-report artifacts entirely in memory.

    Step 8 stores these bytes in Google Drive instead of
    backend/data/final.
    """
    docx = docx_bytes(
        data,
        'final',
        assets,
        photo_loader=photo_loader,
    )

    pdf = pdf_bytes(docx)

    manifest = {
        'template_sha256': hashlib.sha256(
            TEMPLATE.read_bytes()
        ).hexdigest(),
        'docx_sha256': hashlib.sha256(
            docx
        ).hexdigest(),
        'pdf_sha256': hashlib.sha256(
            pdf
        ).hexdigest(),
        'data': data.model_dump(
            mode='json'
        ),
        'calculation': calculate(data),
    }

    manifest_bytes = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ).encode('utf-8')

    return {
        'docx': docx,
        'pdf': pdf,
        'manifest': manifest_bytes,
    }