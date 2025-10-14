import json
from datetime import datetime, timezone
import time
import typing as t
import requests as rq

from fivetran_connector_sdk import Connector  # Connector(update, schema)
from fivetran_connector_sdk import Operations as op  # upsert(), checkpoint()
from fivetran_connector_sdk import Logging as log  # log.info/fin e/warning/severe

DEFAULT_NYC_ZIP_PREFIXES = [
    "100", "101", "102", "103", "104", "111", "112", "113", "114", "116"
]
DEFAULT_TAXONOMY_DESCRIPTIONS = [
    "Reproductive Endocrinology", "Orthopaedic Surgery"
]
DEFAULT_TAXONOMY_CODES = ["207VE0102X", "207X00000X"]

# ---------- helpers ---------


def _safe(d: dict, path: t.List[t.Union[str, int]], default=None):
    cur = d
    try:
        for p in path:
            cur = cur[p]
        return cur
    except (KeyError, IndexError, TypeError):
        return default


def choose_primary_taxonomy(taxonomies: t.Optional[list]) -> t.Optional[dict]:
    if not taxonomies: return None
    for txy in taxonomies:
        # NPI marks primary taxonomy; value can be True/"Y"/"true"
        val = str(txy.get("primary", "")).lower()
        if val in ("true", "1", "y", "yes"):
            return txy
    return taxonomies[0]


def extract_primary_desc(r: dict) -> t.Optional[str]:
    txy = choose_primary_taxonomy(r.get("taxonomies"))
    return txy.get("desc") if txy else None


def choose_location_address(addresses: t.Optional[list]) -> t.Optional[dict]:
    if not addresses: return None
    loc, mail = None, None
    for a in addresses:
        purpose = (a.get("address_purpose") or "").upper()
        if purpose == "LOCATION" and loc is None:
            loc = a
        elif purpose == "MAILING" and mail is None:
            mail = a
    return loc or mail or addresses[0]


def extract_city(r: dict) -> t.Optional[str]:
    a = choose_location_address(r.get("addresses"))
    return a.get("city") if a else None


def extract_state(r: dict) -> t.Optional[str]:
    a = choose_location_address(r.get("addresses"))
    return a.get("state") if a else None


def extract_zip(r: dict) -> t.Optional[str]:
    a = choose_location_address(r.get("addresses"))
    return a.get("postal_code") if a else None  # ZIP or ZIP+4


def extract_first_name(r: dict) -> t.Optional[str]:
    return _safe(r, ["basic", "first_name"])


def extract_last_name(r: dict) -> t.Optional[str]:
    return _safe(r, ["basic", "last_name"])


def extract_last_updated_epoch(r: dict) -> t.Optional[int]:
    return r.get("last_updated_epoch")  # provided by NPI API


def epoch_to_iso(epoch: t.Optional[int]) -> t.Optional[str]:
    if epoch is None: return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    except Exception:
        return None


def is_after_bookmark(record_epoch: t.Optional[int],
                      bookmark_iso: t.Optional[str]) -> bool:
    if not bookmark_iso: return True
    if record_epoch is None: return True
    try:
        rec_dt = datetime.fromtimestamp(int(record_epoch), tz=timezone.utc)
        bm = datetime.fromisoformat(bookmark_iso)
        return rec_dt > bm
    except Exception:
        return True


# ---------- SDK functions----------


def schema(configuration: dict):
    """
    Declare only the table + PK; let Fivetran infer other columns & types
    (SDK best practice).
    """
    return [
        {
            "table": "npi_providers",
            "primary_key": ["npi"]
        },
    ]

    # def _fetch_page(api_base: str, limit: int, skip: int, timeout: int) -> list:
    """
    Call NPI Registry v2.1 with pagination. We keep filters client-side initially.
    Docs: https://npiregistry.cms.hhs.gov/api-page
    """
    url = api_base.rstrip("/") + "/"
    params = {"version": "2.1", "limit": limit, "skip": skip}
    headers = {
        "User-Agent": "SmarterDoc NPI Connector (contact: team@example.com)"
    }
    resp = rq.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json() or {}
    return payload.get("results", []) or []


