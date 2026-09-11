export type Field = {key: string; label: string; type?: string; options?: string[]};
const f = (key: string, label: string, type = 'text', options?: string[]): Field => ({key,label,type,options});
export const groups: {key: string; title: string; fields: Field[]}[] = [
 {key:'assignment', title:'Assignment & people', fields:[
  f('display_addressee','Report addressee (optional; defaults to applicant)'),f('display_address','Report addressee address (optional)','textarea'),f('reference','Report reference'),f('bank_reference','Bank reference'),f('purpose','Valuation purpose'),
  f('request_date','Request date','date'),f('inspection_date','Inspection date','date'),f('valuation_date','Valuation date','date'),f('report_date','Report date','date'),
  f('applicant','Applicant name'),f('applicant_address','Applicant address','textarea'),f('owner','Owner name'),f('owner_address','Owner address','textarea')]},
 {key:'property', title:'Property & location', fields:[
  f('kind','Property type','select',['land','land_building']),f('address','Property address','textarea'),f('land_name','Land name'),f('village','Village'),f('district','District'),f('province','Province'),f('local_authority','Local authority'),f('assessment_number','Assessment number'),
  f('plan_number','Survey plan number'),f('plan_date','Survey plan date','date'),f('surveyor','Surveyor'),f('lot_number','Lot number'),f('acres','Acres','integer'),f('roods','Roods (0–3)','integer'),f('perches','Remaining perches (below 40)','decimal'),
  f('latitude','Latitude (decimal degrees)','coordinate'),f('longitude','Longitude (decimal degrees)','coordinate'),f('zoom','Map zoom (1–20)','integer'),f('map_type','Map type','select',['roadmap','satellite','hybrid']),
  f('situation','Situation','textarea'),f('access','Access description','textarea'),f('road_width','Access road width and unit'),f('locality','Neighbourhood','textarea'),f('land_description','Land description','textarea'),
  f('boundary_note','Boundary source note (optional override)','textarea'),f('assessment_text','Assessment particulars (optional override)','textarea'),f('north','North boundary'),f('east','East boundary'),f('south','South boundary'),f('west','West boundary'),f('services','Services and infrastructure','textarea')]},
 {key:'building', title:'Building', fields:[
  f('short_name','Building heading / short name'),f('description','Building description','textarea'),f('area_source','Source of floor areas'),f('roof','Roof'),f('walls','Walls'),f('floor_finish','Floor finish'),f('doors_windows','Doors and windows','textarea'),f('conveniences','Conveniences','textarea'),f('condition','Condition'),f('occupier','Occupier')]},
 {key:'findings', title:'Evidence & findings', fields:[
  f('documents','Documents actually reviewed','textarea'),f('approvals','Approvals and their verification status','textarea'),f('street_building_lines','Street lines and building limits','textarea'),f('legal_interest','Legal interest / assumptions','textarea'),
  f('deed_type','Deed type (e.g. Deed of Gift)'),f('deed_number','Deed number'),f('deed_date','Deed date','date'),f('notary','Notary'),f('method','Adopted valuation method'),f('comparable_evidence','Comparable evidence: source, date, details and adjustments','textarea'),f('analysis','Analysis and basis for adopted rates','textarea'),f('limitations','Limitations and assumptions','textarea'),f('certification','Valuer certification wording','textarea')]},
 {key:'valuation', title:'Valuation figures', fields:[
  f('land_rate_per_perch','Land rate per perch (LKR)','decimal'),f('site_improvements','Separate site improvements (LKR)','decimal'),f('depreciation_amount','Building depreciation (LKR)','decimal'),
  f('adjustment_amount','Other adjustment: + / − LKR','decimal'),f('adjustment_reason','Adjustment basis','textarea'),f('rounding_increment','Round indication to nearest LKR','select',['1','100','1000','10000','100000']),
  f('final_market_value','Adopted market value override (optional LKR)','optional-money'),f('final_market_reason','Reason for overriding the indication','textarea'),
  f('forced_sale_value','Forced-sale value (optional LKR)','optional-money'),f('forced_sale_reason','Forced-sale value basis','textarea'),f('insurance_value','Insurance value (optional LKR)','optional-money'),f('insurance_reason','Insurance value basis','textarea')]},
 {key:'bank',title:'Bank details',fields:[f('name','Bank name'),f('branch','Branch'),f('recipient','Recipient / designation'),f('address','Bank address','textarea')]},
 {key:'valuer',title:'Valuer details',fields:[f('name','Valuer name'),f('qualifications','Letterhead: degree, membership, designation, position (one per line)','textarea'),f('signature_designation','Signature designation'),f('registration','Professional registration'),f('address','Address','textarea'),f('phone','Telephone (one per line)','textarea'),f('email','Email')]}
];
