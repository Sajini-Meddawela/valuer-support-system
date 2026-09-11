"""Presentation mapping for the reference Word layout; no stored property defaults."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
from docxtpl import RichText
from .calculations import words


def number(value):
    return format(Decimal(str(value)), 'f').rstrip('0').rstrip('.') if '.' in format(Decimal(str(value)), 'f') else str(value)


def money_reference(value):
    v=Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return f'{v:,.0f}/-' if v==v.to_integral_value() else f'{v:,.2f}'


def shortdate(value):
    return date.fromisoformat(str(value)).strftime('%d-%m-%Y') if value else ''


def longdate(value):
    if not value:return ''
    v=date.fromisoformat(str(value));day=v.day
    suffix='th' if 11<=day%100<=13 else {1:'st',2:'nd',3:'rd'}.get(day%10,'th')
    return f'{day:02d}{suffix} {v.strftime("%B %Y")}'


def dms(value,latitude):
    seconds=(Decimal(str(abs(value)))*3600).quantize(Decimal('.1'),rounding=ROUND_HALF_UP)
    degrees=int(seconds//3600);seconds-=degrees*3600
    minutes=int(seconds//60);seconds-=minutes*60
    direction=('N' if value>=0 else 'S') if latitude else ('E' if value>=0 else 'W')
    return f'{degrees}°{minutes:02d}\'{seconds:04.1f}"{direction}'


def rich(parts,bold=False):
    r=RichText()
    for text,color in parts:r.add(str(text),font='Trebuchet MS',size=22,bold=bold,color=color)
    return r


def highlight_numbers(text,bold=False):
    return rich([(t,'FF0000' if re.fullmatch(r'\d[\d,]*(?:\.\d+)?(?:/-)?',t) else '000000')
                 for t in re.split(r'(\d[\d,]*(?:\.\d+)?(?:/-)?)',text)],bold)


def mixed(parts):
    r=RichText()
    for text,color,bold in parts:r.add(str(text),font='Trebuchet MS',size=22,color=color,bold=bold)
    return r


def layout_context(data,calc):
    a,p,b,f,v=data.assignment,data.property,data.building,data.findings,data.valuation
    qual=[x.strip() for x in data.valuer.qualifications.splitlines() if x.strip()]
    letterhead=['VLR. '+data.valuer.name if data.valuer.name else '']+qual[:3]+['\n'.join(qual[3:])]
    if len(qual)<3:letterhead=['VLR. '+data.valuer.name if data.valuer.name else '']+qual+['']*(4-len(qual))
    phones=[x.strip() for x in re.split(r'\n|\s*/\s*',data.valuer.phone) if x.strip()]
    phones=(phones+['','',''])[:2]+[' / '.join(phones[2:])] if len(phones)>3 else (phones+['','',''])[:3]
    extent=f'{p.acres:02d}A-{p.roods:02d}R-{number(p.perches).zfill(2)}P'
    name=b.short_name or b.description.strip().split('\n')[0]
    def abbrev(name):
        return {'ground floor':'G.F','first floor':'F.F','second floor':'S.F'}.get(name.strip().lower(),name)
    floors=b.floors if p.kind=='land_building' else []
    rates={x.rate_per_sqft for x in floors}
    floor_text='\n'.join(f'{abbrev(x.name)}- {number(x.area_sqft)} Sq.ft' for x in floors)
    if len(rates)==1:
        detail='('+ '+'.join(f'{abbrev(x.name).replace(".","")}:{number(x.area_sqft)}' for x in floors)+') '
        building_parts=[(detail+number(calc['total_floor_area'])+' sqft @ ','000000'),
            ('Rs '+money_reference(next(iter(rates))),'FF0000'),(' per. sq.ft\t\t','000000'),
            ('= Rs.'+money_reference(calc['building_value']),'FF0000')]
    else:
        building_parts=[]
        for floor,amount in zip(floors,calc['floor_values']):
            building_parts += [(f'{floor.name}: {number(floor.area_sqft)} sqft @ ','000000'),
               ('Rs '+money_reference(floor.rate_per_sqft)+' = Rs.'+money_reference(amount)+'\n','FF0000')]
        building_parts += [('Total building value\t','000000'),('= Rs.'+money_reference(calc['building_value']),'FF0000')]
    def summary(label,value):
        return rich([(label+' of the subject property is ','000000'),
            ('Rs.'+money_reference(value)+' ('+words(value).title()+').','EE0000')],bold=True) if value is not None else ''
    extra=[]
    if v.site_improvements:extra.append('Separate site improvements = Rs.'+money_reference(v.site_improvements))
    if v.depreciation_amount:extra.append('Less building depreciation = Rs.'+money_reference(v.depreciation_amount))
    if v.adjustment_amount:extra.append('Other adjustment = Rs.'+money_reference(v.adjustment_amount)+'; '+v.adjustment_reason)
    if v.final_market_value is not None:extra.append('Adopted market value = Rs.'+money_reference(v.final_market_value)+'; '+v.final_market_reason)
    parts=[x.strip().lstrip('*').strip() for x in re.split(r'\n\s*\n|\n',f.limitations) if x.strip()]
    limitation_paragraphs=[]
    for line in parts:
        chunks=[]
        if data.bank.name and data.bank.name in line:
            spans=line.split(data.bank.name)
            chunks.append(('* '+spans[0],'000000'))
            for span in spans[1:]:chunks.extend([(data.bank.name,'EE0000'),(span,'000000')])
        else:chunks=[('* '+line,'000000')]
        limitation_paragraphs.append(rich(chunks,True))
    owner_present=a.owner.strip() and a.owner.casefold() in f.legal_interest.casefold()
    deed_present=f.deed_number.strip() and f.deed_number in f.legal_interest
    boundary_present='boundaries are' in p.land_description.lower()
    purpose=a.purpose.strip()
    purpose_clause=purpose if purpose.lower().startswith('to ') else ('for '+purpose if purpose else '')
    situation_parts=[]
    for part in re.split(r'([“"][^”\"]+[”\"])',p.situation):
        situation_parts.append((part,'000000',part.startswith(('“','"'))))
    assessment=p.assessment_text or (f'This property falls within the administrative limits of {p.local_authority} and assessed for rates. (Ass. No. {p.assessment_number})' if p.assessment_number else '')
    assessment_parts=[(part,'000000',part.startswith('(Ass.')) for part in re.split(r'(\(Ass\.[^)]*\))',assessment)]
    ownership_text='' if owner_present or not a.owner else f'According to the documentary proofs provided, the present owner of the subject property is {a.owner.rstrip(".")} of {a.owner_address.rstrip(".")}.'
    ownership_rich=mixed([('According to the documentary proofs provided, the present owner of the subject property is ','000000',False),
        (a.owner.rstrip('.')+' of ','000000',True),(a.owner_address.rstrip('.')+'.','FF0000',True)]) if ownership_text else ''
    return dict(letterhead=letterhead,phones=phones,
        display_addressee=a.display_addressee or a.applicant,display_address=a.display_address or a.applicant_address,
        situation_rich=mixed(situation_parts),assessment_rich=mixed(assessment_parts),ownership_rich=ownership_rich,
        identity_rich=mixed([('The property is depicted as ','000000',False),('Lot No. '+p.lot_number+', in Survey Plan No '+p.plan_number,'000000',True),
            (' dated '+longdate(p.plan_date)+' made by '+p.surveyor+', for the ','000000',False),('Extent '+extent+' land.','000000',True)]),
        purpose_clause=purpose_clause,extent_hyphen=extent,extent_spaces=extent.replace('-',' '),building_name=name,
        signature_designation=('('+data.valuer.signature_designation+')') if data.valuer.signature_designation else (('('+qual[2]+')') if len(qual)>2 else ''),
        coordinates_dms=(dms(p.latitude,True)+' '+dms(p.longitude,False)) if p.latitude is not None else '',
        floor_area_lines=floor_text,
        boundary_note=p.boundary_note or ('' if boundary_present else f'Boundaries are as mentioned according to the provided Survey Plan No {p.plan_number} & the field inspection dated {longdate(a.inspection_date)}.'),
        assessment_text=p.assessment_text or (f'This property falls within the administrative limits of {p.local_authority} and assessed for rates. (Ass. No. {p.assessment_number})' if p.assessment_number else ''),
        document_lines=[line.strip().lstrip("•*").strip() for line in f.documents.splitlines() if line.strip()],
        ownership_text='' if owner_present or not a.owner else f'According to the documentary proofs provided, the present owner of the subject property is {a.owner.rstrip(".")} of {a.owner_address.rstrip(".")}.',
        deed_text='' if deed_present or not f.deed_number else f'By {f.deed_type or "deed"} No {f.deed_number} dated {longdate(f.deed_date)}, Attested by {f.notary}.',
        evidence_rich=highlight_numbers(f.comparable_evidence),limitation_paragraphs=limitation_paragraphs,
        land_calculation=rich([(number(calc['extent_perches']).zfill(2)+'P @ ','000000'),('Rs.'+money_reference(v.land_rate_per_perch),'FF0000'),
            (' P.P.\t\t\t\t\t\t\t','000000'),('=Rs. '+money_reference(calc['land_value']),'FF0000')]),
        building_calculation=rich(building_parts),extra_financial_lines='\n'.join(extra),
        total_calculation=rich([('Free hold value of the property\t\t\t\t\t\t','000000'),('=Rs.'+money_reference(calc['calculated_total']),'FF0000')],True),
        rounded_calculation=rich([('Free hold value of the property (Rounded)\t\t\t\t','000000'),('=Rs.'+money_reference(calc['rounded_value']),'FF0000')],True),
        market_summary=summary('The Market Value',calc['market_value']),forced_summary=summary('Forced sale Value',v.forced_sale_value),
        insurance_summary=summary('Insurance sale Value',v.insurance_value))
