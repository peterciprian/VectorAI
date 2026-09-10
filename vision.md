# Project Vision: Intelligent Urban Plan Vectorization System (VectoryAI)

## 1. Executive Summary & Problem Statement

In urban planning and municipal chief architect workflows, reviewing and updating municipal master plans (településszerkezeti tervek - TSZT) and local zoning/regulatory plans (szabályozási tervek - SZT) frequently requires digitizing legacy plans. These plans are predominantly available only as raster formats (.pdf, .jpg, .png, or scanned paper maps).

Current manual digitization workflows (tracing boundaries in CAD or GIS software):
- **Resource and time intensive:** Manually digitizing a complex municipal master plan takes several days or even weeks.
- **Error-prone:** Manual tracing frequently introduces topological errors (overlaps, slivers, gaps, missing boundary lines, spatial misalignment).
- **Data loss & tedious classification:** Manually assigning legend classes and attributes to individual vector geometries is repetitive and prone to classification mistakes.

---

## 2. Vision Statement

> **"As an urban planner, digitizing legacy raster zoning and municipal master plans during plan reviews is a frequent bottleneck. The goal is to build an AI-assisted web application that automatically vectorizes large raster plans (predominantly PDF and high-resolution images), separates distinct classes based on the map's legend into isolated layers containing strictly uniform geometry types (points, polylines, or polygons), and outputs standard ESRI Shapefile (.shp) datasets ready for GIS use."**

---

## 3. Goals and Value Proposition

### 3.1. Key Objectives
1. **Dramatic Time Savings:** Reduce digitization turnaround time by 70–80% via automated AI-driven pre-segmentation and vectorization.
2. **Strict Layer & Geometry Structure:**
   - Every legend class (zoning districts, regulatory lines, buffer zones, point features) is mapped to its own isolated layer.
   - Each layer contains strictly one geometry type (`Polygon`, `PolyLine`, or `Point`), adhering strictly to ESRI Shapefile specifications.
3. **National GIS & CRS Compliance:** Native support for the Hungarian National Grid / Uniform National Projection (EOV - EPSG:23700) and standard WGS84 / Web Mercator coordinate systems.
4. **Intuitive, Domain-Specific User Experience:** A modern web UI (React + OpenLayers) tailored for urban planners without requiring deep programming or AI infrastructure knowledge.

---

## 4. Target Audience & Stakeholders

- **Urban Planners & Master Planning Consultancies:** Professionals conducting regulatory plan revisions and municipal development strategies.
- **Municipal Chief Architect Offices & Technical Departments:** Municipalities maintaining local GIS databases and digital spatial plan archives.
- **GIS Experts & Land Surveyors:** Professionals preparing baseline maps and zoning datasets for cadastral integrations.

---

## 5. Key Performance Indicators (KPIs)

| Metric | Target | Measurement Method |
| :--- | :--- | :--- |
| **Processing Time** | < 5 minutes / A0 map sheet | From file upload to shapefile readiness. |
| **Vectorization Accuracy** | > 90% geometric IoU | Intersection over Union against reference manual digitalizations. |
| **Topological Integrity** | 0 illegal overlaps / slivers | Automated topology rule check output. |
| **Legend Recognition Rate** | > 85% automated class matching | Correctly identified legend items matched to visual map symbols. |

---

## 6. Scope Boundaries

### In-Scope (Phase 1):
- Upload and processing of raster/vector PDFs, TIFFs, JPGs, and PNGs at high resolutions (300+ DPI).
- Interactive and semi-automated georeferencing in EOV (EPSG:23700) using Ground Control Points (GCPs), with an optional user-uploaded reference layer and an OpenStreetMap fallback when no reference layer is provided.
- Legend area detection, OCR extraction of class names, and color/symbol palette extraction.
- Layer-specific segmentation and vectorization (polygons, polylines, points).
- Interactive web map preview and vector layer inspection/editing using OpenLayers.
- Export as ESRI Shapefile packages (.zip containing `.shp`, `.shx`, `.dbf`, `.prj`).

### Out-of-Scope (Phase 1):
- 3D building height/envelope extraction.
- Fully automated zero-reference blind georeferencing without coordinate grids or control points.
- Direct live bi-directional sync with government portal APIs (e.g., Lechner Knowledge Center E-TÉR).
