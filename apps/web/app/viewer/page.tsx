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
import Projection from "ol/proj/Projection";
import { transform } from "ol/proj";
import Style from "ol/style/Style";
import Stroke from "ol/style/Stroke";
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
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const rasterLayerRef = useRef<WebGLTileLayer | null>(null);
  const referenceLayerRef = useRef<TileLayer<OSM> | null>(null);
  const residualLayerRef = useRef<VectorLayer<VectorSource> | null>(null);
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
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
    return () => {
      disposed = true;
      mapRef.current?.setTarget(undefined);
      mapRef.current = null;
    };
  }, [projectId]);

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
