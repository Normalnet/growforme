"""
Regional Batching Algorithm & Intelligent Routing Engine
Core service for optimizing order batching and delivery route planning.
"""

from typing import List, Dict, Tuple, Optional
import math
from datetime import datetime
from app.models import Order, Batch, Route, Farmer, Warehouse, OrderItem, db
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)

class RoutingEngine:
    """
    Intelligent routing engine for multi-stop farm deliveries.
    Uses TSP (Traveling Salesman Problem) approximation for route optimization.
    """
    
    # Earth radius in kilometers
    EARTH_RADIUS_KM = 6371
    
    def __init__(self, config=None):
        self.config = config or {}
        self.max_stops_per_route = self.config.get('MAX_DELIVERY_STOPS_PER_ROUTE', 30)
        self.optimal_distance = self.config.get('OPTIMAL_ROUTE_DISTANCE_KM', 100)
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great circle distance between two points on Earth
        Returns distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        
        return RoutingEngine.EARTH_RADIUS_KM * c
    
    def nearest_neighbor_tsp(self, warehouse: Warehouse, farmers: List[Farmer]) -> Tuple[List[Farmer], float]:
        """
        Nearest Neighbor TSP approximation algorithm for route optimization.
        Starts from warehouse and visits farmers in nearest-first order.
        
        Args:
            warehouse: Starting warehouse location
            farmers: List of farmers to visit
        
        Returns:
            Tuple of (optimized_farmer_sequence, total_distance_km)
        """
        if not farmers:
            return [], 0.0
        
        unvisited = set(farmers)
        current_location = warehouse
        sequence = []
        total_distance = 0.0
        
        while unvisited:
            # Find nearest unvisited farmer
            nearest_farmer = None
            nearest_distance = float('inf')
            
            for farmer in unvisited:
                distance = self.haversine_distance(
                    current_location.latitude,
                    current_location.longitude,
                    farmer.latitude,
                    farmer.longitude
                )
                
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_farmer = farmer
            
            # Visit the nearest farmer
            sequence.append(nearest_farmer)
            total_distance += nearest_distance
            current_location = nearest_farmer
            unvisited.remove(nearest_farmer)
        
        # Add return distance to warehouse
        return_distance = self.haversine_distance(
            current_location.latitude,
            current_location.longitude,
            warehouse.latitude,
            warehouse.longitude
        )
        total_distance += return_distance
        
        return sequence, total_distance
    
    def two_opt_optimization(self, sequence: List[Farmer], warehouse: Warehouse, 
                           max_iterations: int = 100) -> Tuple[List[Farmer], float]:
        """
        2-OPT local search optimization for TSP.
        Iteratively improves the route by reversing segments.
        """
        best_sequence = sequence[:]
        best_distance = self._calculate_total_distance(best_sequence, warehouse)
        improved = True
        iterations = 0
        
        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            
            for i in range(len(best_sequence) - 1):
                for j in range(i + 2, len(best_sequence)):
                    # Create new sequence by reversing segment [i+1:j+1]
                    new_sequence = best_sequence[:i+1] + best_sequence[i+1:j+1][::-1] + best_sequence[j+1:]
                    new_distance = self._calculate_total_distance(new_sequence, warehouse)
                    
                    if new_distance < best_distance:
                        best_sequence = new_sequence
                        best_distance = new_distance
                        improved = True
                        break
                
                if improved:
                    break
        
        return best_sequence, best_distance
    
    def _calculate_total_distance(self, sequence: List[Farmer], warehouse: Warehouse) -> float:
        """Calculate total distance for a given route sequence."""
        total_distance = 0.0
        current = warehouse
        
        for farmer in sequence:
            total_distance += self.haversine_distance(
                current.latitude, current.longitude,
                farmer.latitude, farmer.longitude
            )
            current = farmer
        
        # Return to warehouse
        total_distance += self.haversine_distance(
            current.latitude, current.longitude,
            warehouse.latitude, warehouse.longitude
        )
        
        return total_distance
    
    def estimate_delivery_time(self, distance_km: float, num_stops: int, 
                              avg_speed_kmh: float = 40, 
                              time_per_stop_minutes: float = 15) -> float:
        """
        Estimate delivery time in hours.
        
        Args:
            distance_km: Total route distance
            num_stops: Number of delivery stops
            avg_speed_kmh: Average vehicle speed (default 40 km/h for rural areas)
            time_per_stop_minutes: Average time per delivery stop
        
        Returns:
            Estimated delivery time in hours
        """
        travel_time_hours = distance_km / avg_speed_kmh
        stop_time_hours = (num_stops * time_per_stop_minutes) / 60
        return travel_time_hours + stop_time_hours


