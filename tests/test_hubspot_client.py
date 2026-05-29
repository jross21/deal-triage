from hubspot_client import _ms_to_date, _ms_to_days, _resolve_stage


def test_ms_to_date_valid():
    # 86_400_000 ms = exactly 1 day after epoch = 1970-01-02 UTC
    assert _ms_to_date(86_400_000) == "1970-01-02"


def test_ms_to_date_none():
    from datetime import date
    assert _ms_to_date(None) == str(date.today())


def test_ms_to_days_valid():
    assert _ms_to_days(86_400_000) == 1
    assert _ms_to_days(0) == 0


def test_ms_to_days_none():
    assert _ms_to_days(None) == 0


def test_resolve_stage_match():
    stage_map = {"appointmentscheduled": "Discovery", "qualifiedtobuy": "Demo"}
    assert _resolve_stage("appointmentscheduled", stage_map) == "Discovery"


def test_resolve_stage_no_match():
    assert _resolve_stage("closedwon", {"closedwon": None}) is None


def test_resolve_stage_unknown():
    assert _resolve_stage("unknownstage", {}) is None


def test_fetch_pipeline_returns_correct_schema(monkeypatch):
    """fetch_pipeline() returns DataFrame with all required columns."""
    from unittest.mock import MagicMock, patch
    import hubspot_client as hc

    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token")

    mock_pipelines = {
        "results": [{
            "id": "pipeline1",
            "label": "Sales Pipeline",
            "stages": [
                {"id": "appointmentscheduled", "label": "Appointment Scheduled"},
                {"id": "closedwon", "label": "Closed Won"},
            ]
        }]
    }
    mock_owners = {
        "results": [{"id": "owner1", "firstName": "Alice", "lastName": "Smith"}]
    }
    mock_deals = {
        "results": [{
            "id": "12345",
            "properties": {
                "dealname": "Test Deal",
                "dealstage": "appointmentscheduled",
                "amount": "50000",
                "closedate": "1748476800000",
                "hs_time_in_current_stage": "864000000",
                "notes_last_updated": "1748390400000",
                "hubspot_owner_id": "owner1",
                "hs_next_step": "Follow up",
                "industry": None,
                "numberofemployees": None,
            }
        }],
        "paging": {}
    }

    responses = [mock_pipelines, mock_owners, mock_deals]
    call_count = [0]

    def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = responses[call_count[0] % len(responses)]
        call_count[0] += 1
        return mock_resp

    with patch("hubspot_client.requests.get", side_effect=mock_get):
        df = hc.fetch_pipeline("pipeline1")

    required_cols = {
        "deal_id", "account_name", "stage", "amount", "close_date",
        "days_in_stage", "last_activity_date", "owner", "next_step",
        "industry", "employee_count"
    }
    assert required_cols.issubset(set(df.columns))
    assert len(df) == 1
    assert df.iloc[0]["stage"] == "Discovery"
    assert df.iloc[0]["owner"] == "Alice Smith"
    assert df.iloc[0]["days_in_stage"] == 10
