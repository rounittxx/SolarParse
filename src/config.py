# Field definitions + Excel mapping live here together on purpose.
# When Energybae sends the real template, only FIELD_TO_CELL changes.

from dataclasses import dataclass


@dataclass
class Field:
    key: str
    label: str
    hint: str          # doubles as the LLM hint and the UI tooltip
    unit: str = ""
    required: bool = True


FIELDS = [
    Field("consumer_name",     "Consumer Name",     "Customer name as printed on the bill"),
    Field("consumer_number",   "Consumer Number",   "Account / consumer / service connection number"),
    Field("billing_period",    "Billing Period",    "Bill month or date range, e.g. Mar 2025 or 01/03/2025-31/03/2025"),
    Field("units_consumed",    "Units Consumed",    "Total units in the period (numeric only)", unit="kWh"),
    Field("total_bill_amount", "Total Bill Amount", "Final amount payable in INR (numeric only)", unit="INR"),
    Field("tariff_category",   "Tariff Category",   "Tariff/category code, e.g. LT-I Residential"),
    Field("connected_load",    "Connected Load",    "Connected load in kW (numeric only)", unit="kW"),
    Field("sanctioned_load",   "Sanctioned Load",   "Sanctioned load in kW (numeric only)", unit="kW"),
    Field("meter_number",      "Meter Number",      "Meter serial number, if printed", required=False),
]

FIELD_KEYS = [f.key for f in FIELDS]
FIELD_BY_KEY = {f.key: f for f in FIELDS}


# Where each field gets written in the template.
# These are the INPUT cells only -- formula cells are defined separately
# in src/excel/template_builder.py and are never touched by the filler.
INPUT_SHEET = "Inputs"

FIELD_TO_CELL = {
    "consumer_name":     "C4",
    "consumer_number":   "C5",
    "billing_period":    "C6",
    "units_consumed":    "C7",
    "total_bill_amount": "C8",
    "tariff_category":   "C9",
    "connected_load":    "C10",
    "sanctioned_load":   "C11",
    "meter_number":      "C12",
}


# Rough assumptions for the optional solar preview.
# Numbers are tuned for Maharashtra residential rooftop;
# nothing here lands in the Excel -- Excel does its own math.
SOLAR_DEFAULTS = {
    "sun_hours_per_day": 4.5,
    "system_cost_per_kw": 55000,
    "tariff_rate_inr_per_kwh": 9.5,
    "panel_degradation_pct": 0.7,
    "system_life_years": 25,
    "co2_kg_per_kwh": 0.82,
}
