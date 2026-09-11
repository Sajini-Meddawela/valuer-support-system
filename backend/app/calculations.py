from decimal import Decimal, ROUND_HALF_UP
from .schemas import ReportData


def integer_words(n):
    """English whole-number wording; monetary arithmetic stays in Decimal."""
    ones = ['zero','one','two','three','four','five','six','seven','eight','nine',
            'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen']
    tens = ['', '', 'twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
    if n < 0:
        return 'minus ' + integer_words(-n)
    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + ('-' + ones[n % 10] if n % 10 else '')
    if n < 1000:
        return ones[n // 100] + ' hundred' + (' and ' + integer_words(n % 100) if n % 100 else '')
    for size, label in [(10**15,'quadrillion'),(10**12,'trillion'),(10**9,'billion'),(10**6,'million'),(1000,'thousand')]:
        if n >= size:
            return integer_words(n // size) + ' ' + label + (' ' + integer_words(n % size) if n % size else '')


def money(value):
    return f'{Decimal(value):,.2f}'


def words(value):
    value = Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    whole = int(value)
    cents = int((value - whole) * 100)
    return f'Rupees {integer_words(whole)}'+(f' and {integer_words(cents)} cents' if cents else '')+' only'


def calculate(data: ReportData):
    p, b, v = data.property, data.building, data.valuation
    extent = Decimal(p.acres * 160 + p.roods * 40) + p.perches
    land = (extent * v.land_rate_per_perch).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    floors = b.floors if p.kind == 'land_building' else []
    floor_values = [(f.area_sqft * f.rate_per_sqft).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) for f in floors]
    building = sum(floor_values, Decimal('0'))
    if v.depreciation_amount > building:
        raise ValueError('Building depreciation cannot exceed the gross building value.')
    total = land + building + v.site_improvements - v.depreciation_amount + v.adjustment_amount
    if total < 0:
        raise ValueError('Adjustments cannot produce a negative total value.')
    increment = Decimal(v.rounding_increment)
    rounded = (total / increment).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * increment
    final = v.final_market_value if v.final_market_value is not None else rounded
    amounts = dict(extent_perches=extent, land_value=land, building_value=building,
                   total_floor_area=sum((f.area_sqft for f in floors), Decimal('0')),
                   calculated_total=total, rounded_value=rounded, market_value=final)
    return {**{k: str(x) for k, x in amounts.items()}, 'market_value_words': words(final),
            'floor_values': [str(x) for x in floor_values]}


def review_issues(data: ReportData):
    a, p, f, v = data.assignment, data.property, data.findings, data.valuation
    issues = []
    required = {'Valuer name': data.valuer.name, 'Valuer registration': data.valuer.registration,
                'Bank name': data.bank.name, 'Report reference': a.reference, 'Purpose': a.purpose,
                'Applicant': a.applicant, 'Owner': a.owner, 'Property address': p.address,
                'Survey plan number': p.plan_number, 'Lot number': p.lot_number,
                'Inspection date': a.inspection_date, 'Valuation date': a.valuation_date,
                'Report date': a.report_date, 'Documents reviewed': f.documents,
                'Valuation method': f.method, 'Comparable evidence': f.comparable_evidence,
                'Valuation analysis': f.analysis, 'Limitations': f.limitations,
                'Certification': f.certification}
    issues += [f'{label} is required.' for label, value in required.items() if not value or not str(value).strip()]
    if p.acres * 160 + p.roods * 40 + p.perches <= 0:
        issues.append('Land extent must be greater than zero.')
    if v.land_rate_per_perch <= 0:
        issues.append('Enter the adopted land rate per perch.')
    if p.kind == 'land_building' and (not data.building.floors or any(x.area_sqft <= 0 or x.rate_per_sqft <= 0 for x in data.building.floors)):
        issues.append('Enter positive areas and rates for each building floor.')
    if v.adjustment_amount and not v.adjustment_reason.strip():
        issues.append('Explain the valuation adjustment.')
    if v.final_market_value is not None and not v.final_market_reason.strip():
        issues.append('Explain the manually adopted market value.')
    for name in ['forced_sale', 'insurance']:
        if getattr(v, name + '_value') is not None and not getattr(v, name + '_reason').strip():
            issues.append(f'Explain the {name.replace("_", " ")} value.')
    if a.inspection_date and a.report_date and a.inspection_date > a.report_date:
        issues.append('Inspection date cannot be after the report date.')
    if a.valuation_date and a.report_date and a.valuation_date > a.report_date:
        issues.append('Valuation date cannot be after the report date.')
    try:
        calculate(data)
    except ValueError as exc:
        issues.append(str(exc))
    return issues
