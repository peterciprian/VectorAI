# System Architecture: VectoryAI

## 1. High-Level Architecture Overview

VectoryAI is an enterprise-grade, asynchronous, modular monorepo with independently runnable services for GIS and AI processing in the urban planning sector. Large municipal regulatory plans (Szabályozási Tervek - SZT) and municipal master plans (Településszerkezeti Tervek - TSZT) are typically high-resolution raster sheets (A0–A00+ at 300–600 DPI, frequently 15,000 × 10,000 to 40,000 × 30,000 pixels).

Because raster processing, deep learning inference, and topological planar cleaning are compute- and memory-intensive, all compute-heavy tasks run decoupled in asynchronous worker queues. The frontend provides a responsive, desktop-class web GIS experience based on **Next.js 14+** and **OpenLayers 9+**.

```mermaid
graph TB
    subgraph Client ["Frontend Client (Next.js 14+ / React 18+ / OpenLayers 9+)"]
        UI[Workflow Wizard & Dashboard]
        OL[OpenLayers 9+ Canvas Map Viewer]
        GCP_Tool[Dual-Pane GCP Georeferencer]
        Legend_UI[Interactive Legend Inspector & Color Calibrator]
        Vector_Editor[In-Browser Feature Editor: Draw / Modify / Snap]
        SSE_Client[EventSource SSE Client]
    end

    subgraph Gateway ["API Gateway & Orchestration (FastAPI)"]
        API[FastAPI Asynchronous Gateway]
        Auth[Auth & Session Guard]
        Router[REST Endpoint Controllers]
        SSE_Broadcaster[SSE Progress Event Hub]
    end

    subgraph Queue ["Message Broker & Job Queue"]
        Redis[(Redis 7.2: Celery Broker & Pub/Sub Cache)]
        CeleryWorkers[Celery Worker Cluster: CPU / GPU Nodes]
    end

    subgraph ProcessingCore ["AI & Spatial Processing Core (Python 3.11+)"]
        IngestMod[Module 1: Ingestion & DZI/Tile Pyramid Engine]
        GeoRefMod[Module 2: Georeferencing & GDAL Warper]
        LegendMod[Module 3: AI Legend Parser & PaddleOCR]
        SegMod[Module 4: Segmentation & Text Inpainter]
        VectMod[Module 5: Polygon / Line / Point Vectorizer]
        TopoMod[Module 6: Topology Cleaner & Planar Partitioner]
        ExportMod[Module 7: ESRI Shapefile & GeoJSON Packager]
    end

    subgraph Storage ["Persistent Storage Layer"]
        ObjStore[(File Storage / MinIO / Local FS)]
        DB[(PostgreSQL 16 + PostGIS 3.4 Spatial Database)]
    end

    UI --> API
    OL --> API
    GCP_Tool --> API
    Legend_UI --> API
    Vector_Editor --> API
    API --> DB
    API --> Redis
    Redis --> CeleryWorkers
    CeleryWorkers --> IngestMod
    CeleryWorkers --> GeoRefMod
    CeleryWorkers --> LegendMod
    CeleryWorkers --> SegMod
    CeleryWorkers --> VectMod
    CeleryWorkers --> TopoMod
    CeleryWorkers --> ExportMod
    CeleryWorkers --> ObjStore
    CeleryWorkers --> DB
    CeleryWorkers -.->|PubSub Status Events| Redis
    Redis -.->|Event Stream| SSE_Broadcaster
    SSE_Broadcaster --> SSE_Client
```

  Processing jobs are persisted in `processing_jobs`. Workers publish lifecycle events to the project Redis channel `vectoryai:project:{project_id}:jobs`; the API exposes the channel through `GET /api/v1/projects/{id}/events` and individual lifecycle state through `GET /api/v1/jobs/{job_id}`.

---

## 2. Technology Stack & Component Specifications

### 2.1. Frontend Web Client
- **Framework:** Next.js 14+ (App Router, Server & Client Components, React 18/19, TypeScript 5.4+).
- **GIS Engine:** **OpenLayers 9+** (`ol`):
  - Native Coordinate Systems via `proj4js` (EPSG:23700 - Hungarian EOV, EPSG:3857 - Web Mercator, EPSG:4326 - WGS84).
  - Tiled image streaming using `ol/layer/WebGLTile` and `ol/source/GeoTIFF` (Cloud-Optimized GeoTIFF - COG) or DeepZoom `ol/source/Zoomify`.
  - Vector layers: `ol/layer/Vector`, `ol/source/Vector` with geometry rendering optimizations.
  - Interactive tools: `ol/interaction/Draw`, `ol/interaction/Modify`, `ol/interaction/Snap`, `ol/interaction/Select`, `ol/interaction/Translate`.
- **UI & Design System:** Tailwind CSS v3.4+, Radix UI / shadcn/ui components, Lucide React icons.
- **State Management & Network:** TanStack Query v5 (React Query), Zustand v4 (client state machine), Native `EventSource` for SSE streaming.

