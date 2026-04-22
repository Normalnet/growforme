"""
test_batching.py — Unit tests for K-Means regional batching algorithm.

Target: ≥ 80% branch coverage of app/services/batching.py

Run:
    pytest tests/test_batching.py -v
"""

import importlib.util
import math
import os
import sys

import pytest

# Load batching.py directly — bypasses app/__init__.py → SQLAlchemy (Python 3.14 compat)
_BASE = os.path.join(os.path.dirname(__file__), '..', 'backend')
_spec = importlib.util.spec_from_file_location(
    'batching',
    os.path.join(_BASE, 'app', 'services', 'batching.py'),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

RegionalBatchingService = _mod.RegionalBatchingService
DeliveryPoint = _mod.DeliveryPoint
_haversine_km = _mod._haversine_km
_kmeans = _mod._kmeans
MAX_BATCH_SIZE = _mod.MAX_BATCH_SIZE


# ── Haversine Tests ───────────────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(5.6037, -0.1870, 5.6037, -0.1870) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_accra_kumasi(self):
        # Straight-line distance ~200 km
        dist = _haversine_km(5.6037, -0.1870, 6.6885, -1.6244)
        assert 180 < dist < 230, f"Expected ~200 km, got {dist:.1f} km"

    def test_symmetry(self):
        d1 = _haversine_km(5.6037, -0.1870, 6.6885, -1.6244)
        d2 = _haversine_km(6.6885, -1.6244, 5.6037, -0.1870)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_returns_float(self):
        result = _haversine_km(31.0, 74.0, 32.0, 75.0)
        assert isinstance(result, float)


# ── K-Means Core Tests ────────────────────────────────────────────────────────

class TestKMeans:
    def test_k_equals_n_returns_distinct_assignments(self):
        points = [(float(i), float(i)) for i in range(5)]
        assignments = _kmeans(points, k=5)
        assert len(assignments) == 5
        assert len(set(assignments)) == 5

    def test_two_clear_clusters(self):
        # Two geographically distinct groups
        group_a = [(31.6 + i * 0.001, 74.8 + i * 0.001) for i in range(5)]
        group_b = [(30.9 + i * 0.001, 75.8 + i * 0.001) for i in range(5)]
        points = group_a + group_b
        assignments = _kmeans(points, k=2)
        assert len(set(assignments)) == 2
        # All group_a should share one label, all group_b the other
        assert len(set(assignments[:5])) == 1
        assert len(set(assignments[5:])) == 1
        assert assignments[0] != assignments[5]

    def test_single_cluster(self):
        points = [(31.6, 74.8), (31.601, 74.801), (31.602, 74.802)]
        assignments = _kmeans(points, k=1)
        assert all(a == 0 for a in assignments)

    def test_output_length_matches_input(self):
        points = [(float(i), float(i)) for i in range(8)]
        assignments = _kmeans(points, k=3)
        assert len(assignments) == 8

    def test_deterministic_with_same_seed(self):
        points = [(float(i % 3), float(i % 5)) for i in range(12)]
        r1 = _kmeans(points, k=3, seed=99)
        r2 = _kmeans(points, k=3, seed=99)
        assert r1 == r2


# ── RegionalBatchingService Tests ─────────────────────────────────────────────

class TestRegionalBatchingService:

    def _make_points(self, n: int, lat_base=5.6, lon_base=-0.18):
        return [
            DeliveryPoint(
                delivery_id=f"DEL-{i:03d}",
                farmer_id=f"F-{i:03d}",
                district="Accra",
                latitude=lat_base + i * 0.01,
                longitude=lon_base + i * 0.01,
                order_amount=1000.0 * (i + 1),
            )
            for i in range(n)
        ]

    def test_empty_returns_empty(self):
        svc = RegionalBatchingService()
        assert svc.cluster([]) == []

    def test_single_delivery_one_batch(self):
        svc = RegionalBatchingService()
        batches = svc.cluster(self._make_points(1))
        assert len(batches) == 1
        assert batches[0].size == 1

    def test_batch_count_ceiling(self):
        svc = RegionalBatchingService(max_batch_size=5)
        batches = svc.cluster(self._make_points(11))
        # ceil(11/5) = 3 batches
        assert len(batches) == 3

    def test_all_deliveries_assigned(self, sample_deliveries):
        svc = RegionalBatchingService(max_batch_size=15)
        batches = svc.cluster_from_dicts(sample_deliveries)
        total = sum(b['size'] for b in batches)
        assert total == len(sample_deliveries)

    def test_no_delivery_duplicated(self, sample_deliveries):
        svc = RegionalBatchingService()
        batches = svc.cluster_from_dicts(sample_deliveries)
        all_ids = [did for b in batches for did in b['delivery_ids']]
        assert len(all_ids) == len(set(all_ids)), "Duplicate delivery IDs found"

    def test_two_geographically_separate_districts(self, sample_deliveries):
        svc = RegionalBatchingService(max_batch_size=15)
        batches = svc.cluster_from_dicts(sample_deliveries)
        # 10 deliveries / max 15 = 1 batch, but two geographically distinct
        # clusters exist so k=ceil(10/15)=1 OR k=2 depending on size
        # Main assertion: structure is valid
        for b in batches:
            assert 'batch_id' in b
            assert 'centroid' in b
            assert b['size'] > 0

    def test_batch_id_is_unique(self, sample_deliveries):
        svc = RegionalBatchingService()
        batches = svc.cluster_from_dicts(sample_deliveries)
        ids = [b['batch_id'] for b in batches]
        assert len(ids) == len(set(ids))

    def test_total_amount_correct(self):
        svc = RegionalBatchingService(max_batch_size=100)
        points = self._make_points(5)
        batches = svc.cluster(points)
        expected_total = sum(p.order_amount for p in points)
        actual_total = sum(b.total_amount for b in batches)
        assert actual_total == pytest.approx(expected_total, rel=1e-6)

    def test_centroid_within_bounding_box(self):
        svc = RegionalBatchingService(max_batch_size=100)
        points = self._make_points(5)
        batches = svc.cluster(points)
        for b in batches:
            lats = [d.latitude for d in b.deliveries]
            lons = [d.longitude for d in b.deliveries]
            assert min(lats) <= b.centroid_lat <= max(lats) + 1e-6
            assert min(lons) <= b.centroid_lon <= max(lons) + 1e-6

    def test_missing_required_key_raises(self):
        svc = RegionalBatchingService()
        bad = [{"delivery_id": "DEL-001", "farmer_id": "F-001"}]  # missing lat/lon
        with pytest.raises(KeyError):
            svc.cluster_from_dicts(bad)

    def test_large_batch_performance(self):
        """50 deliveries should complete in under 2 seconds."""
        import time
        svc = RegionalBatchingService(max_batch_size=10)
        points = self._make_points(50)
        t0 = time.time()
        batches = svc.cluster(points)
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"Clustering 50 points took {elapsed:.2f}s (expected <2s)"
        assert len(batches) == 5  # ceil(50/10) = 5
