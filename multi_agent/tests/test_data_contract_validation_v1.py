from multi_agent.data_contract_validation import DataContractValidator


def test_real_data_contract_validation_reports_coverage_and_gaps():
    report = DataContractValidator().validate()

    assert report["contract_version"] == "1.0"
    assert report["claim_rows"] > 0
    assert report["provider_rows"] > 0
    assert report["claim_type_counts"]["CARRIER"] > 0
    assert report["claim_type_counts"]["INPATIENT"] > 0
    assert report["claim_type_counts"]["OUTPATIENT"] > 0
    assert report["can_populate_investigation_context"] is True
    assert report["can_produce_valid_investigation_case"] is True
    assert "claim_id" in report["required_fields"]["claim"]
    assert "npi" in report["required_fields"]["provider"]
    assert report["required_fields"]["claim"]["claim_id"]["status"] == "AVAILABLE"
    assert report["required_fields"]["provider"]["npi"]["status"] == "AVAILABLE"
    assert report["required_fields"]["claim"]["claim_type"]["status"] == "AVAILABLE"
    assert any(item["status"] in {"AVAILABLE", "NOT_AVAILABLE", "NOT_APPLICABLE"} for item in report["required_fields"]["claim"].values())
    assert isinstance(report["limitations"], list)
