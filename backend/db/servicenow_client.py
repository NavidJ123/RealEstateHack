import os, requests
from typing import Dict, Iterator, List, Optional
from urllib.parse import quote_plus

SN_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
SN_USER     = os.getenv("SERVICENOW_USER")
SN_PASS     = os.getenv("SERVICENOW_PASS")

# Tables from env (override per city/dataset)
TBL_PROP = os.getenv("SN_TABLE_PROPERTIES", "x_ai_prop_property")
TBL_MKT  = os.getenv("SN_TABLE_MARKET", "x_ai_prop_market_stats")

DEFAULT_LIMIT = 200  # SN max page size is usually 100..10k depending on instance settings

class SNClient:
    def __init__(self, instance: Optional[str] = None):
        inst = (instance or SN_INSTANCE or '').strip()
        if not inst or not SN_USER or not SN_PASS:
            raise RuntimeError('ServiceNow credentials are not configured')
        if not inst.startswith('http'):
            inst = f'https://{inst}'
        self.base = inst.rstrip('/')
        self.auth = (SN_USER, SN_PASS)

    def _get(self, path: str, params: Dict[str,str]|None=None) -> Dict:
        url = f"{self.base}{path}"
        r = requests.get(url, params=params, auth=self.auth, timeout=60)
        r.raise_for_status()
        return r.json()

    def get_record(self, table: str, sys_id: str) -> Dict:
        return self._get(f"/api/now/table/{table}/{sys_id}")["result"]

    def query(
        self,
        table: str,
        query: str = "",
        fields: List[str] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Iterator[Dict]:
        """
        Stream all records matching a query with pagination.
        """
        offset = 0
        params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": "0",
        }
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = ",".join(fields)

        while True:
            params["sysparm_offset"] = str(offset)
            data = self._get(f"/api/now/table/{table}", params=params)
            batch = data.get("result", [])
            if not batch:
                break
            for row in batch:
                yield row
            if len(batch) < limit:
                break
            offset += limit

# Convenience helpers for your two tables
def stream_properties(
    client: SNClient,
    submarket: str | None = None,
    limit_per_page: int = 200,
) -> Iterator[Dict]:
    fields = [
        "sys_id","property_external_id","property_name","address_line_1","city","state","zip",
        "submarket_name","property_type","property_class","mf_product_type","year_built","num_units",
        "net_rentable_area","average_unit_size","status","as_of_date",
        # Finance/ops
        "noi_t12","cap_rate_market_now","median_income","vacancy_rate",
        # Nice extras you showed
        "gross_buiding_area","land_area_acres","num_buildings","num_stories",
        "latitude","longitude","owner_name","owner_type","energy_star_score",
    ]
    q = "status=existing"
    if submarket:
        q += f"^submarket_name={quote_plus(submarket)}"
    yield from client.query(TBL_PROP, query=q, fields=fields, limit=limit_per_page)

def stream_market_stats(
    client: SNClient,
    submarket_or_zip: str,
    months_back: int = 60,
    limit_per_page: int = 1000,
) -> List[Dict]:
    """
    Pull monthly market rows for a ZIP or submarket for the last N months.
    Your SN schema might store by zipcode or by submarket; pick the right key here.
    """
    fields = [
        "sys_id","zipcode","submarket_name","date",
        "median_rent","median_price","cap_rate_market_now",
        "median_income","vacancy_rate","dom"
    ]
    # Example for ZIP; if you use submarket_name instead, change the query field:
    queries = []
    if str(submarket_or_zip).strip():
        queries.append(f"submarket_name={submarket_or_zip}")
        queries.append(f"zipcode={submarket_or_zip}")
    rows: List[Dict] = []
    for q in queries:
        rows = list(client.query(TBL_MKT, query=q, fields=fields, limit=limit_per_page))
        if rows:
            break
    return rows
