import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.hubapi.com"

DEFAULT_STAGE_MAP = {
    "appointmentscheduled": "Discovery",
    "qualifiedtobuy": "Demo",
    "presentationscheduled": "Demo",
    "decisionmakerboughtin": "Proposal",
    "contractsent": "Negotiation",
    "closedwon": None,
    "closedlost": None,
}

REQUIRED_COLS = [
    "deal_id", "account_name", "stage", "amount", "close_date",
    "days_in_stage", "last_activity_date", "owner", "next_step",
    "industry", "employee_count",
]


class HubSpotError(Exception):
    pass


def is_connected() -> bool:
    return bool(os.getenv("HUBSPOT_ACCESS_TOKEN"))


def get_pipelines() -> list[dict]:
    token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        return []
    try:
        resp = requests.get(
            f"{BASE_URL}/crm/v3/pipelines/deals",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return [{"id": p["id"], "label": p["label"]} for p in resp.json().get("results", [])]
    except Exception:
        return []


def fetch_pipeline(pipeline_id: str | None = None) -> pd.DataFrame:
    token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise HubSpotError("HUBSPOT_ACCESS_TOKEN not set")

    headers = {"Authorization": f"Bearer {token}"}
    effective_pipeline_id = pipeline_id or os.getenv("HUBSPOT_PIPELINE_ID")

    # 1. Get stage map
    stage_map = _get_stage_map(headers, effective_pipeline_id)

    # 2. Get owner map
    owner_map = _get_owner_map(headers)

    # 3. Fetch deals (paginated)
    deals = _fetch_all_deals(headers)

    # 4. Transform to DataFrame
    rows = []
    for deal in deals:
        props = deal.get("properties", {})
        stage = _resolve_stage(props.get("dealstage", ""), stage_map)
        if stage is None:
            continue  # Closed or unmapped stage — exclude

        owner_id = props.get("hubspot_owner_id", "")
        owner_name = owner_map.get(owner_id, owner_id)

        rows.append({
            "deal_id": str(deal["id"]),
            "account_name": props.get("dealname") or "Unknown",
            "stage": stage,
            "amount": float(props.get("amount") or 0),
            "close_date": _ms_to_date(_safe_int(props.get("closedate"))),
            "days_in_stage": _ms_to_days(_safe_int(props.get("hs_time_in_current_stage"))),
            "last_activity_date": _ms_to_date(_safe_int(props.get("notes_last_updated"))),
            "owner": owner_name,
            "next_step": props.get("hs_next_step") or "",
            "industry": props.get("industry") or "Unknown",
            "employee_count": int(props.get("numberofemployees") or 0),
        })

    return pd.DataFrame(rows, columns=REQUIRED_COLS) if rows else pd.DataFrame(columns=REQUIRED_COLS)


# ── Private helpers ────────────────────────────────────────────────────────

def _ms_to_date(ms: int | None) -> str:
    if ms is None or ms == 0:
        return str(date.today())
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _ms_to_days(ms: int | None) -> int:
    if ms is None:
        return 0
    return max(0, int(ms / 86_400_000))


def _resolve_stage(stage_id: str, stage_map: dict) -> str | None:
    return stage_map.get(stage_id)


def _safe_int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _get_stage_map(headers: dict, pipeline_id: str | None) -> dict:
    try:
        resp = requests.get(
            f"{BASE_URL}/crm/v3/pipelines/deals",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        pipelines = resp.json().get("results", [])
    except Exception as e:
        raise HubSpotError(f"Failed to fetch pipelines: {e}")

    # Pick the right pipeline
    if pipeline_id:
        pipeline = next((p for p in pipelines if p["id"] == pipeline_id), None)
    else:
        pipeline = pipelines[0] if pipelines else None

    if not pipeline:
        raise HubSpotError(f"Pipeline '{pipeline_id}' not found")

    # Start with default map (keyed on stage IDs)
    stage_map = dict(DEFAULT_STAGE_MAP)

    # Override with any user-supplied map
    user_map_str = os.getenv("HUBSPOT_STAGE_MAP", "")
    if user_map_str:
        try:
            stage_map.update(json.loads(user_map_str))
        except json.JSONDecodeError:
            pass  # Silently ignore malformed JSON

    return stage_map


def _get_owner_map(headers: dict) -> dict:
    try:
        resp = requests.get(
            f"{BASE_URL}/crm/v3/owners",
            headers=headers,
            params={"limit": 500},
            timeout=10,
        )
        resp.raise_for_status()
        owners = resp.json().get("results", [])
        return {
            str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
            for o in owners
        }
    except Exception:
        return {}


def _fetch_all_deals(headers: dict) -> list[dict]:
    properties = [
        "dealname", "dealstage", "amount", "closedate",
        "hs_time_in_current_stage", "notes_last_updated",
        "hubspot_owner_id", "hs_next_step", "industry", "numberofemployees",
    ]
    deals = []
    after = None
    while True:
        params = {
            "limit": 100,
            "properties": ",".join(properties),
        }
        if after:
            params["after"] = after

        try:
            resp = requests.get(
                f"{BASE_URL}/crm/v3/objects/deals",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            raise HubSpotError(f"Failed to fetch deals: {e}")

        data = resp.json()
        deals.extend(data.get("results", []))

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

    return deals
