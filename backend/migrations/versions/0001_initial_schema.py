"""Initial schema — all core tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-22
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── warehouses ─────────────────────────────────────────────────────
    op.create_table(
        'warehouses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('location', sa.String(200)),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('region', sa.String(100)),
        sa.Column('district', sa.String(100)),
        sa.Column('capacity', sa.Integer, default=0),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # ── inventory_items ────────────────────────────────────────────────
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False),
        sa.Column('sku', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('input_type', sa.String(50), nullable=False),
        sa.Column('quantity_available', sa.Float, default=0),
        sa.Column('quantity_reserved', sa.Float, default=0),
        sa.Column('unit', sa.String(20)),
        sa.Column('reorder_level', sa.Float, default=0),
        sa.Column('unit_price', sa.Float, default=0),
        sa.Column('batch_number', sa.String(100)),
        sa.Column('expiry_date', sa.Date),
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_inventory_items_warehouse_sku', 'inventory_items', ['warehouse_id', 'sku'], unique=True)

    # ── farmers ────────────────────────────────────────────────────────
    op.create_table(
        'farmers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('external_id', sa.String(100), unique=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('district', sa.String(100)),
        sa.Column('region', sa.String(100)),
        sa.Column('farm_size_acres', sa.Float),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_farmers_district', 'farmers', ['district'])

    # ── orders ─────────────────────────────────────────────────────────
    op.create_table(
        'orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_number', sa.String(100), unique=True, nullable=False),
        sa.Column('farmer_id', sa.String(36), sa.ForeignKey('farmers.id'), nullable=False),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('total_amount', sa.Float, default=0),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_orders_farmer_id', 'orders', ['farmer_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])

    # ── order_items ────────────────────────────────────────────────────
    op.create_table(
        'order_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('sku', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('input_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('unit', sa.String(20)),
        sa.Column('unit_price', sa.Float, nullable=False),
        sa.Column('total_price', sa.Float),
        sa.Column('is_verified', sa.Boolean, default=False),
    )

    # ── batches ────────────────────────────────────────────────────────
    op.create_table(
        'batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('batch_number', sa.String(100), unique=True, nullable=False),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False),
        sa.Column('district', sa.String(100)),
        sa.Column('region', sa.String(100)),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('centroid_lat', sa.Float),
        sa.Column('centroid_lon', sa.Float),
        sa.Column('total_orders', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('dispatched_at', sa.DateTime(timezone=True)),
    )

    # ── routes ─────────────────────────────────────────────────────────
    op.create_table(
        'routes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('route_number', sa.String(100), unique=True, nullable=False),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('batches.id'), nullable=False),
        sa.Column('status', sa.String(50), default='planned'),
        sa.Column('total_distance_km', sa.Float),
        sa.Column('estimated_duration_hours', sa.Float),
        sa.Column('optimized_sequence', sa.Text),   # JSON array of order IDs
        sa.Column('algorithm_used', sa.String(100)),
        sa.Column('distance_reduction_pct', sa.Float),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── field_agents ───────────────────────────────────────────────────
    op.create_table(
        'field_agents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('employee_id', sa.String(100), unique=True),
        sa.Column('region', sa.String(100)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── deliveries ─────────────────────────────────────────────────────
    op.create_table(
        'deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('delivery_number', sa.String(100), unique=True, nullable=False),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('route_id', sa.String(36), sa.ForeignKey('routes.id')),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('field_agents.id')),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('sequence_number', sa.Integer),
        sa.Column('scheduled_date', sa.DateTime(timezone=True)),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_deliveries_status', 'deliveries', ['status'])

    # ── proof_of_deliveries ────────────────────────────────────────────
    op.create_table(
        'proof_of_deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('delivery_id', sa.String(36), sa.ForeignKey('deliveries.id'), nullable=False, unique=True),
        sa.Column('farmer_name', sa.String(200)),
        sa.Column('farmer_phone', sa.String(20)),
        sa.Column('delivery_condition', sa.String(50)),
        sa.Column('location_latitude', sa.Float),
        sa.Column('location_longitude', sa.Float),
        sa.Column('location_accuracy_meters', sa.Float),
        sa.Column('signature_data', sa.Text),
        sa.Column('photos', sa.Text),           # JSON array of base64/URLs
        sa.Column('items_verified', sa.Text),   # JSON map sku→bool
        sa.Column('notes', sa.Text),
        sa.Column('sms_sent', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── eligibility_checks ─────────────────────────────────────────────
    op.create_table(
        'eligibility_checks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('farmer_id', sa.String(36), sa.ForeignKey('farmers.id'), nullable=False),
        sa.Column('is_eligible', sa.Boolean, nullable=False),
        sa.Column('credit_score', sa.Integer),
        sa.Column('risk_level', sa.String(20)),
        sa.Column('max_credit_limit', sa.Float),
        sa.Column('order_amount', sa.Float),
        sa.Column('reason', sa.Text),
        sa.Column('source', sa.String(100)),
        sa.Column('checked_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
    )

    # ── delivery_risk_assessments ──────────────────────────────────────
    op.create_table(
        'delivery_risk_assessments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('delivery_id', sa.String(36), sa.ForeignKey('deliveries.id'), nullable=False),
        sa.Column('expected_latitude', sa.Float),
        sa.Column('expected_longitude', sa.Float),
        sa.Column('actual_latitude', sa.Float),
        sa.Column('actual_longitude', sa.Float),
        sa.Column('deviation_meters', sa.Float),
        sa.Column('geofence_radius_meters', sa.Float, default=50),
        sa.Column('risk_score', sa.Integer, default=0),
        sa.Column('risk_level', sa.String(20)),
        sa.Column('anomaly_flags', sa.Text),    # JSON array
        sa.Column('requires_review', sa.Boolean, default=False),
        sa.Column('auto_approved', sa.Boolean, default=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True)),
    )

    # ── dispatch_records ───────────────────────────────────────────────
    op.create_table(
        'dispatch_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('pipeline_id', sa.String(100), unique=True),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('batches.id')),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id')),
        sa.Column('district', sa.String(100)),
        sa.Column('region', sa.String(100)),
        sa.Column('status', sa.String(50)),
        sa.Column('pipeline_stages', sa.Text),   # JSON
        sa.Column('ineligible_farmers', sa.Text), # JSON
        sa.Column('unavailable_items', sa.Text),  # JSON
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('dispatched_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('dispatch_records')
    op.drop_table('delivery_risk_assessments')
    op.drop_table('eligibility_checks')
    op.drop_table('proof_of_deliveries')
    op.drop_table('deliveries')
    op.drop_table('field_agents')
    op.drop_table('routes')
    op.drop_table('batches')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_index('ix_farmers_district', table_name='farmers')
    op.drop_table('farmers')
    op.drop_index('ix_inventory_items_warehouse_sku', table_name='inventory_items')
    op.drop_table('inventory_items')
    op.drop_table('warehouses')
