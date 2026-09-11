from io import BytesIO
from zipfile import ZipFile
import pytest
from PIL import Image
from app.schemas import ReportData
from app.calculations import calculate, review_issues


def complete_data():
    d = ReportData().model_dump(mode='json')
    d['valuer'].update(name='Sample Valuer',registration='TEST-001')
    d['bank']['name']='Example Bank'
    d['assignment'].update(reference='TEST-001',purpose='Demonstration only',applicant='Sample Applicant',owner='Sample Owner',
                           inspection_date='2026-01-01',valuation_date='2026-01-02',report_date='2026-01-03')
    d['property'].update(address='Example property',plan_number='TEST-PLAN',lot_number='1',perches='8')
    for key in ['documents','method','comparable_evidence','analysis','limitations','certification']:
        d['findings'][key]='Synthetic test information; not a real valuation.'
    d['valuation']['land_rate_per_perch']='100000'
    return d


def test_decimal_calculation_and_rounding():
    d = ReportData(**complete_data())
    d.property.acres=1;d.property.roods=2;d.property.perches='10.25'
    d = ReportData(**d.model_dump())
    assert calculate(d)['extent_perches']=='250.25'
    assert calculate(d)['land_value']=='25025000.00'
    d.valuation.rounding_increment=10000
    assert calculate(d)['rounded_value']=='25030000'


def test_land_only_excludes_stale_building_values():
    raw=complete_data();raw['building']['floors']=[{'name':'old','area_sqft':'100','rate_per_sqft':'100'}]
    assert calculate(ReportData(**raw))['building_value']=='0'
    raw['valuation']['depreciation_amount']='1'
    with pytest.raises(ValueError):calculate(ReportData(**raw))


def test_final_override_requires_reason():
    raw=complete_data();raw['valuation']['final_market_value']='999'
    assert any('manually adopted' in x for x in review_issues(ReportData(**raw)))


def test_invalid_coordinates():
    raw=complete_data();raw['property']['latitude']=91
    with pytest.raises(ValueError):ReportData(**raw)


def test_ownership_and_stale_edits(client, auth):
    r=client.post('/api/reports',headers=auth).json()
    other=client.post('/api/auth/register',json={'email':'other@example.test','password':'another-password-123'}).json()
    headers={'Authorization':'Bearer '+other['access_token']}
    for path in ['', '/photos', '/history', '/map', '/export/docx']:
        assert client.get('/api/reports/'+r['id']+path,headers=headers).status_code==404
    url='/api/reports/'+r['id']
    body={'revision':r['revision'],'data':complete_data()}
    assert client.put(url,headers=auth,json=body).status_code==200
    assert client.put(url,headers=auth,json=body).status_code==409


def test_word_export_and_map_gate(client, auth):
    r=client.post('/api/reports',headers=auth).json();url='/api/reports/'+r['id']
    raw=complete_data();raw['assignment']['owner']='A & B <Owner>'
    assert client.put(url,headers=auth,json={'revision':1,'data':raw}).status_code==200
    res=client.get(url+'/export/docx',headers=auth);assert res.status_code==200
    with ZipFile(BytesIO(res.content)) as z:
        xml=z.read('word/document.xml').decode()
        assert 'A &amp; B &lt;Owner&gt;' in xml
        assert '{{' not in xml and '{%' not in xml
        assert 'DRAFT' in xml and '800,000/-' in xml
    raw['property'].update(latitude=0,longitude=0,include_map=True)
    client.put(url,headers=auth,json={'revision':2,'data':raw})
    assert client.get(url+'/export/docx',headers=auth).status_code==409


def test_upload_validation(client, auth):
    r=client.post('/api/reports',headers=auth).json();url='/api/reports/'+r['id']
    res=client.post(url+'/photos',headers=auth,data={'revision':1},files={'file':('bad.jpg',b'not an image','image/jpeg')})
    assert res.status_code==422
    buf=BytesIO();Image.new('RGB',(20,20),'white').save(buf,'PNG')
    res=client.post(url+'/photos',headers=auth,data={'revision':1,'caption':'Test'},files={'file':('test.png',buf.getvalue(),'image/png')})
    assert res.status_code==201 and res.json()['revision']==2


def test_review_approval_and_immutable_exports(client, auth, monkeypatch):
    # Isolate converter availability; actual LibreOffice conversion has a separate smoke command.
    monkeypatch.setattr('app.reporting.pdf_bytes',lambda content:b'%PDF-1.4\nTEST ONLY')
    r=client.post('/api/reports',headers=auth).json();url='/api/reports/'+r['id']
    assert client.post(url+'/review',headers=auth,json={'revision':1}).status_code==422
    client.put(url,headers=auth,json={'revision':1,'data':complete_data()})
    assert client.post(url+'/finalise',headers=auth,json={'revision':2,'confirmed':True}).status_code==409
    reviewed=client.post(url+'/review',headers=auth,json={'revision':2}).json()
    final=client.post(url+'/finalise',headers=auth,json={'revision':reviewed['revision'],'confirmed':True})
    assert final.status_code==200 and final.json()['status']=='final'
    first=client.get(url+'/export/docx',headers=auth).content
    assert client.put(url,headers=auth,json={'revision':final.json()['revision'],'data':complete_data()}).status_code==409
    client.put('/api/profile',headers=auth,json={'name':'Changed profile'})
    assert client.get(url+'/export/docx',headers=auth).content==first
    revised=client.post(url+'/copy',headers=auth).json()
    assert revised['id']!=r['id'] and revised['status']=='draft'