### 2.2. API Gateway & Microservices
- **Framework:** **FastAPI** (Python 3.11+ / Uvicorn / Gunicorn).
- **Serialization & Validation:** Pydantic v2 with custom geospatial validators (`geojson-pydantic`).
- **ORM & Database Client:** SQLAlchemy 2.0+ (asyncpg) with GeoAlchemy2 for PostGIS interactions.
- **Job Orchestration:** Celery 5.3+ backed by Redis 7.2.

### 2.3. Computer Vision, Machine Learning & GIS Processing Engines
- **Spatial & Raster Data IO:** `GDAL/OGR 3.8+`, `rasterio 1.3+`, `Fiona 1.9+`, `GeoPandas 0.14+`, `pyproj 3.6+`.
- **Geometry Operations:** `Shapely 2.0+` (C-optimized GEOS wrapper), `NetworkX 3.2+` (graph skeletonization and line chaining), `scikit-image 0.22+`, `OpenCV (cv2) 4.9+`.
- **AI & Deep Learning Models:**
  - **Text & OCR Engine:** `PaddleOCR 2.7+` (multilingual model with Hungarian language fine-tuning) / `Tesseract 5.3+`.
  - **Segmentation Engine:** Meta Segment Anything Model 2 (SAM 2) / YOLOv8-seg (`ultralytics`) / Adaptive HSV-Lab Color Space Classifier.
  - **Point & Symbol Detector:** YOLOv8n / YOLOv10 for municipal map symbols.
  - **Execution Runtime:** PyTorch 2.2+ (CUDA 12.1 acceleration on GPU nodes, automatic fallback to multi-threaded CPU with OpenVINO / ONNX Runtime).

### 2.4. Storage & Infrastructure
- **Database:** PostgreSQL 16 with PostGIS 3.4 spatial extension.
- **Artifact Storage:** MinIO / AWS S3 compatible object storage or local filesystem with standardized directory taxonomy.
- **Containerization:** Multi-container Docker Compose and Kubernetes Helm chart definitions.

---

## 3. Detailed Module Specifications & Algorithms

```mermaid
classDiagram
    class IngestionEngine {
        +render_pdf_to_raster(pdf_bytes, dpi) Image
        +generate_image_pyramid(image_path) DziPyramid
        +tile_image(image_path, tile_size, overlap) List~Tile~
    }

    class GeoreferencingEngine {
        +calculate_affine(gcps) TransformMatrix
        +calculate_polynomial_2nd(gcps) TransformMatrix
        +calculate_tps(gcps) TPSSpline
        +compute_residuals_and_rmse(gcps, transform) RMSEMetrics
        +warp_to_eov_cog(input_raster, gcps, method, output_path) GeoTIFF
    }

    class LegendParsingEngine {
        +detect_legend_bbox(image) BoundingBox
        +segment_legend_items(legend_crop) List~LegendItemCrop~
        +run_hungarian_ocr(item_crop) TextResult
        +sample_visual_signature(item_crop) VisualSignature
        +infer_geometry_type(text, swatch) GeometryType
    }

    class SegmentationEngine {
        +generate_text_mask(image, ocr_boxes) BinaryMask
        +inpaint_text_regions(image, text_mask) CleanImage
        +color_segment_hsv_lab(clean_image, signature, tolerance) BinaryMask
        +ai_segment_sam2(clean_image, prompt_points) BinaryMask
    }

    class VectorizationEngine {
        +polygonize_mask(binary_mask, min_area_pixels) GeoDataFrame
        +skeletonize_lines(binary_mask) LineGraph
        +graph_to_linestrings(line_graph, max_gap) GeoDataFrame
        +detect_point_symbols(image, templates) GeoDataFrame
    }

    class TopologyCleaner {
        +snap_vertices(gdf, tolerance_meters) GeoDataFrame
        +remove_slivers(gdf, min_area_m2) GeoDataFrame
        +resolve_overlaps_planar(gdf) GeoDataFrame
        +bridge_line_gaps(gdf, bridge_distance) GeoDataFrame
    }

    class ShapefileExporter {
        +validate_single_geometry(gdf, expected_type) Boolean
        +sanitize_attribute_names(gdf) GeoDataFrame
        +write_shapefile_set(gdf, layer_name, out_dir) ShapefileFiles
        +generate_eov_prj(out_path) PrjFile
        +bundle_zip(project_id, file_list) ZipPath
    }

    IngestionEngine --> GeoreferencingEngine
    GeoreferencingEngine --> LegendParsingEngine
    LegendParsingEngine --> SegmentationEngine
    SegmentationEngine --> VectorizationEngine
    VectorizationEngine --> TopologyCleaner
    TopologyCleaner --> ShapefileExporter
```

---

### 3.1. Module 1: Ingestion & Tile Pyramid Engine (`apps/worker/app/ingestion.py`)
Large format maps (e.g., A0 @ 300 DPI = $14,030 \times 9,920$ pixels $\approx 417$ MB raw RGB) cannot be sent directly to the browser or processed in a single GPU pass without Out-Of-Memory (OOM) errors.

