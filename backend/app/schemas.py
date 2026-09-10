from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, le=Decimal('100000000000000'), max_digits=19, decimal_places=2)]
Area = Annotated[Decimal, Field(ge=0, le=Decimal('1000000000'), max_digits=15, decimal_places=4)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_max_length=12000, allow_inf_nan=False)


class Credentials(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if '@' not in value or '.' not in value.rsplit('@', 1)[-1]:
            raise ValueError('Enter a valid email address.')
        return value


class Valuer(Strict):
    name: str = ''
    qualifications: str = ''
    registration: str = ''
    address: str = ''
    phone: str = ''
    email: str = ''


class BankData(Strict):
    name: str = ''
    branch: str = ''
    recipient: str = ''
    address: str = ''


class Assignment(Strict):
    reference: str = ''
    bank_reference: str = ''
    request_date: date | None = None
    inspection_date: date | None = None
    valuation_date: date | None = None
    report_date: date | None = None
    purpose: str = ''
    applicant: str = ''
    applicant_address: str = ''
    owner: str = ''
    owner_address: str = ''


class Property(Strict):
    kind: Literal['land', 'land_building'] = 'land'
    address: str = ''
    land_name: str = ''
    village: str = ''
    district: str = ''
    province: str = ''
    local_authority: str = ''
    assessment_number: str = ''
    plan_number: str = ''
    plan_date: date | None = None
    surveyor: str = ''
    lot_number: str = ''
    acres: int = Field(default=0, ge=0, le=1000000)
    roods: int = Field(default=0, ge=0, le=3)
    perches: Area = Field(default=Decimal('0'), lt=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    zoom: int = Field(default=17, ge=1, le=20)
    map_type: Literal['roadmap', 'satellite', 'hybrid'] = 'hybrid'
    include_map: bool = False
    situation: str = ''
    access: str = ''
    road_width: str = ''
    locality: str = ''
    land_description: str = ''
    north: str = ''
    east: str = ''
    south: str = ''
    west: str = ''
    services: str = ''
    # An optional access route drawn by the valuer, NOT a surveyed boundary.
    access_path: list[tuple[float, float]] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both latitude and longitude.')
        if self.include_map and self.latitude is None:
            raise ValueError('Coordinates are required to include a map.')
        for lat, lng in self.access_path:
            if not -90 <= lat <= 90 or not -180 <= lng <= 180:
                raise ValueError('Invalid access path coordinate.')
        return self


class Floor(Strict):
    name: str = Field(default='', max_length=100)
    area_sqft: Area = Decimal('0')
    rate_per_sqft: Money = Decimal('0')


class Building(Strict):
    description: str = ''
    area_source: str = ''
    roof: str = ''
    walls: str = ''
    floor_finish: str = ''
    doors_windows: str = ''
    conveniences: str = ''
    condition: str = ''
    occupier: str = ''
    floors: list[Floor] = Field(default_factory=list, max_length=30)


class Findings(Strict):
    documents: str = ''
    approvals: str = ''
    street_building_lines: str = ''
    legal_interest: str = ''
    deed_number: str = ''
    deed_date: date | None = None
    notary: str = ''
    method: str = ''
    comparable_evidence: str = ''
    analysis: str = ''
    limitations: str = ''
    certification: str = ''


class Valuation(Strict):
    land_rate_per_perch: Money = Decimal('0')
    site_improvements: Money = Decimal('0')
    depreciation_amount: Money = Decimal('0')
    adjustment_amount: Decimal = Field(default=Decimal('0'), ge=-Decimal('100000000000000'),
                                     le=Decimal('100000000000000'), max_digits=19, decimal_places=2)
    adjustment_reason: str = ''
    rounding_increment: Literal[1, 100, 1000, 10000, 100000] = 1000
    final_market_value: Money | None = None
    final_market_reason: str = ''
    forced_sale_value: Money | None = None
    forced_sale_reason: str = ''
    insurance_value: Money | None = None
    insurance_reason: str = ''


class ReportData(Strict):
    valuer: Valuer = Field(default_factory=Valuer)
    bank: BankData = Field(default_factory=BankData)
    assignment: Assignment = Field(default_factory=Assignment)
    property: Property = Field(default_factory=Property)
    building: Building = Field(default_factory=Building)
    findings: Findings = Field(default_factory=Findings)
    valuation: Valuation = Field(default_factory=Valuation)


class SaveReport(Strict):
    revision: int = Field(ge=1)
    data: ReportData


class Revision(Strict):
    revision: int = Field(ge=1)


class Approval(Revision):
    confirmed: Literal[True]
