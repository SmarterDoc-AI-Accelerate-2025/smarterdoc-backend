import json
import time
import typing as t
from datetime import datetime, timezone

import requests as rq
from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Operations as op
from fivetran_connector_sdk import Logging as log

DEFAULT_NYC_ZIP_PREFIXES = [
    "100", "101", "102", "103", "104", "111", "112", "113", "114", "116"
]
DEFAULT_TAXONOMY_DESCRIPTIONS = [
    "Reproductive Endocrinology", "Orthopaedic Surgery"
]


def epoch_to_iso(epoch: t.Optional[int]) -> t.Optional[str]:
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    except Exception:
        return None


def is_after_bookmark(record_epoch: t.Optional[int],
                      bookmark_iso: t.Optional[str]) -> bool:
    if not bookmark_iso:
        return True
    if record_epoch is None:
        return True
    try:
        rec_dt = datetime.fromtimestamp(int(record_epoch), tz=timezone.utc)
        bm = datetime.fromisoformat(bookmark_iso)
        return rec_dt > bm
    except Exception:
        return True


def _safe(d: dict, *path, default=None):
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
        if str(txy.get("primary", "")).lower() in ("true", "1", "y", "yes"):
            return txy
    return taxonomies[0]


def pick_location_addr(addresses: t.Optional[list]) -> t.Optional[dict]:
    if not addresses: return None
    loc, mail = None, None
    for a in addresses:
        purpose = (a.get("address_purpose") or "").upper()
        if purpose == "LOCATION" and loc is None: loc = a
        elif purpose == "MAILING" and mail is None: mail = a
    return loc or mail or addresses[0]


def city_state_zip(r: dict):
    a = pick_location_addr(r.get("addresses"))
    if not a: return None, None, None
    return a.get("city"), a.get("state"), a.get("postal_code")


def first_last(r: dict):
    return _safe(r, "basic", "first_name"), _safe(r, "basic", "last_name")


def last_updated_epoch(r: dict) -> t.Optional[int]:
    return r.get("last_updated_epoch")


# ----------External API calls----------
def npi_page(api_base: str, limit: int, skip: int, timeout: int,
             postal_prefix: str, taxonomy_desc: str) -> list:
    """Filtered NPI v2.1 request (server-side!): LOCATION+NYC ZIP prefix + taxonomy desc."""
    url = api_base.rstrip("/") + "/"
    params = {
        "version": "2.1",
        "limit": limit,
        "skip": skip,
        "address_purpose": "location",
        "postal_code": f"{postal_prefix}*",
        "taxonomy_description": taxonomy_desc,
        "state": "NY",
    }
    headers = {
        "User-Agent": "SmarterDoc PubMed Connector (contact: team@example.com)"
    }
    resp = rq.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return (resp.json() or {}).get("results", []) or []


