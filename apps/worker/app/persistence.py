from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import asyncpg


async def persist_vector_features(project_id: str, result: dict[str, Any], storage_root: str) -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return 0
    layer_id = str(result["layer_id"])
    geometry_type = str(result["geometry_type"])
    collection_path = Path(storage_root) / project_id / "layers" / f"{layer_id}.geojson"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if any(feature.get("geometry", {}).get("type") != geometry_type for feature in features):
        raise ValueError(f"Layer {layer_id} contains a geometry different from {geometry_type}")
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS vector_features (
                id BIGSERIAL PRIMARY KEY,
                project_id TEXT NOT NULL,
                layer_id TEXT NOT NULL,
                geometry_type TEXT NOT NULL,
                geometry geometry(Geometry, 23700) NOT NULL,
                properties JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (project_id, layer_id, geometry)
            )
        """)
        await connection.execute(
            "DELETE FROM vector_features WHERE project_id = $1 AND layer_id = $2",
            project_id,
            layer_id,
        )
        await connection.executemany(
            """INSERT INTO vector_features (project_id, layer_id, geometry_type, geometry, properties)
               VALUES ($1, $2, $3, ST_SetSRID(ST_GeomFromGeoJSON($4), 23700), $5::jsonb)
               ON CONFLICT (project_id, layer_id, geometry) DO UPDATE SET geometry_type = EXCLUDED.geometry_type, properties = EXCLUDED.properties""",
            [
                (
                    project_id,
                    layer_id,
                    geometry_type,
                    json.dumps(feature["geometry"]),
                    json.dumps(feature.get("properties", {})),
                )
                for feature in features
            ],
        )
    finally:
        await connection.close()
    return len(features)