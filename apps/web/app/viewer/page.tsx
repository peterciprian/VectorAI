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
import proj4 from "proj4";
import { register } from "ol/proj/proj4";
import { getTranslations, type Locale } from "../../lib/i18n";

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
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const rasterLayerRef = useRef<WebGLTileLayer | null>(null);
  const referenceLayerRef = useRef<TileLayer<OSM> | null>(null);
  const residualLayerRef = useRef<VectorLayer<VectorSource> | null>(null);
  const vectorLayerRefs = useRef<Record<string, VectorLayer<VectorSource>>>({});
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

  function updateDiscoveredLayer(layerId: string, visible: boolean) {
    vectorLayerRefs.current[layerId]?.setVisible(visible);
  }

  function updateDiscoveredOpacity(layerId: string, opacity: number) {
    vectorLayerRefs.current[layerId]?.setOpacity(opacity);
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