# only want NYC doctors
def _fetch_page_filtered(
    api_base: str,
    limit: int,
    skip: int,
    timeout: int,
    postal_prefix: str,
    taxonomy_desc: str,
) -> list:
    """
    Filtered call using practice LOCATION, postal_code wildcard, and taxonomy_description.
    API params reference (v2.1): city, state, postal_code(wildcard allowed), address_purpose, taxonomy_description, limit/skip.
    """
    url = api_base.rstrip("/") + "/"
    params = {
        "version": "2.1",
        "limit": limit,
        "skip": skip,
        "address_purpose": "location",  # practice location only
        "postal_code": f"{postal_prefix}*",  # NYC ZIP block
        "taxonomy_description": taxonomy_desc,  # specialty filter
        "state": "NY",
    }
    headers = {
        "User-Agent": "SmarterDoc NPI Connector (contact: team@example.com)"
    }
    resp = rq.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json() or {}
    return payload.get("results", []) or []


def _passes_filters(r: dict, states: t.Optional[t.Set[str]],
                    tax_codes: t.Optional[t.Set[str]]) -> bool:
    if states:
        st = (extract_state(r) or "").upper()
        if st not in states:
            return False
    if tax_codes:
        txy = choose_primary_taxonomy(r.get("taxonomies"))
        code = (txy.get("code") if txy else None) or ""
        if code not in tax_codes:
            return False
    return True


def update(configuration: dict, state: dict):
    log.info("npi_registry: starting sync (NYC + specific specialties only)")

    api_base = configuration.get("api_base",
                                 "https://npiregistry.cms.hhs.gov/api/")
    page_size = int(configuration.get("page_size", 200))
    timeout_s = int(configuration.get("request_timeout_seconds", 30))
    backoff_s = float(configuration.get("request_backoff_seconds", 0.25))
    max_pages = configuration.get("max_pages_per_sync")
    max_pages = int(max_pages) if max_pages not in (None, "") else None

    # Configurable lists; fall back to safe NYC defaults
    nyc_zip_prefixes = configuration.get("nyc_zip_prefixes",
                                         DEFAULT_NYC_ZIP_PREFIXES)
    taxonomy_codes = configuration.get("taxonomy_codes",
                                       DEFAULT_TAXONOMY_CODES)

    bookmark_iso = state.get("last_updated_at")
    total_rows = 0
    shards_seen = 0
    pages = 0

    for zip_prefix in nyc_zip_prefixes:
        for tcode in taxonomy_codes:
            shards_seen += 1
            skip = 0
            while True:
                if max_pages is not None and pages >= max_pages:
                    log.info(f"stopping due to max_pages_per_sync={max_pages}")
                    op.checkpoint(state={"last_updated_at": bookmark_iso})
                    return

                results = _fetch_page_filtered(api_base, page_size, skip,
                                               timeout_s, zip_prefix, tcode)
                pages += 1
                if not results:
                    break

                for r in results:
                    rec_epoch = extract_last_updated_epoch(r)
                    if bookmark_iso and not is_after_bookmark(
                            rec_epoch, bookmark_iso):
                        continue

                    record_iso = epoch_to_iso(rec_epoch)
                    row = {
                        "npi": str(r.get("number") or ""),
                        "first_name": extract_first_name(r),
                        "last_name": extract_last_name(r),
                        "primary_specialty_desc": extract_primary_desc(r),
                        "city": extract_city(r),
                        "state": extract_state(r),
                        "zip": extract_zip(r),
                        "last_updated_at": record_iso,
                        "raw": r,
                    }
                    if not row["npi"]:
                        continue

                    op.upsert(table="npi_providers", data=row)
                    total_rows += 1

                    if record_iso and (bookmark_iso is None
                                       or record_iso > bookmark_iso):
                        bookmark_iso = record_iso

                if len(results) < page_size:
                    break
                skip += page_size
                time.sleep(backoff_s)

    op.checkpoint(state={"last_updated_at": bookmark_iso})
    log.info(
        f"npi_registry: shards={shards_seen}, pages={pages}, rows={total_rows}, bookmark={bookmark_iso}"
    )


# Connector object
connector = Connector(update=update, schema=schema)

if __name__ == "__main__":
    try:
        with open("configuration.json", "r") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    connector.debug(configuration=cfg)
