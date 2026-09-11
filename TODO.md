# VectoryAI Follow-up TODOs

This file records known gaps and limitations identified while implementing PBIs. It complements `backlog.md`; items remain open until their acceptance criteria are fully covered.

## PBI-02: Ingestion

- [ ] Add a real high-resolution stress fixture for A0/A00 plans.
- [ ] Benchmark peak memory and processing time on large plans.
- [ ] Verify that the full PDF rasterization path remains bounded for very large pages; PyMuPDF page rendering can still create a large intermediate raster.
- [ ] Add upload-progress integration tests covering browser progress events.
- [ ] Add end-to-end tests for corrupt PDFs, corrupt raster images, 200 MB boundary behavior, multi-page selection, and artifact cleanup.
- [ ] Add persistent project/file records and statuses instead of relying only on storage paths and registry files.
- [ ] Add a project listing/status API backed by persistent project metadata.

## PBI-03: Georeferencing

- [ ] Persist reference-layer metadata and CRS in the database.
- [ ] Add reference-layer deletion/replacement and multiple-reference-layer management.
- [ ] Add visual residual arrows with scale/legend controls and outlier highlighting.
- [ ] Add stronger GCP distribution warnings: clustering, near-collinearity, duplicate EOV coordinates, and insufficient sheet coverage.
- [ ] Add automatic transform-method recommendation to the UI with explanation and override confirmation.
- [ ] Add a formal user confirmation state that gates downstream vectorization readiness.
- [ ] Add a UI path for user-confirmed EOV coordinates independent of visual OSM matching.
- [ ] Add direct drag/snap editing for GCP markers and coordinate-pair correction.
- [ ] Validate affine, polynomial, and TPS warps against real reference plans, not only synthetic fixtures.
- [ ] Validate COG output with a dedicated COG validator and inspect internal tiling/overviews.
- [ ] Add GeoTIFF/COG reference-layer reprojection tests using a real EOV fixture.
- [ ] Add EOV grid tick/crosshair detection assist for US-2.2.
- [ ] Replace the temporary GeoJSON/GeoTIFF reference-layer API with durable object-storage-backed artifacts.

## PBI-04: OpenLayers Viewer

- [x] Add automatic discovery and rendering of generated legend-class vector layers.
- [x] Add a real layer catalog with names, class codes, geometry types, visibility, and opacity.
- [ ] Add raster/vector layer ordering and independent opacity persistence.
- [ ] Add project-aware viewer loading states and API error recovery.
- [ ] Add browser tests for EOV cursor coordinates, layer toggles, opacity, and COG rendering.

## PBI-05: Legend Detection and OCR

- [ ] Validate Hungarian OCR accuracy against real municipal TSZT/SZT plan fixtures.
- [ ] Add a curated real-plan legend fixture corpus with expected OCR/classes.
- [ ] Add OCR confidence scores and per-item review flags.
- [ ] Replace heuristic legend-box detection with a stronger layout model or contour/grid strategy.
- [ ] Improve row segmentation for multi-line legend entries, merged rows, and irregular layouts.
- [ ] Improve swatch extraction beyond a simple leading crop.
- [ ] Calibrate HSV/Lab tolerances and stroke/pattern signatures on real map samples.
- [ ] Detect line styles (solid, dashed, dotted) and localized point-symbol signatures.
- [ ] Persist OCR confidence, source crop, and visual signatures in PostGIS.
- [ ] Add retry/failure metadata for OCR worker jobs.

## PBI-06: Legend Review UI

- [ ] Add direct drag/resize legend-box editing over the source plan at full resolution.
- [ ] Add preview of the selected legend crop and sampled swatch.
- [ ] Add per-class color swatch preview and tolerance visualization.
- [ ] Add explicit OCR confidence and manual-review indicators.
- [ ] Add legend detection progress/error states and retry action.
- [ ] Add PostGIS-backed legend loading/update integration tests.
- [ ] Gate vectorization until legend review is explicitly confirmed.

## PBI-07: Polygon Vectorization