```mermaid
flowchart TD
    A[Upload .pdf / .jpg / .png / .tif] --> B{Is PDF?}
    B -- Yes --> C[PyMuPDF / pdf2image at 300-600 DPI]
    B -- No --> D[OpenCV / PIL Loader]
    C --> E[Raw High-Res Master Raster]
    D --> E
    E --> F[Generate DeepZoom / Zoomify Image Pyramid]
    E --> G[Generate 512x512 Tiled Slices with 64px Overlap]
    F --> H[Fast OpenLayers Browser Viewport]
    G --> I[Worker AI Inference Pipeline]
```

- **PDF Rasterization:** Uses `PyMuPDF` (`fitz`) and `pdftoppm` rendering engine with anti-aliasing and subpixel rendering.
- **Tiling & Pyramid Generation:** Generates DeepZoom (`.dzi`) / Zoomify pyramid tiles (`libvips`) for instant, lag-free pan/zoom in OpenLayers.
- **Processing Slices:** Generates $512 \times 512$ pixel sliding window tiles with a 64 px overlap. The overlap eliminates boundary artifacts during subsequent edge detection and polygon tracing.

---

### 3.2. Module 2: Georeferencing & Spatial Calibration (`apps.georef`)
Transforms image space $(u, v)$ (pixel coordinates from top-left) into Hungarian Uniform National Projection (**EOV - EPSG:23700**, coordinates $Y, X$ in meters).

The georeferencing workspace always provides a visual reference for placing GCPs. The user may upload an optional georeferenced reference layer, such as an EOV GeoTIFF/COG, GeoJSON, or compatible GIS layer. When no reference layer is uploaded, the frontend loads an OpenStreetMap layer as the default visual reference. An uploaded reference layer takes precedence over OpenStreetMap. The reference layer assists point matching; every GCP coordinate must still be entered or explicitly confirmed by the user before it is submitted for transformation.

```mermaid
flowchart LR
    A[Image Coordinates: u, v] --> B[GCP Pair Matcher]
    R[Uploaded EOV Reference Layer] --> B
    O[Default OpenStreetMap Reference] --> B
    C[Confirmed EOV Coordinates: X, Y] --> B
    B --> D{Transform Method}
    D -- 3-5 GCPs --> E[1st Order Affine Transform]
    D -- 6-9 GCPs --> F[2nd Order Polynomial Transform]
    D -- 10+ GCPs --> G[Thin Plate Spline - TPS]
    E --> H[Compute Residuals & Global RMSE]
    F --> H
    G --> H
    H --> I[GDAL Warp: Generate COG GeoTIFF in EPSG:23700]
```

#### Mathematical Formulations:
1. **1st Order Affine Transformation ($N \ge 3$ GCPs):**
   $$\begin{bmatrix} Y_{eov} \\ X_{eov} \end{bmatrix} = \begin{bmatrix} a_0 \\ b_0 \end{bmatrix} + \begin{bmatrix} a_1 & a_2 \\ b_1 & b_2 \end{bmatrix} \begin{bmatrix} u \\ v \end{bmatrix}$$
2. **Residual Error & RMSE:**
   $$r_i = \sqrt{(Y_i^{actual} - Y_i^{calc})^2 + (X_i^{actual} - X_i^{calc})^2}$$
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} r_i^2}$$
- **Warping Engine:** Executes `gdal.Warp` using `-r bilinear` or `-r lanczos` resampling and creates Cloud Optimized GeoTIFFs (COG) with internal overviews (`COMPRESS=DEFLATE`, `TILED=YES`).
- **Implemented transform selection:** `auto` recommends affine for 3-5 GCPs, second-order polynomial for 6-9 GCPs, and TPS for 10 or more GCPs. Confirmed GCPs are persisted in the PostGIS `gcps` table before the asynchronous warp is queued. The status response includes per-point residual vectors, RMSE, warnings, and the generated COG URL.

---

### 3.3. Module 3: AI Legend Parser & Classifier (`apps.legend`)

```mermaid
flowchart TD
    A[Georeferenced Raster Map] --> B[Detect Legend Box: YOLOv8 Layout / Contour Heuristics]
    B --> C[Crop Legend Area]
    C --> D[Morphological Row & Item Segmentation]
    D --> E[PaddleOCR Hungarian Text Recognition]
    D --> F[Color Swatch & Pattern Sampler: HSV/Lab + Stroke Width]
    E --> G[Rule-Based & NLP Geometry Inference]
    F --> G
    G --> H[Legend Class Registry JSON]
```

#### Geometry Type Inference Rules:
- **`Polygon`:** Triggered by text keywords (*"övezet"*, *"lakóterület"*, *"gazdasági"*, *"zöldterület"*, *"beépítésre szánt"*, *"vízfelület"*) OR if the legend swatch is a colored rectangle/box.
- **`LineString`:** Triggered by keywords (*"vonal"*, *"szabályozási vonal"*, *"építési vonal"*, *"védőtávolság"*, *"tengely"*, *"határ"*) OR if the swatch is an elongated line/dashed sample.
- **`Point`:** Triggered by keywords (*"fa"*, *"műemlék"*, *"kút"*, *"magassági pont"*, *"műtárgy"*, *"jel"*) OR if the swatch is a localized icon.

