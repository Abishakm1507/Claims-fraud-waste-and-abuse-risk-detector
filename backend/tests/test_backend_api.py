from __future__ import annotations


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_loaded"]["claims"] > 0
    assert payload["data_loaded"]["providers"] > 0


def test_stats_overview_endpoint(client):
    response = client.get("/api/v1/stats/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_claims"] > 0
    assert payload["total_providers"] > 0
    assert payload["risk_distribution"]["CRITICAL"] >= 0
    assert payload["top_risk_factors"]


def test_claims_listing_endpoint(client):
    response = client.get("/api/v1/claims?page=1&page_size=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2
    assert payload["total"] > 0


def test_claim_detail_endpoint_happy_path(client, repo):
    claim_id = str(repo.claims_df.iloc[0]["claim_id"])
    response = client.get(f"/api/v1/claims/{claim_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["claim"]["claim_id"] == claim_id
    assert "investigation" in payload
    assert "shap" in payload
    assert "genai_narrative" in payload


def test_claim_detail_endpoint_not_found(client):
    response = client.get("/api/v1/claims/NOT_A_REAL_CLAIM")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CLAIM_NOT_FOUND"


def test_provider_detail_endpoint_happy_path(client, repo):
    provider_npi = str(repo.providers_df.iloc[0]["npi"])
    response = client.get(f"/api/v1/providers/{provider_npi}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"]["npi"] == provider_npi
    assert payload["investigation"]["provider_npi"] == provider_npi
    assert payload["provider_evidence"] is not None
    assert "exclusion_status" in payload["provider_evidence"]


def test_provider_detail_has_single_consistent_evidence_shape(client):
    for npi in ["1003078684", "1003000134"]:
        response = client.get(f"/api/v1/providers/{npi}")
        assert response.status_code == 200
        payload = response.json()
        assert "provider_evidence" in payload
        assert "provider_evidence" not in payload["provider"]
        evidence = payload["provider_evidence"]
        assert evidence["exclusion_status"] in {"EXCLUDED", "NOT_FOUND"}
        assert evidence["leie_match"] is None or isinstance(evidence["leie_match"], dict)


def test_provider_detail_endpoint_not_found(client):
    response = client.get("/api/v1/providers/NOT_A_REAL_PROVIDER")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROVIDER_NOT_FOUND"


def test_investigation_run_endpoint(client, repo):
    claim_id = str(repo.claims_df.iloc[0]["claim_id"])
    response = client.post(f"/api/v1/investigations/{claim_id}/run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == claim_id
    assert payload["status"] == "started"


def test_claim_detail_with_ml_evidence_carrier(client, repo):
    """Verify carrier claim returns type-specific ML evidence."""
    # Find a carrier claim from the unified CSV
    carrier_claims = repo.claims_df[repo.claims_df["claim_type"] == "CARRIER"]
    if len(carrier_claims) > 0:
        claim_id = str(carrier_claims.iloc[0]["claim_id"])
        response = client.get(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["claim"]["claim_type"] == "CARRIER"
        assert payload["ml_evidence"] is not None
        ml_ev = payload["ml_evidence"]
        assert ml_ev["claim_type"] == "CARRIER"
        assert ml_ev["ensemble_score"] >= 0
        assert "isolation_forest" in ml_ev["model_scores"]
        assert "lof" in ml_ev["model_scores"]
        assert "ocsvm" in ml_ev["model_scores"]
        assert ml_ev.get("model_consensus") is None  # Carrier doesn't have consensus (excluded when None)
        assert "source_pipeline" in ml_ev


def test_claim_detail_with_ml_evidence_inpatient(client, repo):
    """Verify inpatient claim returns type-specific ML evidence with consensus."""
    # Find an inpatient claim from the unified CSV
    inpatient_claims = repo.claims_df[repo.claims_df["claim_type"] == "INPATIENT"]
    if len(inpatient_claims) > 0:
        claim_id = str(inpatient_claims.iloc[0]["claim_id"])
        response = client.get(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["claim"]["claim_type"] == "INPATIENT"
        assert payload["ml_evidence"] is not None
        ml_ev = payload["ml_evidence"]
        assert ml_ev["claim_type"] == "INPATIENT"
        assert ml_ev["ensemble_score"] >= 0
        assert "isolation_forest" in ml_ev["model_scores"]
        assert "lof" in ml_ev["model_scores"]
        assert "ocsvm" in ml_ev["model_scores"]
        assert ml_ev.get("model_consensus") is not None  # Inpatient has consensus
        assert isinstance(ml_ev.get("model_consensus_count"), (int, type(None)))
        # risk_percentile may be excluded if None


def test_claim_detail_with_ml_evidence_outpatient(client, repo):
    """Verify outpatient claim returns type-specific ML evidence with 44 features."""
    # Find an outpatient claim from the unified CSV
    outpatient_claims = repo.claims_df[repo.claims_df["claim_type"] == "OUTPATIENT"]
    if len(outpatient_claims) > 0:
        claim_id = str(outpatient_claims.iloc[0]["claim_id"])
        response = client.get(f"/api/v1/claims/{claim_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["claim"]["claim_type"] == "OUTPATIENT"
        assert payload["ml_evidence"] is not None
        ml_ev = payload["ml_evidence"]
        assert ml_ev["claim_type"] == "OUTPATIENT"
        assert ml_ev["ensemble_score"] >= 0
        assert "isolation_forest" in ml_ev["model_scores"]
        assert "lof" in ml_ev["model_scores"]
        assert "ocsvm" in ml_ev["model_scores"]
        assert ml_ev.get("model_consensus") is None  # Outpatient doesn't have consensus (excluded when None)
        # Outpatient should have many feature columns preserved
        assert len(ml_ev["feature_evidence"]) > 30  # Should have many features


def test_claim_evidence_cache_completeness(repo):
    """Verify the claim evidence cache covers all 65,941 claims."""
    assert len(repo._claim_evidence_cache) == 65941
    # Verify each type is represented
    carrier_count = sum(1 for ev in repo._claim_evidence_cache.values() if ev.claim_type == "CARRIER")
    inpatient_count = sum(1 for ev in repo._claim_evidence_cache.values() if ev.claim_type == "INPATIENT")
    outpatient_count = sum(1 for ev in repo._claim_evidence_cache.values() if ev.claim_type == "OUTPATIENT")
    assert carrier_count == 6665
    assert inpatient_count == 20867
    assert outpatient_count == 38409


def test_report_endpoint(client, repo):
    claim_id = str(repo.claims_df.iloc[0]["claim_id"])
    response = client.get(f"/api/v1/reports/{claim_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == claim_id
    assert payload["report_type"] == "investigation_report"


def test_chat_endpoint_stub(client):
    response = client.post("/api/v1/chat", json={"message": "hello", "case_id": "CASE-123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "stub"
    assert "CASE-123" in payload["response"] or payload["response"]


def test_data_integrity_check(repo):
    """Verify data integrity check ran and reports healthy status."""
    assert repo.integrity_check is not None
    assert repo.integrity_check.carrier_count == 6665
    assert repo.integrity_check.inpatient_count == 20867
    assert repo.integrity_check.outpatient_count == 38409
    assert repo.integrity_check.unified_count == 65941
    assert repo.integrity_check.total_unique_claims == 65941
    # Verify no duplicates or collisions
    assert len(repo.integrity_check.carrier_duplicates) == 0
    assert len(repo.integrity_check.inpatient_duplicates) == 0
    assert len(repo.integrity_check.outpatient_duplicates) == 0
    assert len(repo.integrity_check.cross_type_collisions) == 0
    # Status should be healthy
    assert repo.integrity_check.is_healthy == True


def test_stats_overview_with_per_type_breakdown(client):
    """Verify stats endpoint includes per-claim-type breakdown."""
    response = client.get("/api/v1/stats/overview")
    assert response.status_code == 200
    payload = response.json()
    # Verify overall stats
    assert payload["total_claims"] == 65941
    assert payload["total_providers"] > 0
    # Verify per-type breakdown exists
    assert "per_claim_type" in payload
    per_type = payload["per_claim_type"]
    # Verify each type has required fields
    for claim_type in ["CARRIER", "INPATIENT", "OUTPATIENT"]:
        assert claim_type in per_type
        assert "count" in per_type[claim_type]
        assert "avg_ensemble_score" in per_type[claim_type]
        assert "risk_band_distribution" in per_type[claim_type]
        # Verify risk band distribution has all four levels
        dist = per_type[claim_type]["risk_band_distribution"]
        for band in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert band in dist
    # Verify counts match expectations
    assert per_type["CARRIER"]["count"] == 6665
    assert per_type["INPATIENT"]["count"] == 20867
    assert per_type["OUTPATIENT"]["count"] == 38409


def test_claims_list_includes_lean_ml_evidence(client):
    """Verify claims list includes lean ml_evidence (no feature_evidence)."""
    response = client.get("/api/v1/claims?page=1&page_size=2")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    for item in payload["items"]:
        # Verify ml_evidence is present with essential fields
        assert "ml_evidence" in item
        ml_ev = item["ml_evidence"]
        assert "claim_type" in ml_ev
        assert "ensemble_score" in ml_ev
        assert "risk_band" in ml_ev
        # Verify feature_evidence is NOT present (lean version)
        assert "feature_evidence" not in ml_ev


def test_claims_list_filter_by_claim_type(client):
    """Verify claims list can be filtered by claim_type."""
    response = client.get("/api/v1/claims?claim_type=CARRIER&page=1&page_size=5")
    assert response.status_code == 200
    payload = response.json()
    # All items should be carrier type
    for item in payload["items"]:
        assert item.get("claim_type") == "CARRIER"
        assert item["ml_evidence"]["claim_type"] == "CARRIER"


def test_report_includes_full_ml_evidence(client, repo):
    """Verify report endpoint includes full ml_evidence with feature_evidence."""
    claim_id = str(repo.claims_df.iloc[0]["claim_id"])
    response = client.get(f"/api/v1/reports/{claim_id}")
    assert response.status_code == 200
    payload = response.json()
    # Verify ml_evidence is present with all fields
    assert "ml_evidence" in payload
    ml_ev = payload["ml_evidence"]
    assert ml_ev is not None
    assert "claim_type" in ml_ev
    assert "ensemble_score" in ml_ev
    assert "risk_band" in ml_ev
    # Verify feature_evidence IS present (full version for reports)
    assert "feature_evidence" in ml_ev
    assert isinstance(ml_ev["feature_evidence"], dict)
