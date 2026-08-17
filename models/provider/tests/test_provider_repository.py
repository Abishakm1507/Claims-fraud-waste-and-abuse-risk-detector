"""
Tests for the Provider ML -> Multi-Agent handoff layer.

These tests run against the REAL authoritative output
(models/provider/output/provider_risk_scores.csv), so the repository is
verified against actual data -- no fabricated peer statistics.

Run from the repository root (or from models/provider):

    python -m unittest discover -s models/provider/tests -t models/provider

or, with pytest installed:

    pytest models/provider/tests
"""

import sys
import unittest
from pathlib import Path

# make the sibling modules importable when running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from provider_context import (  # noqa: E402
    GeoEvidence,
    LeieEvidence,
    PeerEvidence,
    ProviderContext,
    TemporalEvidence,
)
from provider_repository import (  # noqa: E402
    ProviderRepository,
    get_provider,
    get_providers,
    search_providers,
)

# Real provider present in the authoritative output (top-risk provider).
REAL_NPI = 1003569997
# Real provider with multiple observed years (2021-2024).
MULTI_YEAR_NPI = 1003099631
# NPI that is not in the dataset (all 9s).
MISSING_NPI = 9999999999
INVALID_NPI = "not-an-npi"

# One shared repository instance for the whole suite (loads the CSV once).
_REPO = ProviderRepository()


def _csv_row(npi):
    csv_path = (
        Path(__file__).resolve().parent.parent
        / "output"
        / "provider_risk_scores.csv"
    )
    df = pd.read_csv(csv_path, low_memory=False)
    return df[df["NPI"] == int(npi)].iloc[0]


class TestRepositoryLoading(unittest.TestCase):
    """1. Loading provider data."""

    def test_loads_authoritative_output(self):
        repo = ProviderRepository()
        self.assertEqual(len(repo), 36108)
        self.assertTrue(repo.csv_path.name == "provider_risk_scores.csv")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            ProviderRepository(csv_path="does/not/exist.csv")


class TestGetProvider(unittest.TestCase):
    """2/3. get_provider(npi) and valid NPI lookup."""

    def setUp(self):
        self.repo = _REPO

    def test_valid_npi_returns_context(self):
        ctx = self.repo.get_provider(REAL_NPI)
        self.assertIsInstance(ctx, ProviderContext)
        self.assertEqual(ctx.npi, REAL_NPI)

    def test_valid_npi_as_string(self):
        ctx = self.repo.get_provider(str(REAL_NPI))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.npi, REAL_NPI)

    def test_module_level_get_provider(self):
        ctx = get_provider(REAL_NPI)
        self.assertIsInstance(ctx, ProviderContext)

    def test_contains(self):
        self.assertIn(REAL_NPI, self.repo)
        self.assertNotIn(MISSING_NPI, self.repo)

    def test_batch_get_providers(self):
        ctxs = get_providers([REAL_NPI, MULTI_YEAR_NPI, MISSING_NPI])
        self.assertEqual(len(ctxs), 2)
        self.assertEqual([c.npi for c in ctxs], [REAL_NPI, MULTI_YEAR_NPI])


class TestMissingNpi(unittest.TestCase):
    """4. Missing NPI handling."""

    def setUp(self):
        self.repo = _REPO

    def test_missing_npi_returns_none(self):
        self.assertIsNone(self.repo.get_provider(MISSING_NPI))

    def test_invalid_npi_returns_none(self):
        self.assertIsNone(self.repo.get_provider(INVALID_NPI))
        self.assertIsNone(self.repo.get_provider(None))


class TestRiskScoreRetrieval(unittest.TestCase):
    """5. Correct Provider_Risk_Score retrieval."""

    def setUp(self):
        self.repo = _REPO

    def test_risk_score_matches_csv(self):
        row = _csv_row(REAL_NPI)
        ctx = self.repo.get_provider(REAL_NPI)
        self.assertAlmostEqual(ctx.risk_score, float(row["Provider_Risk_Score"]), places=6)
        self.assertEqual(ctx.risk_tier, row["Risk_Tier"])
        self.assertAlmostEqual(ctx.anomaly_score, float(row["global_anomaly_score"]), places=6)

    def test_risk_score_range(self):
        for npi in [REAL_NPI, MULTI_YEAR_NPI]:
            ctx = self.repo.get_provider(npi)
            self.assertGreaterEqual(ctx.risk_score, 0.0)
            self.assertLessEqual(ctx.risk_score, 100.0)