---

### 3.4. Module 4: Preprocessing & Text Inpainting (`apps.segmentation.inpaint`)
A major challenge in regulatory plans is that zoning codes (e.g., "Lk-1", "SZ", "6.0", "Vt") and street names are printed on top of colored polygons, creating unwanted holes ("doughnuts") during standard polygonization.

```mermaid
flowchart TD
    A[Original Master Raster] --> B[PaddleOCR / Text Bounding Box Extractor]
    B --> C[Generate Binary Text Mask with 3px Dilation]
    C --> D[OpenCV Fast Marching Inpainting cv2.INPAINT_TELEA]
    D --> E[Clean, Continuous Color Surface Image]
```

1. **Text Mask Generation:** Detect all text instances on the map sheet; dilate the detected bounding boxes by 3 pixels to cover font antialiasing.
2. **Inpainting (`cv2.inpaint`):** Use the Fast Marching Method (`INPAINT_TELEA`) with radius $r=3$ to reconstruct the original zone background color seamlessly underneath the text.

---

### 3.5. Module 5: Multi-Layer Vectorization Engine (`apps.vectorizer`)

The initial implemented vectorizer slice is exposed by `POST /api/v1/projects/{id}/vectorize` and asynchronously runs a reviewed Polygon legend class through OCR text-box masking, confidence filtering, legend/annotation/border exclusion zones, geometry-aware Polygon-only OpenCV Telea inpainting, Lab-distance color masking, morphological cleanup, raster polygonization, validity repair, and simplification. It writes a strict Polygon GeoJSON layer under the project storage and serves it through `GET /api/v1/projects/{id}/layers/{layer_id}/geojson`. Polygon results also report a binary color-mask IoU diagnostic comparing masks before and after inpainting.

The LineString slice uses the same reviewed legend contract, Lab-distance masking, morphological closing, skeletonization, graph tracing, simplification, and strict LineString GeoJSON output through the same asynchronous vectorize endpoint. The Point slice uses Lab connected components and an optional project-relative OpenCV template fallback for symbols whose color is not sufficiently isolated; generated Point features are written to GeoJSON and persisted in PostGIS with EPSG:23700 geometry and symbol metadata. The API exposes a generated-layer catalog, which the OpenLayers viewer discovers and renders automatically.

```mermaid
flowchart TD
    A[Clean Raster Image] --> B{Geometry Target}
    
    subgraph PolygonPipeline ["Polygon Extraction"]
        B -- Polygon Class --> P1[Color Filtering in HSV & CIELAB Space]
        P1 --> P2[Binary Morphological Opening & Closing]
        P2 --> P3[cv2.findContours & rasterio.features.shapes]
        P3 --> P4[Pixel-to-EOV Affine Coordinate Transform]
        P4 --> P5[Shapely Polygon Construction & Validation]
        P5 --> P6[Douglas-Peucker Simplification: epsilon = 0.2m]
    end

    subgraph LinePipeline ["LineString Extraction"]
        B -- LineString Class --> L1[Color & Edge Masking]
        L1 --> L2[Zhang-Suen Skeletonization / Medial Axis Thinning]
        L2 --> L3[Pixel Graph Construction: NetworkX]
        L3 --> L4[Prune Spur Branches & Detect Junction Nodes]
        L4 --> L5[Trace Longest Continuous Line Paths]
        L5 --> L6[Line Smoothing & Gap Bridging: d < 2.0m]
    end

    subgraph PointPipeline ["Point Extraction"]
      B -- Point Class --> T1[Lab Color Mask & Connected Components]
      T1 --> T2[Extract Component Centroids]
        T2 --> T3[Pixel-to-EOV Coordinate Transform]
      T3 --> T4[Shapely Point Features with Symbol Metadata]
    end

    P6 --> Out[Layer GeoDataFrame]
    L6 --> Out
    T4 --> Out
```

---

### 3.6. Module 6: Topology Validation & Cleaning (`apps.topology`)
To ensure GIS compliance, the raw vector geometries must be cleaned before export:

```mermaid
flowchart LR
    A[Raw GeoDataFrame] --> B[Snapping Engine: snap vertices within 0.2m tolerance]
    B --> C[Sliver Removal: absorb polygons < 1.0 m² into largest neighbor]
    C --> D[Planar Partitioning: resolve overlapping polygons of same rank]
    D --> E[Unclosed Line Fixing: connect end-nodes within tolerance]
    E --> F[Topologically Clean GeoDataFrame]
```

