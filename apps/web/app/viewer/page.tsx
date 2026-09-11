"use client";

import "ol/ol.css";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import WebGLTileLayer from "ol/layer/WebGLTile";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import Modify from "ol/interaction/Modify";
import Draw from "ol/interaction/Draw";
import Snap from "ol/interaction/Snap";
import Select from "ol/interaction/Select";
import OSM from "ol/source/OSM";
import GeoTIFF from "ol/source/GeoTIFF";
import GeoJSON from "ol/format/GeoJSON";
import Projection from "ol/proj/Projection";
import { transform } from "ol/proj";
import Style from "ol/style/Style";
import Stroke from "ol/style/Stroke";
import Fill from "ol/style/Fill";
import CircleStyle from "ol/style/Circle";
import LineString from "ol/geom/LineString";
import Feature from "ol/Feature";
import { featureCollection, lineString, polygon } from "@turf/helpers";
import intersect from "@turf/intersect";
import union from "@turf/union";
import proj4 from "proj4";
import { register } from "ol/proj/proj4";
import { getTranslations, type Locale } from "../../lib/i18n";
import { applyWmtsBaseLayer } from "../../lib/wmts";

proj4.defs(
  "EPSG:23700",
  "+proj=krovak +lat_0=47.14439372222222 +lon_0=19.04857177777778 +alpha=90 +k=0.99993 +x_0=650000 +y_0=200000 +ellps=GRS67 +towgs84=52.17,-71.82,-14.9,0 +units=m +no_defs +type=crs",
);
register(proj4);

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const defaultLocale: Locale = "en";

type DiscoveredLayer = {
  layer_id: string;
  code: string;
  name: string;
  geometry_type: string;
  feature_count: number;
};