def search_orcid(first: str, last: str, city: t.Optional[str],
                 state: t.Optional[str], use_location_filter: bool,
                 http_timeout: int) -> t.Optional[str]:
    """
    Name-first ORCID search. Optional location filter (off by default; can hurt recall).
    """
    base = "https://pub.orcid.org/v3.0/expanded-search/"
    q = [f'given-names:"{first}"', f'family-name:"{last}"']
    # location filter is optional (ORCID expects org/affiliation; city/state can reduce hits)
    if use_location_filter and city:
        q.append(f'address-city:"{city}"')
    if use_location_filter and state:
        q.append(f'address-region:"{state}"')
    params = {"q": " AND ".join(q), "rows": 1}
    headers = {
        "Accept": "application/json",
        "User-Agent": "SmarterDoc PubMed Connector"
    }
    r = rq.get(base, params=params, headers=headers, timeout=http_timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    items = (r.json() or {}).get("expanded-result", []) or []
    if not items:
        return None
    # Take the first best hit
    return items[0].get("orcid-id") or None


def pubmed_esearch_by_author(first: str, last: str, email: str,
                             api_key: t.Optional[str], max_articles: int,
                             http_timeout: int) -> list[str]:
    """
    PubMed ESearch by author name, returns PMIDs (as strings).
    """
    term = f'"{last} {first}"[Author]'
    params = {
        "db": "pubmed",
        "retmode": "json",
        "retmax": max_articles,
        "term": term,
        "email": email
    }
    if api_key:
        params["api_key"] = api_key
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    r = rq.get(url, params=params, timeout=http_timeout)
    r.raise_for_status()
    js = r.json() or {}
    return (js.get("esearchresult", {}).get("idlist", [])) or []


# ---------- Fivetran SDK: schema + update ----------
def schema(configuration: dict):
    return [
        {
            "table": "orcid_ids",
            "primary_key": ["npi"]
        },
        {
            "table": "pubmed_articles",
            "primary_key": ["pmid"]
        },
        {
            "table": "provider_publications",
            "primary_key": ["npi", "pmid"]
        },
    ]


def update(configuration: dict, state: dict):
    log.info("pubmed_orcid: starting sync")

    # --- config
    api_base = configuration.get("api_base",
                                 "https://npiregistry.cms.hhs.gov/api/")
    page_size = int(configuration.get("page_size", 200))
    timeout_s = int(configuration.get("request_timeout_seconds", 30))
    backoff_s = float(configuration.get("request_backoff_seconds", 0.25))
    max_pages = configuration.get("max_pages_per_sync")
    max_pages = int(max_pages) if max_pages not in (None, "") else None
    max_doctors = int(configuration.get("max_doctors_per_sync",
                                        150))  # hard cap
    processed_doctors = 0

    nyc_zip_prefixes = configuration.get("nyc_zip_prefixes",
                                         DEFAULT_NYC_ZIP_PREFIXES)
    taxonomy_descriptions = configuration.get("taxonomy_descriptions",
                                              DEFAULT_TAXONOMY_DESCRIPTIONS)

    email = configuration.get("email")  # REQUIRED by NCBI
    if not email:
        raise ValueError(
            "Configuration requires 'email' for PubMed E-utilities.")
    ncbi_api_key = configuration.get("ncbi_api_key")  # optional

    max_articles_per_doctor = int(
        configuration.get("max_articles_per_doctor", 50))
    use_location_filter = bool(configuration.get("use_location_filter", False))

    # incremental bookmark (ISO)
    bookmark_iso = state.get("last_updated_at")

    total_rows = 0
    pages = 0
    shards = 0

    for zip_prefix in nyc_zip_prefixes:
        for tdesc in taxonomy_descriptions:
            shards += 1
            skip = 0
            while True:
                if max_pages is not None and pages >= max_pages:
                    log.info(
                        f"pubmed_orcid: stopping due to max_pages_per_sync={max_pages}"
                    )
                    op.checkpoint(state={"last_updated_at": bookmark_iso})
                    return

                providers = npi_page(api_base, page_size, skip, timeout_s,
                                     zip_prefix, tdesc)
                pages += 1
                if not providers:
                    break

                for r in providers:
                    if processed_doctors >= max_doctors:
                        log.info(
                            f"pubmed_orcid: hit max_doctors_per_sync={max_doctors}, stopping early"
                        )
                        op.checkpoint(state={"last_updated_at": bookmark_iso})
                        return

                    rec_epoch = last_updated_epoch(r)
                    if bookmark_iso and not is_after_bookmark(
                            rec_epoch, bookmark_iso):
                        continue  # incremental skip

                    npi = str(r.get("number") or "")
                    if not npi:
                        continue

                    first, last = first_last(r)
                    city, st, _ = city_state_zip(r)
                    specialty_desc = (choose_primary_taxonomy(
                        r.get("taxonomies")) or {}).get("desc")

                    orcid_id = None
                    try:
                        if first and last:
                            orcid_id = search_orcid(first, last, city, st,
                                                    use_location_filter,
                                                    timeout_s)
                    except Exception as e:
                        log.warning(
                            f"ORCID lookup failed for {first} {last}: {e}")

                    op.upsert(
                        "orcid_ids", {
                            "npi": npi,
                            "orcid": orcid_id,
                            "matched_name":
                            f"{first or ''} {last or ''}".strip(),
                            "city": city,
                            "state": st,
                            "specialty": specialty_desc
                        })

                    # PubMed ESearch by author name (keeps spend tiny & avoids extra calls)
                    pmids: list[str] = []
                    try:
                        if first and last:
                            pmids = pubmed_esearch_by_author(
                                first, last, email, ncbi_api_key,
                                max_articles_per_doctor, timeout_s)
                    except Exception as e:
                        log.warning(
                            f"PubMed search failed for {first} {last}: {e}")
                        pmids = []

                    # articles + bridge
                    for pmid in pmids:
                        op.upsert(
                            "pubmed_articles", {
                                "pmid": pmid,
                                "url":
                                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                            })
                        op.upsert(
                            "provider_publications", {
                                "npi": npi,
                                "pmid": pmid,
                                "search_method": "author_name"
                            })
                        total_rows += 1

                    # advance bookmark
                    record_iso = epoch_to_iso(rec_epoch)
                    if record_iso and (bookmark_iso is None
                                       or record_iso > bookmark_iso):
                        bookmark_iso = record_iso

                if len(providers) < page_size:
                    break
                skip += page_size
                time.sleep(backoff_s)

    op.checkpoint(state={"last_updated_at": bookmark_iso})
    log.info(
        f"pubmed_orcid: shards={shards}, pages={pages}, rows={total_rows}, bookmark={bookmark_iso}"
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