1. **Vertex Snapping:** `shapely.ops.snap(geom1, geom2, tolerance=0.2)` snaps vertices within $20\text{ cm}$ in EOV space to close micro-gaps.
2. **Sliver Elimination:** Identifies polygons with $\text{Area} < 1.0\text{ m}^2$ or thinness ratio $\frac{4\pi \cdot \text{Area}}{\text{Perimeter}^2} < 0.05$, merging them into the adjacent polygon sharing the longest boundary.
3. **Planar Partitioning:** Subtracts already-occupied polygon area in deterministic feature order and splits multipart results, ensuring same-layer polygons have zero overlaps.
4. **Line Gap Bridging:** Detects LineString endpoints within 0.2 m, inserts a connecting segment, and merges the result into a continuous line.

---

### 3.7. Module 7: GIS Exporter & Shapefile Packager (`apps.exporter`)
ESRI Shapefiles enforce strict legacy constraints that this module guarantees:

```mermaid
flowchart TD
    A[Clean Vector Layers] --> B[Filter by Legend Class & Strict Geometry Type]
    B --> C[Sanitize DBF Attributes: Names <= 10 ASCII chars, UTF-8/CP1250]
    C --> D[Write ESRI Shapefile Component Files: .shp, .shx, .dbf, .cpg, .prj]
    D --> E[Generate EOV EPSG:23700 WKT .prj File]
    E --> F[Generate metadata.json & README.txt]
    F --> G[Compress into export_project_xxx.zip]
```

- **Single Geometry Guarantee:** A layer containing mixed geometries is strictly rejected or partitioned into separate `.shp` files (e.g., `_POLYGON.shp`, `_LINE.shp`).
- **EOV PRJ Content:**
```
PROJCS["HD72 / EOV",GEOGCS["HD72",DATUM["Hungarian_Datum_1972",SPHEROID["GRS 1967",6378160,298.247167427,AUTHORITY["EPSG","7036"]],TOWGS84[52.17,-71.82,-14.9,0,0,0,0],AUTHORITY["EPSG","6237"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4237"]],PROJECTION["Hotine_Oblique_Mercator_Hungarian_Azimuthal_Centre"],PARAMETER["latitude_of_center",47.1443937222222],PARAMETER["longitude_of_center",19.0485717777778],PARAMETER["azimuth",90],PARAMETER["rectified_grid_angle",90],PARAMETER["scale_factor",0.99993],PARAMETER["false_easting",650000],PARAMETER["false_northing",200000],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","23700"]]
```

---

## 4. End-to-End Sequence & Communication Protocol

```mermaid
sequenceDiagram
    autonumber
    actor User as Urban Planner
    participant FE as Next.js / OpenLayers
    participant API as FastAPI Gateway
    participant Redis as Redis Pub/Sub & Queue
    participant Worker as Celery Worker Core
    participant DB as PostGIS DB
    participant FS as File Storage

    User->>FE: 1. Drag & drop map PDF/image
    FE->>API: POST /api/v1/projects/upload (multipart/form-data)
    API->>FS: Save raw file to /storage/projects/{id}/raw/
    API->>DB: INSERT into projects & files (status='UPLOADED')
    API->>Redis: Enqueue task: tasks.ingest_document(project_id)
    API-->>FE: HTTP 202 Accepted { project_id, job_id }
    
    FE->>API: GET /api/v1/projects/{id}/events (SSE connection)
    API-->>FE: SSE Connected

    Worker->>FS: Read PDF -> Render 300 DPI + Generate DZI pyramid
    Worker->>Redis: Publish SSE event (stage='INGESTION_COMPLETED', progress=100)
    Redis-->>API: PubSub event
    API-->>FE: SSE: { stage: 'INGESTION_COMPLETED', dzi_url: '/tiles/...' }
    FE->>FE: OpenLayers displays raw map via DeepZoom / Tile layer

    User->>FE: 2. Optionally uploads an EOV reference layer
    FE->>API: POST /api/v1/projects/{id}/georef/reference (multipart/form-data)
    API->>FS: Save reference layer to /storage/projects/{id}/reference/
    API->>DB: INSERT reference layer metadata and CRS
    FE->>FE: If no upload exists, load OpenStreetMap as default reference
    User->>FE: 3. Places 4 GCPs on the plan and confirms EOV coordinates against the selected reference
    FE->>API: POST /api/v1/projects/{id}/georef (GCP list + transform type)
    API->>DB: INSERT INTO gcps
    API->>Redis: Enqueue task: tasks.warp_georef(project_id)
    Worker->>FS: Compute affine/TPS -> GDAL Warp -> warped_eov.tif (COG)
    Worker->>Redis: Publish SSE event (stage='GEOREF_COMPLETED', rmse=0.18)
    API-->>FE: SSE: { stage: 'GEOREF_COMPLETED', cog_url: '/cog/...', rmse: 0.18 }
    FE->>FE: OpenLayers switches to EPSG:23700 view with GeoTIFF overlay

    User->>FE: 4. Clicks "Detect Legend"
    FE->>API: POST /api/v1/projects/{id}/legend/detect
    API->>Redis: Enqueue task: tasks.parse_legend(project_id)
    Worker->>FS: Detect legend bbox -> PaddleOCR -> Extract swatch & text
    Worker->>DB: INSERT INTO legend_classes
    Worker->>Redis: Publish SSE event (stage='LEGEND_PARSED')
    API-->>FE: SSE: { stage: 'LEGEND_PARSED', classes: [...] }
    FE->>FE: Displays editable Legend Table UI

    User->>FE: 4. Confirms/Edits legend classes & clicks "Start Vectorization"
    FE->>API: POST /api/v1/projects/{id}/vectorize (layer configurations)
    API->>Redis: Enqueue task: tasks.vectorize_layers(project_id)
    Worker->>Worker: Inpaint text labels on raster
    Worker->>Worker: Segment polygons, trace lines, extract points
    Worker->>Worker: Topology snapping & sliver cleaning
    Worker->>DB: INSERT Point, LineString, and Polygon geometries into PostGIS vector_features
    Worker->>FS: Write GeoJSONs & Shapefile archives
    Worker->>Redis: Publish SSE event (stage='VECTORIZATION_COMPLETED')
    API-->>FE: SSE: { stage: 'VECTORIZATION_COMPLETED', layers: [...] }

    FE->>FE: OpenLayers renders all vector layers over GeoTIFF
    User->>FE: 5. Edits/fixes vertices in OpenLayers editor & clicks "Save"
    FE->>API: PUT /api/v1/projects/{id}/layers/{layer_id}/features (GeoJSON)
    API->>DB: UPDATE PostGIS geometries

    User->>FE: 6. Clicks "Download ESRI Shapefile (.zip)"
    FE->>API: GET /api/v1/projects/{id}/export/shapefile
    API->>FS: Retrieve packaged export_project_{id}.zip
    API-->>User: File download stream (200 OK)
```

  Edited GeoJSON FeatureCollections are sent to `PUT /api/v1/projects/{id}/layers/{layer_id}/features`; the API validates the layer's single geometry type, updates the file artifact, and synchronizes the `vector_features` PostGIS table. The viewer supports modify, draw, delete, snap, split, merge, and attribute inspection modes for active Polygon and LineString layers.

