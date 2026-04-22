"""
Regional Batching Service — K-Means Clustering

Groups delivery requests into district-level batches to maximise
vehicle capacity and minimise cross-district travel.

Algorithm:
  1. Parse GPS coordinates from each delivery request.
  2. Run Lloyd's K-Means algorithm (pure stdlib, no sklearn dependency)
     with k = ceil(n / MAX_BATCH_SIZE) clusters.
  3. Assign every delivery to its nearest cluster centroid.
  4. Return one Batch object per cluster.

The TSP route optimiser in routing.py then operates within each batch.
"""

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple


# ── Constants ────────────────────────────────────────────────────────────────

MAX_BATCH_SIZE = 15      # maximum deliveries per district batch
KMEANS_MAX_ITER = 100    # Lloyd's algorithm convergence limit
KMEANS_SEED = 42         # reproducible centroid initialisation


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class DeliveryPoint:
    delivery_id: str
    farmer_id: str
    district: str
    latitude: float
    longitude: float
    order_amount: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegionalBatch:
    batch_id: str
    cluster_id: int
    district: str
    centroid_lat: float
    centroid_lon: float
    deliveries: List[DeliveryPoint]
    total_amount: float
    created_at: str

    @property
    def size(self) -> int:
        return len(self.deliveries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "cluster_id": self.cluster_id,
            "district": self.district,
            "centroid": {"latitude": self.centroid_lat, "longitude": self.centroid_lon},
            "size": self.size,
            "total_amount": self.total_amount,
            "delivery_ids": [d.delivery_id for d in self.deliveries],
            "farmer_ids": [d.farmer_id for d in self.deliveries],
            "created_at": self.created_at,
        }


# ── Haversine helper (kilometres) ────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── K-Means Core (pure stdlib) ───────────────────────────────────────────────

def _kmeans(
    points: List[Tuple[float, float]],
    k: int,
    max_iter: int = KMEANS_MAX_ITER,
    seed: int = KMEANS_SEED,
) -> List[int]:
    """
    Lloyd's K-Means algorithm on (lat, lon) pairs using Haversine distance.

    Returns a list of cluster assignments (0-indexed) the same length as `points`.
    """
    if k >= len(points):
        return list(range(len(points)))

    rng = random.Random(seed)
    # K-Means++ initialisation for better convergence
    centroids = [points[rng.randint(0, len(points) - 1)]]
    for _ in range(k - 1):
        dists = [
            min(_haversine_km(p[0], p[1], c[0], c[1]) for c in centroids)
            for p in points
        ]
        total = sum(dists)
        r = rng.random() * total
        cumulative = 0.0
        chosen = points[-1]
        for p, d in zip(points, dists):
            cumulative += d
            if cumulative >= r:
                chosen = p
                break
        centroids.append(chosen)

    assignments = [0] * len(points)
    for _ in range(max_iter):
        # Assignment step
        new_assignments = [
            min(range(k), key=lambda ci: _haversine_km(p[0], p[1], centroids[ci][0], centroids[ci][1]))
            for p in points
        ]
        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Update step — recompute centroids as mean lat/lon per cluster
        sums = [(0.0, 0.0, 0) for _ in range(k)]
        for idx, ci in enumerate(assignments):
            lat_sum, lon_sum, count = sums[ci]
            sums[ci] = (lat_sum + points[idx][0], lon_sum + points[idx][1], count + 1)

        for ci in range(k):
            lat_sum, lon_sum, count = sums[ci]
            if count > 0:
                centroids[ci] = (lat_sum / count, lon_sum / count)

    return assignments


# ── Public API ───────────────────────────────────────────────────────────────

class RegionalBatchingService:
    """
    Groups delivery requests into regional batches using K-Means clustering.

    Usage:
        service = RegionalBatchingService()
        batches = service.cluster(delivery_points)
    """

    def __init__(self, max_batch_size: int = MAX_BATCH_SIZE):
        self.max_batch_size = max_batch_size

    def cluster(self, deliveries: List[DeliveryPoint]) -> List[RegionalBatch]:
        """
        Cluster deliveries into regional batches.

        Args:
            deliveries: List of DeliveryPoint objects with GPS coordinates.

        Returns:
            List of RegionalBatch objects, one per cluster.
        """
        if not deliveries:
            return []

        n = len(deliveries)
        k = max(1, math.ceil(n / self.max_batch_size))

        coords = [(d.latitude, d.longitude) for d in deliveries]
        assignments = _kmeans(coords, k)

        # Group deliveries by cluster
        clusters: Dict[int, List[DeliveryPoint]] = {i: [] for i in range(k)}
        for delivery, cluster_id in zip(deliveries, assignments):
            clusters[cluster_id].append(delivery)

        now = datetime.now(timezone.utc).isoformat()
        batches: List[RegionalBatch] = []

        for cluster_id, members in clusters.items():
            if not members:
                continue

            # Compute centroid
            c_lat = sum(d.latitude for d in members) / len(members)
            c_lon = sum(d.longitude for d in members) / len(members)

            # Derive district label from plurality of member districts
            district_counts: Dict[str, int] = {}
            for d in members:
                district_counts[d.district] = district_counts.get(d.district, 0) + 1
            district = max(district_counts, key=district_counts.get)

            total_amount = sum(d.order_amount for d in members)

            batches.append(RegionalBatch(
                batch_id=f"BATCH-{uuid.uuid4().hex[:8].upper()}",
                cluster_id=cluster_id,
                district=district,
                centroid_lat=round(c_lat, 6),
                centroid_lon=round(c_lon, 6),
                deliveries=members,
                total_amount=round(total_amount, 2),
                created_at=now,
            ))

        # Sort batches by cluster_id for deterministic output
        batches.sort(key=lambda b: b.cluster_id)
        return batches

    def cluster_from_dicts(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convenience wrapper: accepts raw dicts, returns serialisable dicts.

        Expected dict keys: delivery_id, farmer_id, district, latitude, longitude,
                            order_amount (optional), metadata (optional).
        """
        points = [
            DeliveryPoint(
                delivery_id=r['delivery_id'],
                farmer_id=r['farmer_id'],
                district=r.get('district', 'Unknown'),
                latitude=float(r['latitude']),
                longitude=float(r['longitude']),
                order_amount=float(r.get('order_amount', 0)),
                metadata=r.get('metadata', {}),
            )
            for r in raw
        ]
        batches = self.cluster(points)
        return [b.to_dict() for b in batches]