class BatchingEngine:
    """
    Regional Batching Algorithm Engine
    Groups orders by district, warehouse, and optimizes for delivery efficiency.
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.max_orders_per_batch = self.config.get('MAX_ORDERS_PER_BATCH', 50)
        self.routing_engine = RoutingEngine(config)
    
    def create_batches_for_district(self, warehouse_id: str, district: str, 
                                    region: str) -> List[Dict]:
        """
        Create optimized batches for pending orders in a specific district.
        
        Args:
            warehouse_id: Source warehouse ID
            district: Target district
            region: Target region
        
        Returns:
            List of batch configurations
        """
        # Fetch pending orders for this district
        pending_orders = Order.query.filter(
            and_(
                Order.status == 'pending',
                Order.warehouse_id == warehouse_id,
                Farmer.district == district
            )
        ).join(Farmer).all()
        
        if not pending_orders:
            logger.info(f"No pending orders for {district} in {region}")
            return []
        
        # Group orders by farmer location clusters
        batches = []
        orders_processed = 0
        
        while orders_processed < len(pending_orders):
            batch_orders = pending_orders[orders_processed:orders_processed + self.max_orders_per_batch]
            
            # Calculate batch metrics
            total_weight = sum(
                sum(item.quantity for item in order.order_items)
                for order in batch_orders
            )
            
            total_value = sum(order.total_amount for order in batch_orders)
            
            batch_config = {
                'warehouse_id': warehouse_id,
                'district': district,
                'region': region,
                'orders': [order.id for order in batch_orders],
                'order_count': len(batch_orders),
                'total_weight_kg': total_weight,
                'total_value': total_value
            }
            
            batches.append(batch_config)
            orders_processed += len(batch_orders)
        
        logger.info(f"Created {len(batches)} batches for {district}")
        return batches
    
    def generate_routes_for_batch(self, batch_id: str) -> List[Dict]:
        """
        Generate optimized delivery routes for a batch.
        
        Args:
            batch_id: Batch ID
        
        Returns:
            List of route configurations
        """
        batch = Batch.query.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        warehouse = Warehouse.query.get(batch.warehouse_id)
        if not warehouse:
            raise ValueError(f"Warehouse {batch.warehouse_id} not found")
        
        # Get all farmers from orders in the batch
        farmer_ids = db.session.query(Farmer.id).join(Order).filter(
            Order.batch_id == batch_id
        ).distinct().all()
        
        farmers = Farmer.query.filter(Farmer.id.in_([f[0] for f in farmer_ids])).all()
        
        # Optimize route using nearest neighbor + 2-opt
        optimized_sequence, total_distance = self.routing_engine.nearest_neighbor_tsp(
            warehouse, farmers
        )
        
        # Apply 2-opt optimization
        optimized_sequence, optimized_distance = self.routing_engine.two_opt_optimization(
            optimized_sequence, warehouse
        )
        
        # Split into sub-routes if too many stops
        routes = self._split_into_subroutes(
            warehouse, optimized_sequence, optimized_distance, batch_id
        )
        
        return routes
    
    def _split_into_subroutes(self, warehouse: Warehouse, sequence: List[Farmer], 
                             total_distance: float, batch_id: str) -> List[Dict]:
        """
        Split a large optimized route into multiple sub-routes if needed.
        """
        max_stops = self.routing_engine.max_stops_per_route
        routes = []
        
        if len(sequence) <= max_stops:
            # Single route is sufficient
            est_delivery_time = self.routing_engine.estimate_delivery_time(
                total_distance, len(sequence)
            )
            
            route_config = {
                'batch_id': batch_id,
                'district': warehouse.district,
                'stops': [f.id for f in sequence],
                'total_stops': len(sequence),
                'total_distance_km': total_distance,
                'estimated_delivery_time_hours': est_delivery_time,
                'optimized_sequence': [f.id for f in sequence]
            }
            routes.append(route_config)
        else:
            # Split into multiple sub-routes
            for i in range(0, len(sequence), max_stops):
                sub_sequence = sequence[i:i+max_stops]
                
                # Calculate distance for sub-route
                sub_distance = self.routing_engine._calculate_total_distance(
                    sub_sequence, warehouse
                )
                
                est_delivery_time = self.routing_engine.estimate_delivery_time(
                    sub_distance, len(sub_sequence)
                )
                
                route_config = {
                    'batch_id': batch_id,
                    'district': warehouse.district,
                    'stops': [f.id for f in sub_sequence],
                    'total_stops': len(sub_sequence),
                    'total_distance_km': sub_distance,
                    'estimated_delivery_time_hours': est_delivery_time,
                    'optimized_sequence': [f.id for f in sub_sequence]
                }
                routes.append(route_config)
        
        logger.info(f"Generated {len(routes)} routes for batch {batch_id}")
        return routes
