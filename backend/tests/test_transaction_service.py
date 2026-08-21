from app.services.transaction_service import get_team_transactions


def test_team_transactions_filters_and_caches_mlb_payload(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(url: str, timeout: int):
        calls.append(url)
        return {
            "transactions": [
                {
                    "id": 1,
                    "date": "2026-08-02",
                    "effectiveDate": "2026-08-02",
                    "person": {"id": 100, "fullName": "Test Pitcher"},
                    "toTeam": {"id": 135, "name": "San Diego Padres"},
                    "typeCode": "SC",
                    "typeDesc": "Status Change",
                    "description": "San Diego Padres placed RHP Test Pitcher on the 15-day injured list.",
                },
                {
                    "id": 2,
                    "date": "2026-08-01",
                    "person": {"id": 200, "fullName": "Other Player"},
                    "toTeam": {"id": 109, "name": "Arizona Diamondbacks"},
                    "typeDesc": "Status Change",
                    "description": "Arizona Diamondbacks recalled Other Player from the minors.",
                },
            ]
        }

    monkeypatch.setattr("app.services.transaction_service.fetch_json", fake_fetch)
    padres = get_team_transactions(2026, "SD", 135, data_dir=tmp_path)
    padres_again = get_team_transactions(2026, "SD", 135, data_dir=tmp_path)
    refreshed = get_team_transactions(2026, "SD", 135, data_dir=tmp_path, force_refresh=True)

    assert len(calls) == 2
    assert [row.player_name for row in padres.transactions] == ["Test Pitcher"]
    assert padres.transactions[0].category == "Injury"
    assert padres_again.transactions[0].transaction_id == 1
    assert refreshed.transactions[0].category == "Injury"
    assert (tmp_path / "MLB2026" / "mlb_2026_transactions.json").exists()
