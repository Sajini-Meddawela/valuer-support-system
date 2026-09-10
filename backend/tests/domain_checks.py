"""Dependency-light domain tests: python -m unittest tests.domain_checks -v."""
import unittest
from decimal import Decimal
from app.schemas import ReportData
from app.calculations import calculate, words, review_issues


class DomainChecks(unittest.TestCase):
    def test_units_and_rounding(self):
        d = ReportData(property={'acres':1,'roods':2,'perches':'10.25'},valuation={'land_rate_per_perch':'100000','rounding_increment':10000})
        c = calculate(d)
        self.assertEqual(c['extent_perches'],'250.25')
        self.assertEqual(c['land_value'],'25025000.00')
        self.assertEqual(c['rounded_value'],'25030000')

    def test_building_and_decimal_precision(self):
        d = ReportData(property={'kind':'land_building','perches':'1.25'},
            building={'floors':[{'name':'Ground','area_sqft':'100.1','rate_per_sqft':'50.55'}]},
            valuation={'land_rate_per_perch':'100.10','site_improvements':'10','depreciation_amount':'5','rounding_increment':1})
        c=calculate(d)
        self.assertEqual(c['land_value'],'125.13')
        self.assertEqual(c['building_value'],'5060.06')
        self.assertEqual(c['calculated_total'],'5190.19')

    def test_manual_value_and_wording(self):
        d=ReportData(valuation={'final_market_value':'26700000.25','final_market_reason':'Example'})
        self.assertEqual(calculate(d)['market_value'],'26700000.25')
        self.assertEqual(words('26700000.25'),'Rupees twenty-six million seven hundred thousand and twenty-five cents only')
        self.assertEqual(words('0'),'Rupees zero only')
        self.assertEqual(words('100.999'),'Rupees one hundred and one only')

    def test_land_only_excludes_building(self):
        d=ReportData(building={'floors':[{'area_sqft':'100','rate_per_sqft':'10'}]})
        self.assertEqual(calculate(d)['building_value'],'0')

    def test_negative_total_rejected(self):
        d=ReportData(valuation={'adjustment_amount':'-1'})
        with self.assertRaises(ValueError):calculate(d)

    def test_excessive_depreciation_rejected(self):
        d=ReportData(valuation={'depreciation_amount':'1'})
        with self.assertRaises(ValueError):calculate(d)

    def test_coordinate_pair_and_ranges(self):
        for coords in [{'latitude':7},{'latitude':91,'longitude':80},{'latitude':float('nan'),'longitude':80}]:
            with self.assertRaises(ValueError):ReportData(property=coords)
        d=ReportData(property={'latitude':0,'longitude':0})
        self.assertEqual(d.property.latitude,0)

    def test_review_rejects_blank_fields(self):
        self.assertGreater(len(review_issues(ReportData())),10)

    def test_no_implicit_forced_sale_or_insurance(self):
        d=ReportData()
        self.assertIsNone(d.valuation.forced_sale_value)
        self.assertIsNone(d.valuation.insurance_value)

    def test_extent_components(self):
        for p in [{'roods':4},{'perches':'40'},{'acres':-1}]:
            with self.assertRaises(ValueError):ReportData(property=p)


if __name__=='__main__':unittest.main()
