# User Stories: VectoryAI

## Overview & Role Definitions

- **Urban Planner / Településtervező (Primary User):** Plans and revises municipal regulatory and zoning plans. Needs fast, accurate vector data from legacy maps in EOV coordinate system.
- **Municipal GIS Administrator / Főépítészi munkatárs:** Maintains municipal geospatial databases and validates topological accuracy of zoning layers.
- **System Administrator:** Manages deployment, worker resource limits, and job monitoring.

---

## Epic 1: Project Management & Plan Ingestion

### US-1.1: Upload High-Resolution Urban Plan
- **As an** Urban Planner,
- **I want to** upload large PDF (vector/raster) or high-resolution image files (JPG, PNG, TIFF) through the web interface,
- **So that** I can initiate the digitization process without worrying about file size or format incompatibilities.

**Acceptance Criteria:**
- Accepts files up to 200 MB.
- Supports single-page and multi-page PDF files (allows page selection if multi-page).
- Displays upload progress bar and file validation checks (detects invalid or corrupted files).
- Automatically creates a new project session and generates a high-resolution preview thumbnail.

### US-1.2: Project Dashboard & File Overview
- **As an** Urban Planner,
- **I want to** view a list of my ongoing and completed digitization projects,
- **So that** I can resume work, track progress, or re-download previously generated shapefiles.

**Acceptance Criteria:**
- Dashboard lists project name, creation date, source filename, current status (Uploaded, Georeferenced, Vectorized, Ready), and action buttons.
- Allows renaming and deleting projects.

---

## Epic 2: Georeferencing & Spatial Calibration (EOV / EPSG:23700)

### US-2.1: Interactive Ground Control Point (GCP) Placement
- **As an** Urban Planner,
- **I want to** optionally upload a georeferenced reference layer and use it, or use the default OpenStreetMap reference layer when no reference layer is provided, to match Ground Control Points (GCPs) on the uploaded map sheet with Hungarian EOV coordinates,
- **So that** the resulting vector data is accurately placed in real-world geospatial coordinates.

**Acceptance Criteria:**
- The georeferencing workspace provides a dual-view or split-map mode: one pane shows the raw raster plan and the other shows the selected reference layer in EPSG:23700.
- The user may upload an optional georeferenced reference layer, such as an EOV GeoTIFF/COG, GeoJSON, or compatible vector/raster GIS layer, and specify or confirm its CRS.
- If no reference layer is uploaded, the system loads an OpenStreetMap layer by default for visual orientation and GCP placement.
- An uploaded reference layer takes precedence over the default OpenStreetMap layer and can be toggled on or off during GCP placement.
- Allows adding, modifying, and deleting at least 3-4 GCP pairs (Image X,Y to EOV X,Y).
- Allows the user to enter or confirm the EOV coordinates for each selected reference point; the system must not treat an unconfirmed visual match as a valid GCP.
- Computes and displays Root Mean Square Error (RMSE) for positional accuracy assessment.
- Displays per-point residuals and warns when GCPs are clustered, poorly distributed, duplicated, or inconsistent with the selected transformation.
- Requires user confirmation of the GCP set and georeferencing preview before vectorization can start.

### US-2.2: Coordinate Grid Detection Assist
- **As an** Urban Planner,
- **I want** the system to detect printed EOV coordinate crosshairs/grid ticks on the map border,
- **So that** GCP input is accelerated with semi-automatic snap suggestions.

**Acceptance Criteria:**
- Detects '+' coordinate tick marks along sheet margins.
- Prompts user to confirm or enter the numeric EOV values (e.g., $Y = 650000, X = 230000$).

---

## Epic 3: Legend Recognition & Class Extraction

### US-3.1: Automatic Legend Box Detection & OCR Parsing
- **As an** Urban Planner,
- **I want** the system to automatically detect the map's legend (jelmagyarázat) area and read the category names,
- **So that** I do not have to manually type out every zoning code and description.

**Acceptance Criteria:**
- Highlights the detected legend bounding box with manual resize/reposition capability.
- Runs Hungarian-optimized OCR to extract zone codes (e.g., "Lk-1", "Vt", "Z", "Kb-R") and textual descriptions.
- Samples representative fill color, line color/style, or point icon for each detected item.

### US-3.2: Interactive Legend Configuration & Geometry Assignment
- **As an** Urban Planner,
- **I want to** review and adjust the detected legend classes and assign their geometry type (`Polygon`, `LineString`, `Point`),
- **So that** each map element is routed to the correct layer type before vectorization runs.

**Acceptance Criteria:**
- Displays an editable legend table with:
  - Class Name & Code
  - Geometry Type Selector (`Polygon` / `LineString` / `Point`)
  - Color Swatch & Color Tolerance Slider
  - Enable / Disable checkbox for processing