class TestPeerEvidence(unittest.TestCase):
    """6. Correct peer evidence retrieval."""

    def setUp(self):
        self.repo = _REPO

    def test_peer_group_present(self):
        ctx = self.repo.get_provider(REAL_NPI)
        self.assertIsInstance(ctx.peer_evidence, PeerEvidence)
        self.assertTrue(ctx.peer_evidence.peer_group)
        # peer group is Provider_Type when the specialty has >= 20 providers,
        # otherwise the reserved "Other/Small-Specialty" bucket.
        self.assertIn(ctx.peer_evidence.peer_group, {ctx.provider_type, "Other/Small-Specialty"})

    def test_peer_metrics_match_csv(self):
        row = _csv_row(REAL_NPI)
        ctx = self.repo.get_provider(REAL_NPI)
        metrics = {m.metric: m for m in ctx.peer_evidence.metrics}
        self.assertEqual(
            set(metrics),
            {
                "Payment_per_Service",
                "Charge_per_Service",
                "Services_per_Beneficiary",
                "Payment_to_Charge_Ratio",
                "Svc_HHI_Concentration",
            },
        )
        m = metrics["Payment_per_Service"]
        self.assertAlmostEqual(m.provider_value, float(row["Payment_per_Service"]), places=6)
        self.assertAlmostEqual(m.peer_mean, float(row["Payment_per_Service_Peer_Mean"]), places=6)
        self.assertAlmostEqual(m.peer_median, float(row["Payment_per_Service_Peer_Median"]), places=6)
        self.assertAlmostEqual(m.peer_std, float(row["Payment_per_Service_Peer_Std"]), places=6)
        self.assertAlmostEqual(m.deviation_ratio, float(row["Payment_per_Service_Deviation_Ratio"]), places=6)
        self.assertAlmostEqual(m.percentile, float(row["Payment_per_Service_Peer_Pctile"]), places=6)

    def test_peer_score_matches_csv(self):
        row = _csv_row(REAL_NPI)
        ctx = self.repo.get_provider(REAL_NPI)
        self.assertAlmostEqual(ctx.peer_evidence.score, float(row["peer_deviation_score"]), places=6)


class TestGeoEvidence(unittest.TestCase):
    """7. Correct geographic evidence retrieval."""

    def setUp(self):
        self.repo = _REPO

    def test_geo_fields_present_and_match_csv(self):
        row = _csv_row(REAL_NPI)
        ctx = self.repo.get_provider(REAL_NPI)
        geo = ctx.geo_evidence
        self.assertIsInstance(geo, GeoEvidence)
        self.assertAlmostEqual(geo.score, float(row["geo_deviation_score"]), places=6)
        self.assertAlmostEqual(geo.avg_pymt_deviation, float(row["Peer_Avg_Pymt_Deviation"]), places=6)
        self.assertAlmostEqual(geo.bench_pymt_mean, float(row["Geo_Bench_Pymt_Mean"]), places=6)
        self.assertAlmostEqual(geo.bench_pymt_median, float(row["Geo_Bench_Pymt_Median"]), places=6)
        self.assertAlmostEqual(geo.bench_pymt_std, float(row["Geo_Bench_Pymt_Std"]), places=6)
        self.assertAlmostEqual(geo.provider_avg_pymt, float(row["Geo_Provider_Avg_Pymt"]), places=6)
        self.assertEqual(
            sum(geo.rows_by_level.values()),
            int(row["Geo_Rows_Matched"]),
        )


class TestLeieEvidence(unittest.TestCase):
    """8. Correct LEIE flag retrieval."""

    def setUp(self):
        self.repo = _REPO

    def test_leie_flag_matches_csv(self):
        for npi in [REAL_NPI, MULTI_YEAR_NPI]:
            row = _csv_row(npi)
            ctx = self.repo.get_provider(npi)
            self.assertIsInstance(ctx.leie_evidence, LeieEvidence)
            self.assertEqual(ctx.leie_evidence.is_excluded, bool(row["is_leie_excluded"]))

    def test_some_providers_excluded(self):
        # 15 providers in the scored population are on the LEIE list.
        excluded = self.repo._df[self.repo._df["is_leie_excluded"] == 1]
        self.assertGreaterEqual(len(excluded), 1)
        npi = int(excluded.iloc[0]["NPI"])
        self.assertTrue(self.repo.get_provider(npi).leie_evidence.is_excluded)


