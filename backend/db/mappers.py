from typing import Any, Dict

from ..utils.coerce import to_float, to_int, to_str


def _computed_value(r: Dict[str, Any], cap_rate: float | None) -> float | None:
    value = to_float(r.get("current_est_value")) or to_float(r.get("appraised_value"))
    if value:
        return value
    noi = to_float(r.get("noi_t12"))
    if noi and cap_rate and cap_rate > 0:
        return noi / cap_rate
    return noi  # fallback, maybe used downstream


def map_property_row(r: Dict[str, Any]) -> Dict[str, Any]:
    cap_rate = to_float(r.get("cap_rate_market_now"))
    est_value = _computed_value(r, cap_rate)
    return {
        "id": to_str(r.get("sys_id")) or to_str(r.get("id")),
        "external_id": to_str(r.get("property_external_id")),
        "name": to_str(r.get("property_name") or r.get("name")),
        "address": to_str(r.get("address_line_1") or r.get("address")),
        "city": to_str(r.get("city")),
        "state": to_str(r.get("state")),
        "zipcode": to_str(r.get("zip") or r.get("zipcode")),
        "submarket": to_str(r.get("submarket_name")),
        "type": to_str(r.get("property_type")),
        "property_class": to_str(r.get("property_class")),
        "product": to_str(r.get("mf_product_type")),
        "year_built": to_int(r.get("year_built")),
        "units": to_int(r.get("num_units")),
        "nra": to_int(r.get("net_rentable_area")),
        "avg_unit_size": to_float(r.get("average_unit_size")),
        "sqft": to_int(r.get("net_rentable_area")),
        "est_monthly_rent": to_float(r.get("est_monthly_rent")),
        "noi_t12": to_float(r.get("noi_t12")),
        "cap_rate_market_now": cap_rate,
        "median_income_now": to_float(r.get("median_income")),
        "vacancy_rate_now": to_float(r.get("vacancy_rate")),
        "current_est_value": est_value,
        "provenance": ["ServiceNow"],
    }


def map_market_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "zipcode": to_str(r.get("zipcode")),
        "submarket_name": to_str(r.get("submarket_name")),
        "date": to_str(r.get("date")),
        "median_rent": to_float(r.get("median_rent")),
        "rent_yoy": to_float(r.get("rent_yoy")),
        "median_price": to_float(r.get("median_price") or r.get("sale_price_per_unit_usd")),
        "cap_rate_market_now": to_float(r.get("cap_rate_market_now")),
        "median_income": to_float(r.get("median_income")),
        "vacancy_rate": to_float(r.get("vacancy_rate")),
        "dom": to_int(r.get("dom")),
        "pipeline_12m_units": to_float(r.get("pipeline_12m_units")),
    }