- [ ] Add realistic municipal raster fixtures with known polygon ground truth.
- [ ] Measure geometric IoU against manually digitized reference polygons.
- [ ] Add multi-window/vectorization tests on large raster inputs.
- [x] Integrate OCR text masking/inpainting from PBI-13 before polygonization.
- [x] Add deterministic OCR-mask/inpainting fixture coverage.
- [x] Add OCR confidence filtering and configurable text exclusion zones.
- [x] Keep inpainting geometry-aware so LineString and Point workflows are untouched.
- [x] Report color-mask IoU before and after polygon inpainting.
- [ ] Improve segmentation with full HSV/Lab tolerance controls and class-specific signatures.
- [ ] Handle disconnected regions, holes, and multipart polygons explicitly.
- [ ] Add polygon area/shape quality thresholds based on EOV units.
- [ ] Persist vector features in PostGIS as well as GeoJSON artifacts.
- [ ] Add automatic discovery of polygon layers to the OpenLayers viewer.
- [ ] Process all enabled Polygon legend classes in one project vectorization job.
- [ ] Add job progress events for segmentation and polygonization stages.

## PBI-08/PBI-09: Other Geometry Types

- [x] Implement initial line skeletonization, morphological gap bridging, smoothing, and strict LineString GeoJSON output.
- [x] Implement initial graph-based endpoint/junction tracing, short-spur pruning, and path chaining.
- [x] Complete and validate the branched-line graph fixture test in the rebuilt NetworkX worker image.
- [x] Implement color-mask connected-component point-symbol detection and centroid extraction.
- [x] Add project-relative template matching for symbols that are not isolated reliably by color.
- [x] Persist generated Point features in PostGIS with EPSG:23700 geometry and symbol metadata.
- [x] Enforce the initial strict LineString output contract.
- [x] Add an initial LineString fixture and output test.
- [x] Add an initial Point fixture with strict geometry and symbol metadata assertions.
- [ ] Add real municipal line fixtures and geometry-specific accuracy tests.
- [ ] Add real municipal point-symbol fixtures and accuracy tests for color/template detection.
- [ ] Evaluate YOLO-based symbol detection for crowded or visually ambiguous point classes.

## PBI-10/PBI-11/PBI-15: Export, Layers, Editing

- [x] Implement strict single-geometry Shapefile packaging with `.prj`, `.cpg`, metadata, and README.
- [x] Add attribute-name sanitization and Hungarian encoding tests.
- [x] Add GeoJSON layer catalog and download endpoints.
- [x] Add a viewer action for downloading the generated Shapefile ZIP.
- [x] Persist Polygon, LineString, and Point features in PostGIS for export/edit parity.
- [x] Add vector layer editor interactions: select, modify, draw, delete, and snap.
- [x] Add attribute inspection and feature-edit persistence.
- [x] Add geometry split and merge commands for active Polygon and LineString layers.
- [ ] Add editor undo/redo history and richer attribute editing.
- [x] Add topology validation panel and one-click cleanup integration.
- [x] Resolve same-layer polygon overlaps through deterministic planar partitioning.
- [x] Bridge and validate near-endpoint LineString gaps within the cleanup tolerance.
- [x] Persist cleaned topology results back to PostGIS.
- [ ] Add topology browser tests.

## PBI-12: Async Progress and Jobs

- [x] Add persistent job records and lifecycle states.
- [x] Add SSE event hub and frontend progress subscription.
- [x] Add retry/cancel support and user-visible failure recovery for processing jobs.
- [x] Add stage-level progress for ingestion, georeferencing, OCR, and vectorization.
- [x] Add stage-level progress for topology and export.
- [x] Configure Celery worker concurrency from deployment settings instead of the current fixed development default.
- [x] Run the worker as a non-root container user.

## Cross-Cutting Infrastructure

- [ ] Add formal SQLAlchemy/GeoAlchemy models and migrations for PostGIS tables.
- [ ] Add authentication and project-level authorization.
- [ ] Move durable source files and generated artifacts to S3-compatible object storage.
- [x] Add processing-job retention cleanup helper for completed/failed/cancelled jobs.
- [x] Schedule daily processing-job retention cleanup with Celery beat.
- [x] Persist processing-job action history.
- [ ] Add security limits for upload content, decompression bombs, and archive inputs.
- [ ] Add API integration tests and browser end-to-end tests to CI.
- [ ] Add production Render/worker deployment checks and secret configuration validation.
- [ ] Resolve the remaining Next.js workspace-root warning caused by multiple lockfiles.
- [ ] Add observability: structured logs, metrics, task tracing, and worker health alerts.

## Known Product Scope Decisions

- [ ] Keep fully blind zero-GCP georeferencing out of the initial release.
- [ ] Keep 3D building extraction out of the initial release.
- [ ] Keep government-portal bidirectional sync out of the initial release.
- [ ] Reassess free-tier deployment limitations before public use: Render free Postgres expiry, ephemeral filesystems, non-persistent Key Value, and worker availability.