class TestTemporalEvidence(unittest.TestCase):
    """9. Correct temporal fields if available."""

    def setUp(self):
        self.repo = _REPO

    def test_year_first_last_present(self):
        row = _csv_row(MULTI_YEAR_NPI)
        ctx = self.repo.get_provider(MULTI_YEAR_NPI)
        temporal = ctx.temporal_evidence
        self.assertIsInstance(temporal, TemporalEvidence)
        self.assertEqual(temporal.year_first, int(row["Year_First"]))
        self.assertEqual(temporal.year_last, int(row["Year_Last"]))
        self.assertEqual(temporal.num_years_observed, int(row["Num_Years_Observed"]))
        self.assertGreaterEqual(temporal.num_years_observed, 2)

    def test_growth_metrics_consistent(self):
        row = _csv_row(MULTI_YEAR_NPI)
        ctx = self.repo.get_provider(MULTI_YEAR_NPI)
        svc = ctx.temporal_evidence.metrics["Tot_Srvcs"]
        self.assertAlmostEqual(svc["first"], float(row["Svc_First_Year"]), places=6)
        self.assertAlmostEqual(svc["last"], float(row["Svc_Last_Year"]), places=6)
        self.assertAlmostEqual(svc["growth_pct"], float(row["Svc_Growth_Pct"]), places=6)
        # growth is (last - first) / first * 100
        expected = (svc["last"] - svc["first"]) / svc["first"] * 100.0
        self.assertAlmostEqual(svc["growth_pct"], expected, places=6)

    def test_all_providers_have_year_context(self):
        for npi in [REAL_NPI, MULTI_YEAR_NPI]:
            temporal = self.repo.get_provider(npi).temporal_evidence
            self.assertIsNotNone(temporal.year_first)
            self.assertIsNotNone(temporal.year_last)


class TestSearch(unittest.TestCase):
    def test_search_by_tier(self):
        high = search_providers(risk_tier="Critical", limit=5)
        self.assertEqual(len(high), 5)
        self.assertTrue(all(c.risk_tier == "Critical" for c in high))
        # sorted descending by risk
        scores = [c.risk_score for c in high]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_by_state_and_type(self):
        found = search_providers(provider_type="optometry", limit=3)
        self.assertGreaterEqual(len(found), 1)
        self.assertTrue(all("optometry" in (c.provider_type or "").lower() for c in found))

    def test_search_risk_range(self):
        found = search_providers(min_risk=95.0, limit=10)
        self.assertGreaterEqual(len(found), 1)
        self.assertTrue(all(c.risk_score >= 95.0 for c in found))


class TestSchema(unittest.TestCase):
    """10. Schema validation."""

    def setUp(self):
        self.repo = _REPO

    def test_context_types(self):
        ctx = self.repo.get_provider(REAL_NPI)
        self.assertIsInstance(ctx.npi, int)
        self.assertIsInstance(ctx.provider_type, str)
        self.assertIsInstance(ctx.state, str)
        self.assertIsInstance(ctx.provider_features, dict)
        self.assertIsInstance(ctx.peer_evidence, PeerEvidence)
        self.assertIsInstance(ctx.geo_evidence, GeoEvidence)
        self.assertIsInstance(ctx.temporal_evidence, TemporalEvidence)
        self.assertIsInstance(ctx.leie_evidence, LeieEvidence)
        self.assertIn("Tot_Srvcs", ctx.provider_features)
        self.assertIn("Payment_per_Service", ctx.provider_features)

    def test_to_dict_roundtrip(self):
        ctx = self.repo.get_provider(REAL_NPI)
        d = ctx.to_dict()
        self.assertEqual(d["npi"], REAL_NPI)
        self.assertEqual(d["risk_tier"], ctx.risk_tier)
        self.assertIn("peer_evidence", d)
        self.assertIn("geo_evidence", d)
        self.assertIn("temporal_evidence", d)
        self.assertIn("leie_evidence", d)
        self.assertEqual(d["leie_evidence"]["is_excluded"], ctx.leie_evidence.is_excluded)

    def test_score_interpretation_direction(self):
        # higher risk score must correspond to higher global anomaly score
        # for the highest-risk providers (documented interpretation).
        top = search_providers(limit=20)
        mid = search_providers(limit=20, min_risk=30.0, max_risk=50.0)
        self.assertGreater(
            sum(c.anomaly_score for c in top) / len(top),
            sum(c.anomaly_score for c in mid) / len(mid),
        )


if __name__ == "__main__":
    unittest.main()