export default function ViewerPage() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [rasterVisible, setRasterVisible] = useState(true);
  const [referenceVisible, setReferenceVisible] = useState(true);
  const [residualVisible, setResidualVisible] = useState(true);
  const [rasterOpacity, setRasterOpacity] = useState(0.85);
  const [referenceOpacity, setReferenceOpacity] = useState(0.35);
  const [cursorCoordinate, setCursorCoordinate] = useState<
    [number, number] | null
  >(null);
  const [discoveredLayers, setDiscoveredLayers] = useState<DiscoveredLayer[]>([]);
  const [topologyStatus, setTopologyStatus] = useState<{ valid: boolean; issue_count: number } | null>(null);
  const [topologyBusy, setTopologyBusy] = useState(false);
  const [activeLayerId, setActiveLayerId] = useState("");
  const [editMode, setEditMode] = useState<"none" | "modify" | "draw" | "delete" | "inspect" | "split" | "merge">("none");
  const [editStatus, setEditStatus] = useState("");
  const [selectedProperties, setSelectedProperties] = useState<Record<string, unknown> | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const rasterLayerRef = useRef<WebGLTileLayer | null>(null);
  const referenceLayerRef = useRef<TileLayer<OSM> | null>(null);
  const residualLayerRef = useRef<VectorLayer<VectorSource> | null>(null);
  const vectorLayerRefs = useRef<Record<string, VectorLayer<VectorSource>>>({});
  const editInteractionRefs = useRef<(Modify | Draw | Snap | Select)[]>([]);
  const selectedFeatureRef = useRef<Feature | null>(null);
  const historyRef = useRef<Record<string, { past: object[]; future: object[] }>>({});
  const content = getTranslations(locale);

  useEffect(() => {
    const savedLocale = window.localStorage.getItem("vectoryai-locale");
    if (savedLocale === "en" || savedLocale === "hu") setLocale(savedLocale);
    setProjectId(
      new URLSearchParams(window.location.search).get("project") || "",
    );
  }, []);

  useEffect(() => {
    if (!projectId || !mapElement.current) return;
    let disposed = false;
    fetch(`${apiBase}/api/v1/projects/${projectId}/georef/status`)
      .then((response) => {
        if (!response.ok) throw new Error("Viewer data is not ready");
        return response.json();
      })
      .then((georef) => {
        if (disposed || !mapElement.current) return;
        const eovProjection = new Projection({
          code: "EPSG:23700",
          units: "m",
        });
        const rasterLayer = new WebGLTileLayer({
          opacity: rasterOpacity,
          source: new GeoTIFF({
            sources: [{ url: `${apiBase}${georef.cog_url}` }],
            projection: "EPSG:23700",
          }),
        });
        const referenceLayer = new TileLayer({
          opacity: referenceOpacity,
          source: new OSM(),
        });
        void applyWmtsBaseLayer(referenceLayer, apiBase);
        const residualSource = new VectorSource();
        (georef.residuals || []).forEach(
          (residual: {
            actual_map_x: number;
            actual_map_y: number;
            predicted_map_x: number;
            predicted_map_y: number;
          }) => {
            residualSource.addFeature(
              new Feature(
                new LineString([
                  [residual.actual_map_x, residual.actual_map_y],
                  [residual.predicted_map_x, residual.predicted_map_y],
                ]),
              ),
            );
          },
        );
        const residualLayer = new VectorLayer({
          source: residualSource,
          opacity: 1,
          style: new Style({
            stroke: new Stroke({ color: "#d7f26c", width: 3 }),
          }),
        });
        const map = new OlMap({
          target: mapElement.current,
          layers: [referenceLayer, rasterLayer, residualLayer],
          view: new View({
            projection: eovProjection,
            center: [georef.transform[2], georef.transform[5]],
            zoom: 1,
          }),
        });
        map.on("pointermove", (event) => {
          const [easting, northing] = transform(
            event.coordinate,
            "EPSG:23700",
            "EPSG:23700",
          );
          setCursorCoordinate([easting, northing]);
        });
        mapRef.current = map;
        rasterLayerRef.current = rasterLayer;
        referenceLayerRef.current = referenceLayer;
        residualLayerRef.current = residualLayer;
        fetch(`${apiBase}/api/v1/projects/${projectId}/layers`)
          .then((response) => {
            if (!response.ok) throw new Error("Layer catalog is not ready");
            return response.json();
          })
          .then(async (catalog: { layers: DiscoveredLayer[] & { geojson_url?: string }[] }) => {
            if (disposed) return;
            const loadedLayers: DiscoveredLayer[] = [];
            await Promise.all(
              catalog.layers.map(async (layer) => {
                const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/layers/${layer.layer_id}/geojson`);
                if (!response.ok) return;
                const collection = await response.json();
                const source = new VectorSource({
                  features: new GeoJSON().readFeatures(collection, {
                    dataProjection: "EPSG:23700",
                    featureProjection: "EPSG:23700",
                  }),
                });
                const vectorLayer = new VectorLayer({
                  source,
                  opacity: 0.9,
                  style: layer.geometry_type === "Point"
                    ? new Style({ image: new CircleStyle({ radius: 6, fill: new Fill({ color: "#e85d75" }), stroke: new Stroke({ color: "#fff", width: 2 }) }) })
                    : layer.geometry_type === "LineString"
                      ? new Style({ stroke: new Stroke({ color: "#e85d75", width: 2 }) })
                      : new Style({ fill: new Fill({ color: "rgba(232, 93, 117, 0.22)" }), stroke: new Stroke({ color: "#e85d75", width: 1 }) }),
                });
                map.addLayer(vectorLayer);
                vectorLayerRefs.current[layer.layer_id] = vectorLayer;
                loadedLayers.push(layer);
              }),
            );
            setDiscoveredLayers(loadedLayers);
          })
          .catch(() => setDiscoveredLayers([]));
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    return () => {
      disposed = true;
      mapRef.current?.setTarget(undefined);
      mapRef.current = null;
      vectorLayerRefs.current = {};
      setDiscoveredLayers([]);
    };
  }, [projectId]);

  useEffect(() => {
    const map = mapRef.current;
    const vectorLayer = vectorLayerRefs.current[activeLayerId];
    const source = vectorLayer?.getSource();
    editInteractionRefs.current.forEach((interaction) => map?.removeInteraction(interaction));
    editInteractionRefs.current = [];
    setSelectedProperties(null);
    selectedFeatureRef.current = null;
    if (!map || !source || editMode === "none") return;
    if (editMode === "modify") {
      const modify = new Modify({ source });
      const snap = new Snap({ source });
      modify.on("modifystart", () => recordHistory(activeLayerId));
      map.addInteraction(modify);
      map.addInteraction(snap);
      editInteractionRefs.current = [modify, snap];
    }
    if (editMode === "draw") {
      const layer = discoveredLayers.find((candidate) => candidate.layer_id === activeLayerId);
      if (!layer) return;
      const draw = new Draw({ source, type: layer.geometry_type as "Point" | "LineString" | "Polygon" });
      const snap = new Snap({ source });
      draw.on("drawstart", () => recordHistory(activeLayerId));
      map.addInteraction(draw);
      map.addInteraction(snap);
      editInteractionRefs.current = [draw, snap];
    }
    if (["delete", "inspect", "split", "merge"].includes(editMode)) {
      const select = new Select({ layers: [vectorLayer], multi: editMode === "merge" });
      select.on("select", (event) => {
        const feature = event.selected[0];
        if (editMode === "delete" && feature) { recordHistory(activeLayerId); source.removeFeature(feature); }
        if (editMode === "inspect" && feature) { selectedFeatureRef.current = feature; setSelectedProperties(feature.getProperties()); }
        if (editMode === "split" && feature) { recordHistory(activeLayerId); splitFeature(source, feature); }
        if (editMode === "merge" && event.selected.length >= 2) mergeFeatures(source, event.selected);
      });
      map.addInteraction(select);
      editInteractionRefs.current = [select];
    }
    return () => {
      editInteractionRefs.current.forEach((interaction) => map.removeInteraction(interaction));
      editInteractionRefs.current = [];
    };
  }, [activeLayerId, discoveredLayers, editMode]);

  function updateDiscoveredLayer(layerId: string, visible: boolean) {
    vectorLayerRefs.current[layerId]?.setVisible(visible);
  }

  function updateDiscoveredOpacity(layerId: string, opacity: number) {
    vectorLayerRefs.current[layerId]?.setOpacity(opacity);
  }

  function snapshotSource(layerId: string): object {
    const source = vectorLayerRefs.current[layerId]?.getSource();
    return source ? new GeoJSON().writeFeaturesObject(source.getFeatures(), { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }) : { type: "FeatureCollection", features: [] };
  }

  function recordHistory(layerId: string) {
    if (!layerId) return;
    const history = historyRef.current[layerId] || { past: [], future: [] };
    history.past = [...history.past.slice(-19), snapshotSource(layerId)];
    history.future = [];
    historyRef.current[layerId] = history;
    setHistoryVersion((version) => version + 1);
  }

  function restoreSnapshot(layerId: string, snapshot: object) {
    const source = vectorLayerRefs.current[layerId]?.getSource();
    if (!source) return;
    source.clear();
    source.addFeatures(new GeoJSON().readFeatures(snapshot, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }));
  }

  function undoEdit() {
    const history = historyRef.current[activeLayerId];
    if (!history?.past.length) return;
    const current = snapshotSource(activeLayerId);
    const previous = history.past.pop();
    if (!previous) return;
    history.future.push(current);
    restoreSnapshot(activeLayerId, previous);
    setHistoryVersion((version) => version + 1);
  }

  function redoEdit() {
    const history = historyRef.current[activeLayerId];
    if (!history?.future.length) return;
    const current = snapshotSource(activeLayerId);
    const next = history.future.pop();
    if (!next) return;
    history.past.push(current);
    restoreSnapshot(activeLayerId, next);
    setHistoryVersion((version) => version + 1);
  }

  function updateSelectedProperty(property: "label" | "code", value: string) {
    const feature = selectedFeatureRef.current;
    if (!feature) return;
    recordHistory(activeLayerId);
    feature.set(property, value);
    setSelectedProperties(feature.getProperties());
  }

  function replaceWithSplitFeatures(source: VectorSource, feature: Feature, splitFeatures: Feature[]) {
    source.removeFeature(feature);
    splitFeatures.forEach((splitFeature) => source.addFeature(splitFeature));
    setEditStatus(`${splitFeatures.length} features created`);
  }

  function splitFeature(source: VectorSource, feature: Feature) {
    const geometry = feature.getGeometry();
    if (!geometry) return;
    if (geometry.getType() === "LineString") {
      const coordinates = (geometry as LineString).getCoordinates();
      if (coordinates.length < 3) {
        setEditStatus("Line needs at least three vertices to split");
        return;
      }
      const midpoint = Math.floor((coordinates.length - 1) / 2);
      const first = lineString(coordinates.slice(0, midpoint + 1) as [number, number][]);
      const second = lineString(coordinates.slice(midpoint) as [number, number][]);
      replaceWithSplitFeatures(source, feature, [first, second].map((result) => new GeoJSON().readFeature(result as any, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }) as Feature));
      return;
    }
    if (geometry.getType() === "Polygon") {
      const extent = geometry.getExtent();
      const centerX = (extent[0] + extent[2]) / 2;
      const halves = [
        polygon([[[extent[0], extent[1]], [centerX, extent[1]], [centerX, extent[3]], [extent[0], extent[3]], [extent[0], extent[1]]]]),
        polygon([[[centerX, extent[1]], [extent[2], extent[1]], [extent[2], extent[3]], [centerX, extent[3]], [centerX, extent[1]]]]),
      ];
      const sourcePolygon = new GeoJSON().writeFeatureObject(feature, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" });
      const splitFeatures: Feature[] = halves.map((half) => intersect(featureCollection([sourcePolygon as any, half as any]) as any)).filter(Boolean).map((result) => new GeoJSON().readFeature(result as any, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }) as Feature);
      if (splitFeatures.length === 2) replaceWithSplitFeatures(source, feature, splitFeatures);
      else setEditStatus("Polygon could not be split at its center");
      return;
    }
    setEditStatus("Split is available for lines and polygons");
  }

  function mergeFeatures(source: VectorSource, features: Feature[]) {
    if (features.length < 2) return;
    const geometryType = features[0].getGeometry()?.getType();
    if (!features.every((feature) => feature.getGeometry()?.getType() === geometryType) || !["LineString", "Polygon"].includes(geometryType || "")) {
      setEditStatus("Merge requires two or more lines or polygons");
      return;
    }
    recordHistory(activeLayerId);
    const turfFeatures = features.map((feature) => new GeoJSON().writeFeatureObject(feature, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }));
    const merged = geometryType === "Polygon" ? union(featureCollection(turfFeatures as any) as any) : lineString(turfFeatures.flatMap((feature) => (feature.geometry as any).coordinates) as [number, number][]);
    if (!merged) return;
    features.forEach((feature) => source.removeFeature(feature));
    source.addFeature(new GeoJSON().readFeature(merged as any, { dataProjection: "EPSG:23700", featureProjection: "EPSG:23700" }) as Feature);
    setEditStatus("Features merged");
  }

  async function validateTopology() {
    setTopologyBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/topology/validate`);
      if (!response.ok) throw new Error("Topology validation failed");
      setTopologyStatus(await response.json());
    } catch {
      setTopologyStatus(null);
    } finally {
      setTopologyBusy(false);
    }
  }

  async function cleanTopology() {
    setTopologyBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/topology/clean`, { method: "POST" });
      if (!response.ok) throw new Error("Topology cleanup failed");
      const result = await response.json();
      setTopologyStatus(result.validation);
    } catch {
      setTopologyStatus(null);
    } finally {
      setTopologyBusy(false);
    }
  }

  async function saveActiveLayer() {
    const source = vectorLayerRefs.current[activeLayerId]?.getSource();
    if (!source || !activeLayerId) return;
    setEditStatus("saving");
    const collection = new GeoJSON().writeFeaturesObject(source.getFeatures(), {
      dataProjection: "EPSG:23700",
      featureProjection: "EPSG:23700",
    });
    try {
      const response = await fetch(`${apiBase}/api/v1/projects/${projectId}/layers/${activeLayerId}/features`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collection),
      });
      if (!response.ok) throw new Error("Save failed");
      setEditStatus("saved");
    } catch {
      setEditStatus("error");
    }
  }

  function updateLayer(
    layer: "raster" | "reference" | "residual",
    visible: boolean,
  ) {
    if (layer === "raster") {
      setRasterVisible(visible);
      rasterLayerRef.current?.setVisible(visible);
    }
    if (layer === "reference") {
      setReferenceVisible(visible);
      referenceLayerRef.current?.setVisible(visible);
    }
    if (layer === "residual") {
      setResidualVisible(visible);
      residualLayerRef.current?.setVisible(visible);
    }
  }

  function updateOpacity(layer: "raster" | "reference", opacity: number) {
    if (layer === "raster") {
      setRasterOpacity(opacity);
      rasterLayerRef.current?.setOpacity(opacity);
    }
    if (layer === "reference") {
      setReferenceOpacity(opacity);
      referenceLayerRef.current?.setOpacity(opacity);
    }
  }

  return (
    <main className="viewer-page">
      <nav className="nav shell-width" aria-label={content.navigation.main}>
        <Link className="brand" href="/">
          <span className="brand-mark">V</span> VectoryAI
        </Link>
        <div className="nav-links">
          <Link className="back-link" href={`/georef?project=${projectId}`}>
            &#8592; {content.upload.back}
          </Link>
          <label className="language-picker">
            <span className="sr-only">{content.language.label}</span>
            <select
              value={locale}
              onChange={(event) => {
                setLocale(event.target.value as Locale);
                window.localStorage.setItem(
                  "vectoryai-locale",
                  event.target.value,
                );
              }}
              aria-label={content.language.label}
            >
              <option value="en">EN</option>
              <option value="hu">HU</option>
            </select>
          </label>
        </div>
      </nav>
      <section className="viewer-shell shell-width">
        <div className="viewer-heading">
          <p className="eyebrow">
            <span className="eyebrow-dot" /> {content.viewer.eyebrow}
          </p>
          <h1>
            {content.viewer.titleBefore} <em>{content.viewer.titleEmphasis}</em>
          </h1>
          <p className="lede">{content.viewer.description}</p>
        </div>
        {status === "error" && (
          <p className="upload-error">{content.viewer.notReady}</p>
        )}
        {status === "loading" && (
          <p className="upload-hint">{content.viewer.loading}</p>
        )}
        <div className="viewer-layout">
          <div ref={mapElement} className="viewer-map" />
          <aside className="layer-panel">
            <p className="section-kicker">{content.viewer.layers}</p>
            <a
              className="primary-button"
              href={`${apiBase}/api/v1/projects/${projectId}/export/shapefile`}
              download
            >
              {content.viewer.downloadShapefile}
            </a>
            <div className="viewer-topology">
              <button type="button" className="secondary-button" onClick={validateTopology} disabled={topologyBusy}>
                {content.viewer.validateTopology}
              </button>
              {topologyStatus && (
                <p className={topologyStatus.valid ? "topology-valid" : "upload-error"}>
                  {topologyStatus.valid
                    ? content.viewer.topologyValid
                    : `${topologyStatus.issue_count} ${content.viewer.topologyIssues}`}
                </p>
              )}
              {topologyStatus && !topologyStatus.valid && (
                <button type="button" className="secondary-button" onClick={cleanTopology} disabled={topologyBusy}>
                  {content.viewer.cleanTopology}
                </button>
              )}
            </div>
            <div className="viewer-editor">
              <p className="section-kicker">{content.viewer.editor}</p>
              <select aria-label={content.viewer.activeLayer} value={activeLayerId} onChange={(event) => setActiveLayerId(event.target.value)}>
                <option value="">{content.viewer.chooseLayer}</option>
                {discoveredLayers.map((layer) => <option key={layer.layer_id} value={layer.layer_id}>{layer.code || layer.name || layer.layer_id}</option>)}
              </select>
              <select aria-label={content.viewer.editMode} value={editMode} onChange={(event) => setEditMode(event.target.value as typeof editMode)} disabled={!activeLayerId}>
                <option value="none">{content.viewer.editNone}</option>
                <option value="modify">{content.viewer.editModify}</option>
                <option value="draw">{content.viewer.editDraw}</option>
                <option value="delete">{content.viewer.editDelete}</option>
                <option value="inspect">{content.viewer.editInspect}</option>
                <option value="split">{content.viewer.editSplit}</option>
                <option value="merge">{content.viewer.editMerge}</option>
              </select>
              <button type="button" className="secondary-button" onClick={saveActiveLayer} disabled={!activeLayerId || editMode === "none"}>
                {content.viewer.saveEdits}
              </button>
              <button type="button" className="secondary-button" onClick={undoEdit} disabled={!activeLayerId || !(historyRef.current[activeLayerId]?.past.length) || historyVersion < 0}>
                {content.viewer.undoEdit}
              </button>
              <button type="button" className="secondary-button" onClick={redoEdit} disabled={!activeLayerId || !(historyRef.current[activeLayerId]?.future.length) || historyVersion < 0}>
                {content.viewer.redoEdit}
              </button>
              {editStatus && <p className="upload-hint">{editStatus}</p>}
              {selectedProperties && (
                <div className="viewer-properties">
                  <label>{content.viewer.attributeLabel}
                    <input value={String(selectedProperties.label ?? "")} onChange={(event) => updateSelectedProperty("label", event.target.value)} />
                  </label>
                  <label>{content.viewer.attributeCode}
                    <input value={String(selectedProperties.code ?? "")} onChange={(event) => updateSelectedProperty("code", event.target.value)} />
                  </label>
                  <pre>{JSON.stringify(selectedProperties, null, 2)}</pre>
                </div>
              )}
            </div>
            <label>
              <input
                type="checkbox"
                checked={referenceVisible}
                onChange={(event) =>
                  updateLayer("reference", event.target.checked)
                }
              />{" "}
              {content.viewer.reference}
            </label>
            <input
              aria-label={content.viewer.referenceOpacity}
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={referenceOpacity}
              onChange={(event) =>
                updateOpacity("reference", Number(event.target.value))
              }
            />
            <label>
              <input
                type="checkbox"
                checked={rasterVisible}
                onChange={(event) =>
                  updateLayer("raster", event.target.checked)
                }
              />{" "}
              {content.viewer.raster}
            </label>
            <input
              aria-label={content.viewer.rasterOpacity}
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={rasterOpacity}
              onChange={(event) =>
                updateOpacity("raster", Number(event.target.value))
              }
            />
            <label>
              <input
                type="checkbox"
                checked={residualVisible}
                onChange={(event) =>
                  updateLayer("residual", event.target.checked)
                }
              />{" "}
              {content.viewer.residuals}
            </label>
            {discoveredLayers.map((layer) => (
              <div className="viewer-discovered-layer" key={layer.layer_id}>
                <label>
                  <input
                    type="checkbox"
                    defaultChecked
                    onChange={(event) => updateDiscoveredLayer(layer.layer_id, event.target.checked)}
                  />{" "}
                  {layer.code || layer.name || layer.layer_id} ({layer.geometry_type})
                </label>
                <input
                  aria-label={`${layer.code || layer.name} opacity`}
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  defaultValue="0.9"
                  onChange={(event) => updateDiscoveredOpacity(layer.layer_id, Number(event.target.value))}
                />
              </div>
            ))}
            <div className="viewer-coordinate">
              <span>{content.viewer.cursor}</span>
              <strong>
                {cursorCoordinate
                  ? `${cursorCoordinate[0].toFixed(2)} / ${cursorCoordinate[1].toFixed(2)}`
                  : "-- / --"}
              </strong>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