---

## 5. Comprehensive API Data Contracts & Sockets

### 5.1. REST API Endpoints Specification

| Method | Endpoint | Request Body | Response Status & Body | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/projects` | `{ name: string, crs: string }` | `201 Created` `{ project_id, status }` | Initializes project session. |
| `POST` | `/api/v1/projects/{id}/upload` | `FormData (file, dpi)` | `202 Accepted` `{ job_id, file_id }` | Uploads raw raster/PDF plan. |
| `POST` | `/api/v1/projects/{id}/georef/reference` | `FormData (file, crs)` | `201 Created` `{ reference_id, crs }` | Uploads an optional georeferenced reference layer for GCP placement. |
| `GET` | `/api/v1/projects/{id}/events` | *None* | `200 OK (text/event-stream)` | Server-Sent Events real-time stream. |
| `POST` | `/api/v1/projects/{id}/georef` | `GCPPayload` | `202 Accepted` `{ job_id }` | Starts GDAL warping to EOV. |
| `GET` | `/api/v1/projects/{id}/georef/status` | *None* | `200 OK` `{ rmse, residuals, cog_url }` | Gets georeferencing quality metrics. |
| `POST` | `/api/v1/projects/{id}/legend/detect`| `{ bbox?: [ymin, xmin, ymax, xmax] }` | `202 Accepted` `{ job_id }` | Initiates AI legend parsing. |
| `GET` | `/api/v1/projects/{id}/legend` | *None* | `200 OK` `{ items: LegendItem[] }` | Fetches detected legend catalog. |
| `PUT` | `/api/v1/projects/{id}/legend` | `{ items: LegendItem[] }` | `200 OK` `{ updated_count }` | Updates user-edited legend classes. |
| `POST` | `/api/v1/projects/{id}/vectorize` | `VectorizeConfig` | `202 Accepted` `{ job_id }` | Starts multi-layer vectorization. |
| `GET` | `/api/v1/jobs/{job_id}` | *None* | `200 OK` `{ status, stage, progress_percent }` | Returns persistent processing-job state. |
| `GET` | `/api/v1/projects/{id}/events` | *None* | `200 OK (text/event-stream)` | Streams project job lifecycle and stage events. |
| `GET` | `/api/v1/projects/{id}/layers` | *None* | `200 OK` `{ layers: VectorLayerSummary[] }` | Returns layer catalog & GeoJSON URLs. |
| `GET` | `/api/v1/projects/{id}/layers/{layer_id}/geojson` | *None* | `200 OK` `FeatureCollection (GeoJSON)` | Streams layer GeoJSON to OpenLayers. |
| `PUT` | `/api/v1/projects/{id}/layers/{layer_id}/features` | `FeatureCollection` | `200 OK` `{ updated_features: number }` | Saves manual edits made in OpenLayers. |
| `GET` | `/api/v1/projects/{id}/export/shapefile` | *None* | `200 OK (application/zip)` | Downloads complete Shapefile ZIP. |

---

### 5.2. Detailed JSON Data Contracts

#### A. GCP Georeferencing Request (`GCPPayload`)
```json
{
  "transform_method": "auto",
  "target_crs": "EPSG:23700",
  "reference_id": "reference_01",
  "points": [
    { "id": "gcp_1", "pixel_x": 1240.5, "pixel_y": 890.2, "map_y": 654200.00, "map_x": 231400.00 },
    { "id": "gcp_2", "pixel_x": 18540.0, "pixel_y": 910.0, "map_y": 662000.00, "map_x": 231400.00 },
    { "id": "gcp_3", "pixel_x": 18520.8, "pixel_y": 12450.5, "map_y": 662000.00, "map_x": 225000.00 },
    { "id": "gcp_4", "pixel_x": 1250.0, "pixel_y": 12430.0, "map_y": 654200.00, "map_x": 225000.00 }
  ]
}
```

#### B. Legend Configuration Payload (`LegendItem[]`)
```json
[
  {
    "id": "leg_cls_01",
    "code": "Lk-1",
    "name": "Kisvárosias lakóterület",
    "geometry_type": "Polygon",
    "enabled": true,
    "color_signature": {
      "space": "LAB",
      "values": [78.2, 14.5, 62.1],
      "tolerance": 18.0
    },
    "stroke_signature": {
      "color_rgb": [0, 0, 0],
      "width_px": 2,
      "style": "solid"
    },
    "ocr_confidence": 0.96
  },
  {
    "id": "leg_cls_02",
    "code": "SZV",
    "name": "Kötelező szabályozási vonal",
    "geometry_type": "LineString",
    "enabled": true,
    "color_signature": {
      "space": "RGB",
      "values": [255, 0, 0],
      "tolerance": 25.0
    },
    "stroke_signature": {
      "color_rgb": [255, 0, 0],
      "width_px": 4,
      "style": "dash-dot"
    },
    "ocr_confidence": 0.91
  }
]
```

#### C. Real-Time Server-Sent Events (SSE) Protocol
```json
{
  "event": "PROGRESS_UPDATE",
  "data": {
    "job_id": "job_c78a94e0",
    "project_id": "proj_9981a",
    "stage": "VECTORIZING_LAYER",
    "current_step": 7,
    "total_steps": 12,
    "percent_complete": 58.3,
    "active_layer_code": "Lk-1",
    "active_layer_name": "Kisvárosias lakóterület",
    "features_extracted_so_far": 142,
    "message": "Tracing contours and applying Douglas-Peucker simplification (epsilon=0.2m)...",
    "timestamp": "2026-09-10T14:23:45.120Z"
  }
}
```

---

## 6. Physical Database Schema (PostgreSQL 16 + PostGIS 3.4)

```mermaid
erDiagram
    PROJECTS ||--o{ PROJECT_FILES : contains
    PROJECTS ||--o{ GCPS : has
    PROJECTS ||--o{ LEGEND_CLASSES : defines
    PROJECTS ||--o{ VECTOR_LAYERS : generates
    PROJECTS ||--o{ PROCESSING_JOBS : runs
    VECTOR_LAYERS ||--o{ VECTOR_FEATURES : contains

    PROJECTS {
        uuid id PK
        varchar name
        varchar description
        varchar status
        varchar target_crs
        timestamp created_at
        timestamp updated_at
    }

    PROJECT_FILES {
        uuid id PK
        uuid project_id FK
        varchar file_type
        varchar original_filename
        varchar storage_path
        integer width_px
        integer height_px
        integer dpi
        jsonb metadata
    }

    GCPS {
        uuid id PK
        uuid project_id FK
        float pixel_x
        float pixel_y
        float map_y
        float map_x
        float residual_error
        boolean is_active
    }

    LEGEND_CLASSES {
        uuid id PK
        uuid project_id FK
        varchar code
        varchar name
        varchar geometry_type
        jsonb visual_signature
        float ocr_confidence
        boolean is_enabled
    }

    VECTOR_LAYERS {
        uuid id PK
        uuid project_id FK
        uuid legend_class_id FK
        varchar layer_name
        varchar geometry_type
        integer feature_count
        varchar shapefile_path
        varchar geojson_path
    }

    VECTOR_FEATURES {
        uuid id PK
        uuid layer_id FK
        geometry geom
        jsonb properties
        float area_m2
        float length_m
    }

    PROCESSING_JOBS {
        uuid id PK
        uuid project_id FK
        varchar job_type
        varchar status
        float progress_percent
        jsonb error_details
        timestamp started_at
        timestamp finished_at
    }
```

### SQL DDL Schema Definition
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'CREATED',
    target_crs VARCHAR(50) NOT NULL DEFAULT 'EPSG:23700',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Project Files
CREATE TABLE project_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_type VARCHAR(50) NOT NULL, -- RAW_PDF, RAW_IMAGE, WARPED_COG, DZI_PYRAMID
    original_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    width_px INTEGER,
    height_px INTEGER,
    dpi INTEGER DEFAULT 300,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Ground Control Points (GCPs)
CREATE TABLE gcps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pixel_x DOUBLE PRECISION NOT NULL,
    pixel_y DOUBLE PRECISION NOT NULL,
    map_y DOUBLE PRECISION NOT NULL, -- EOV Y (Easting)
    map_x DOUBLE PRECISION NOT NULL, -- EOV X (Northing)
    residual_error DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Legend Classes
CREATE TABLE legend_classes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    geometry_type VARCHAR(30) NOT NULL, -- Polygon, LineString, Point
    visual_signature JSONB NOT NULL,
    ocr_confidence DOUBLE PRECISION,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Vector Layers
CREATE TABLE vector_layers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    legend_class_id UUID REFERENCES legend_classes(id) ON DELETE SET NULL,
    layer_name VARCHAR(100) NOT NULL,
    geometry_type VARCHAR(30) NOT NULL,
    feature_count INTEGER DEFAULT 0,
    shapefile_path VARCHAR(1024),
    geojson_path VARCHAR(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Vector Features (Spatial)
CREATE TABLE vector_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    layer_id UUID NOT NULL REFERENCES vector_layers(id) ON DELETE CASCADE,
    geom GEOMETRY(Geometry, 23700) NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    area_m2 DOUBLE PRECISION,
    length_m DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_vector_features_geom ON vector_features USING GIST(geom);
CREATE INDEX idx_vector_features_layer ON vector_features(layer_id);

-- 7. Processing Jobs
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    progress_percent DOUBLE PRECISION DEFAULT 0.0,
    error_details JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE
);
```

---

## 7. Storage Directory Hierarchy

```
/storage/
└── projects/
    └── {project_id}/
        ├── raw/
        │   └── master_plan_sheet_01.pdf
        ├── pyramid/
        │   ├── master.dzi
        │   └── master_files/0..14/
        ├── warped/
        │   └── warped_eov.tif (Cloud Optimized GeoTIFF)
        ├── legend/
        │   ├── legend_crop.png
        │   └── items/
        │       ├── item_01_Lk1.png
        │       └── item_02_SZV.png
        ├── masks/
        │   ├── inpaint_text_mask.png
        │   ├── clean_surface.png
        │   └── layer_masks/
        │       ├── Lk_1_mask.png
        │       └── SZV_mask.png
        ├── vector/
        │   ├── Lk_1_polygons.geojson
        │   └── SZV_lines.geojson
        └── export/
            ├── export_project_{project_id}.zip
            ├── Lk_1_POLYGON.shp
            ├── Lk_1_POLYGON.shx
            ├── Lk_1_POLYGON.dbf
            ├── Lk_1_POLYGON.cpg
            ├── Lk_1_POLYGON.prj
            ├── SZV_LINESTRING.shp
            ├── SZV_LINESTRING.shx
            ├── SZV_LINESTRING.dbf
            ├── SZV_LINESTRING.cpg
            └── SZV_LINESTRING.prj
```

---

## 8. Deployment, Scaling & Resilience

### 8.1. Docker Compose Production Profile
```yaml
version: '3.9'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend-api

  backend-api:
    build:
      context: ./backend
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://vectory:vectory_pass@postgis:5432/vectory_ai
      - REDIS_URL=redis://redis:6379/0
      - STORAGE_ROOT=/storage
    volumes:
      - shared-storage:/storage
    depends_on:
      - postgis
      - redis

  celery-worker-gpu:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      - DATABASE_URL=postgresql+asyncpg://vectory:vectory_pass@postgis:5432/vectory_ai
      - REDIS_URL=redis://redis:6379/0
      - STORAGE_ROOT=/storage
      - TORCH_DEVICE=cuda
    volumes:
      - shared-storage:/storage
    depends_on:
      - redis
      - postgis

  postgis:
    image: postgis/postgis:16-3.4
    environment:
      - POSTGRES_USER=vectory
      - POSTGRES_PASSWORD=vectory_pass
      - POSTGRES_DB=vectory_ai
    ports:
      - "5432:5432"
    volumes:
      - postgis-data:/var/lib/postgresql/data

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"

volumes:
  shared-storage:
  postgis-data:
```

### 8.2. Resilience & Edge Cases Handling
1. **Out-of-Memory (OOM) Protection:** Celery workers enforce max task memory limits (`--max-memory-per-child=4194304` - 4GB). Gigapixel images are processed via sliding window arrays using `numpy.memmap` and `rasterio.windows.Window`.
2. **Text Inpainting Failover:** If GPU-based inpainting runs out of VRAM, the engine falls back to CPU-optimized OpenCV Telea inpainting on multi-threaded slices.
3. **Shapefile Encoding:** To prevent corrupt characters in municipal GIS software (QGIS, DigiTerra, AutoCAD Map 3D), all DBF files include a `.cpg` file specifying `UTF-8` or `CP1250` code page.