- Allows adding custom legend classes manually if any were missed by OCR.

---

## Epic 4: AI Vectorization & Layer Separation

### US-4.1: Zoning District Polygon Vectorization with Text Inpainting
- **As an** Urban Planner,
- **I want** area zoning boundaries (övezeti poligonok) to be extracted cleanly without holes caused by labels or street names,
- **So that** I get continuous, topologically clean polygon layers for every zoning category.

**Acceptance Criteria:**
- Automatically identifies and in-paints text labels inside polygons prior to contour extraction.
- Generates separate vector polygons for each zoning color category.
- Adheres strictly to the single-geometry rule: only `Polygon` features are placed in polygon layers.

### US-4.2: Regulatory Line & Boundary Tracing
- **As an** Urban Planner,
- **I want** regulatory lines (szabályozási vonalak, építési vonalak, védőtávolságok) to be extracted as smooth, continuous polylines,
- **So that** linear constraints are preserved with high geometric fidelity.

**Acceptance Criteria:**
- Skeletons and traces linear features matching line color/stroke signatures.
- Bridges minor gaps in dashed or dotted regulatory lines based on proximity heuristics.
- Generates strictly `LineString` features.

### US-4.3: Point Symbol Detection
- **As an** Urban Planner,
- **I want** point-like symbols (e.g., protected trees, monument markers, survey benchmarks) to be identified and converted into point coordinates,
- **So that** isolated point elements are represented as true spatial `Point` features.

**Acceptance Criteria:**
- Detects symbol locations and extracts centroid coordinates.
- Stores symbol type and label in the feature's attribute table.
- Generates strictly `Point` features.

---

## Epic 5: Topology Cleaning & Interactive OpenLayers Inspection

### US-5.1: Multi-Layer OpenLayers Map Inspection
- **As an** Urban Planner,
- **I want to** view all generated vector layers overlaid on the original georeferenced raster plan inside an OpenLayers map,
- **So that** I can visually verify vector-to-raster alignment and toggle individual layers on and off.

**Acceptance Criteria:**
- OpenLayers viewport supports zooming, panning, opacity sliders for raster vs. vector layers.
- Layer switcher sidebar allowing toggling visibility of each legend class.
- Supports EOV (EPSG:23700) coordinate display under cursor.

### US-5.2: In-Browser Geometry Editing & Snapping
- **As an** Urban Planner,
- **I want to** select, modify vertices, split, or merge polygons/lines directly in OpenLayers,
- **So that** I can make quick manual corrections to any AI segmentation inaccuracies before downloading.

**Acceptance Criteria:**
- OpenLayers modify, snap, and draw interactions enabled for active vector layers.
- Snapping to neighboring polygon vertices to prevent manual slivers.
- Attribute inspection popup when clicking a vector feature.

### US-5.3: Automated Topology Validation
- **As an** Urban Planner,
- **I want** the system to automatically validate topology (checking for overlapping polygons of the same level or unclosed polygons),
- **So that** the exported data complies with standard municipal GIS validation criteria.

**Acceptance Criteria:**
- Flags overlapping polygons and micro-slivers (< 1 $m^2$) in a validation panel.
- Provides a "One-Click Auto-Clean & Snap" action.

---

## Epic 6: Shapefile Packaging & Export

### US-6.1: ESRI Shapefile Bundle Download (.zip)
- **As an** Urban Planner,
- **I want to** download the complete digitized project as an ESRI Shapefile ZIP archive,
- **So that** I can immediately import the layers into QGIS, ArcGIS, or AutoCAD Map 3D.

**Acceptance Criteria:**
- Output ZIP contains a dedicated `.shp`, `.shx`, `.dbf`, and `.prj` file for every enabled legend class.
- `.prj` file contains exact WKT definition for Hungarian EOV (EPSG:23700).
- `.dbf` attribute tables use UTF-8 or Hungarian ISO-8859-2 encoding with properly formatted column names (<= 10 chars, ASCII compliant).
- Strict separation: no mixed geometry types exist within any single `.shp` file.

### US-6.2: GeoJSON & DXF Secondary Export
- **As an** Urban Planner,
- **I want** the option to also download GeoJSON or DXF files,
- **So that** I can use the data in web applications or legacy CAD tools if needed.

**Acceptance Criteria:**
- "Export as GeoJSON" and "Export as DXF" options available in the export dialog.

---

## Epic 7: Real-Time Processing Feedback

### US-7.1: Live Processing Progress Tracker
- **As an** Urban Planner,
- **I want to** see step-by-step progress feedback while the AI is processing the map,
- **So that** I understand how long the operation will take and what stage (OCR, Segmentation, Topology) is currently executing.

**Acceptance Criteria:**
- Progress bar and textual stage updates streamed in real time (via SSE or WebSockets).
- Informative error notifications with clear recovery steps if an error occurs.
