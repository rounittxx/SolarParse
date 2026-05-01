# Quick solar preview shown in the UI BEFORE the user generates Excel.
# The Excel template does its own (more authoritative) maths -- this is
# just so the user sees a preview without opening the file.

from src.config import SOLAR_DEFAULTS


def recommend(units_consumed_kwh, sanctioned_load_kw=None, opts=None):
    """
    units_consumed_kwh: monthly units off the bill
    Returns a small dict ready to render as a table/cards.
    """
    o = {**SOLAR_DEFAULTS, **(opts or {})}

    if not units_consumed_kwh or units_consumed_kwh <= 0:
        return None

    daily = units_consumed_kwh / 30
    size_kw = round(daily / o["sun_hours_per_day"], 2)

    # sanity cap -- if sanctioned load is known, don't recommend more than that
    if sanctioned_load_kw and sanctioned_load_kw > 0 and size_kw > sanctioned_load_kw:
        size_kw = sanctioned_load_kw

    cost = round(size_kw * o["system_cost_per_kw"])
    annual_gen = round(size_kw * o["sun_hours_per_day"] * 365)
    annual_savings = round(annual_gen * o["tariff_rate_inr_per_kwh"])
    payback = round(cost / annual_savings, 1) if annual_savings else None
    co2 = round(annual_gen * o["co2_kg_per_kwh"] / 1000, 2)
    twentyfive_yr = round(annual_savings * o["system_life_years"] - cost)

    return {
        "recommended_kw": size_kw,
        "system_cost_inr": cost,
        "annual_generation_kwh": annual_gen,
        "annual_savings_inr": annual_savings,
        "payback_years": payback,
        "co2_offset_tpy": co2,
        "lifetime_savings_inr": twentyfive_yr,
    }
