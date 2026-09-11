"use client";

import "ol/ol.css";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import Feature from "ol/Feature";
import Point from "ol/geom/Point";
import LineString from "ol/geom/LineString";
import TileLayer from "ol/layer/Tile";
import BaseLayer from "ol/layer/Base";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import GeoJSON from "ol/format/GeoJSON";
import GeoTIFF from "ol/source/GeoTIFF";
import TileGrid from "ol/tilegrid/TileGrid";
import Projection from "ol/proj/Projection";
import { fromLonLat, toLonLat, transform } from "ol/proj";
import Style from "ol/style/Style";
import CircleStyle from "ol/style/Circle";
import Fill from "ol/style/Fill";
import Stroke from "ol/style/Stroke";
import proj4 from "proj4";
import { register } from "ol/proj/proj4";
import { getTranslations, type Locale } from "../../lib/i18n";

proj4.defs(
  "EPSG:23700",
  "+proj=krovak +lat_0=47.14439372222222 +lon_0=19.04857177777778 +alpha=90 +k=0.99993 +x_0=650000 +y_0=200000 +ellps=GRS67 +towgs84=52.17,-71.82,-14.9,0,0,0,0 +units=m +no_defs +type=crs",
);
register(proj4);

const defaultLocale: Locale = "en";
const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Gcp = {
  id: string;
  pixel_x: number;
  pixel_y: number;
  map_x: number;
  map_y: number;
};

type IngestionMetadata = {
  width: number;
  height: number;
  deepzoom_levels: number;
  thumbnail: string;
};

type Residual = {
  id: string;
  residual_m: number;
  actual_map_x?: number;
  actual_map_y?: number;
  predicted_map_x?: number;
  predicted_map_y?: number;
};

export default function GeorefPage() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const [projectId, setProjectId] = useState("");
  const [metadata, setMetadata] = useState<IngestionMetadata | null>(null);
  const [gcps, setGcps] = useState<Gcp[]>([]);
  const [pendingPixel, setPendingPixel] = useState<[number, number] | null>(
    null,
  );
  const [referenceLayerVisible, setReferenceLayerVisible] = useState(false);
  const [referenceLayerName, setReferenceLayerName] = useState("");
  const pendingPixelRef = useRef<[number, number] | null>(null);
  const planMapRef = useRef<OlMap | null>(null);
  const referenceMapRef = useRef<OlMap | null>(null);
  const referenceLayerRef = useRef<BaseLayer | null>(null);
  const residualSourceRef = useRef<VectorSource | null>(null);
  const gcpCountRef = useRef(0);
  const planElement = useRef<HTMLDivElement>(null);
  const referenceElement = useRef<HTMLDivElement>(null);
  const [georefStatus, setGeorefStatus] = useState<
    "idle" | "queued" | "completed" | "error"
  >("idle");
  const [rmse, setRmse] = useState<number | null>(null);
  const [residuals, setResiduals] = useState<Residual[]>([]);
  const [transformMethod, setTransformMethod] = useState("auto");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [jobProgress, setJobProgress] = useState<{ stage: string; progress_percent: number } | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const content = getTranslations(locale);

  useEffect(() => {
    gcpCountRef.current = gcps.length;
  }, [gcps.length]);

  useEffect(() => {
    if (!projectId) return;
    const events = new EventSource(`${apiBase}/api/v1/projects/${projectId}/events`);
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { status: string; stage: string; progress_percent: number };
      setJobProgress({ stage: event.stage, progress_percent: event.progress_percent });
      if (event.status === "completed" && event.stage === "georeferencing") setGeorefStatus("completed");
      if (event.status === "failed" && event.stage === "georeferencing") setGeorefStatus("error");
    };
    events.onerror = () => undefined;
    return () => events.close();
  }, [projectId]);

  useEffect(() => {
    const savedLocale = window.localStorage.getItem("vectoryai-locale");
    if (savedLocale === "en" || savedLocale === "hu") setLocale(savedLocale);
    setProjectId(
      new URLSearchParams(window.location.search).get("project") || "",
    );
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetch(`${apiBase}/api/v1/projects/${projectId}/ingestion`)
      .then((response) => response.json())
      .then((result) => setMetadata(result.metadata))
      .catch(() => setGeorefStatus("error"));
    fetch(`${apiBase}/api/v1/projects/${projectId}/georef/status`)
      .then((response) => response.json())
      .then((result) => {
        if (result.status === "completed") {
          setRmse(result.rmse_m);
          setResiduals(result.residuals || []);
          setWarnings(result.warnings || []);
          setGeorefStatus("completed");
        }
      })
      .catch(() => undefined);
  }, [projectId]);

  useEffect(() => {
    if (!residualSourceRef.current || residuals.length === 0) return;
    residualSourceRef.current.clear();
    residuals.forEach(
      (residual: {
        actual_map_x?: number;
        actual_map_y?: number;
        predicted_map_x?: number;
        predicted_map_y?: number;
      }) => {
        if (
          residual.actual_map_x === undefined ||
          residual.actual_map_y === undefined ||
          residual.predicted_map_x === undefined ||
          residual.predicted_map_y === undefined
        )
          return;
        residualSourceRef.current?.addFeature(
          new Feature(
            new LineString([
              transform(
                [residual.actual_map_x, residual.actual_map_y],
                "EPSG:23700",
                "EPSG:3857",
              ),
              transform(
                [residual.predicted_map_x, residual.predicted_map_y],
                "EPSG:23700",
                "EPSG:3857",
              ),
            ]),
          ),
        );
      },
    );
  }, [residuals, metadata]);

  useEffect(() => {
    if (!metadata || !planElement.current || !referenceElement.current) return;
    const planProjection = new Projection({
      code: "PIXELS",
      units: "pixels",
      extent: [0, 0, metadata.width, metadata.height],
    });
    const planSource = new VectorSource();
    const referenceSource = new VectorSource();
    const residualSource = new VectorSource();
    const pointStyle = new Style({
      image: new CircleStyle({
        radius: 6,
        fill: new Fill({ color: "#e36d50" }),
        stroke: new Stroke({ color: "#f2f0e8", width: 2 }),
      }),
    });
    const planMap = new OlMap({
      target: planElement.current,
      layers: [
        new TileLayer({
          source: new XYZ({
            tileGrid: new TileGrid({
              extent: [0, 0, metadata.width, metadata.height],
              origin: [0, metadata.height],
              tileSize: 512,
              resolutions: Array.from(
                { length: Math.max(metadata.deepzoom_levels, 1) },
                (_, zoom) =>
                  Math.max(metadata.width, metadata.height) / 512 / 2 ** zoom,
              ),
            }),
            tileUrlFunction: (tileCoordinate) => {
              if (!tileCoordinate) return "";
              const level = metadata.deepzoom_levels - 1 - tileCoordinate[0];
              return `${apiBase}/api/v1/projects/${projectId}/deepzoom/${level}/${tileCoordinate[1]}_${tileCoordinate[2]}.jpg`;
            },
          }),
        }),
        new VectorLayer({ source: planSource, style: pointStyle }),
      ],
      view: new View({
        projection: planProjection,
        center: [metadata.width / 2, metadata.height / 2],
        zoom: 1,
        extent: [0, 0, metadata.width, metadata.height],
      }),
    });
    const referenceMap = new OlMap({
      target: referenceElement.current,
      layers: [
        new TileLayer({ source: new OSM() }),
        new VectorLayer({ source: referenceSource, style: pointStyle }),
        new VectorLayer({
          source: residualSource,
          style: new Style({
            stroke: new Stroke({ color: "#d7f26c", width: 3 }),
          }),
        }),
      ],
      view: new View({ center: fromLonLat([19.05, 47.5]), zoom: 7 }),
    });
    planMapRef.current = planMap;
    referenceMapRef.current = referenceMap;
    residualSourceRef.current = residualSource;
    return () => {
      planMap.setTarget(undefined);
      referenceMap.setTarget(undefined);
      planMapRef.current = null;
      referenceMapRef.current = null;
      referenceLayerRef.current = null;
      residualSourceRef.current = null;
    };
  }, [metadata, projectId]);

  useEffect(() => {
    if (georefStatus !== "queued" || !projectId) return;
    const interval = window.setInterval(() => {
      fetch(`${apiBase}/api/v1/projects/${projectId}/georef/status`)
        .then((response) => response.json())
        .then((result) => {
          if (result.status === "completed") {
            setRmse(result.rmse_m);
            setResiduals(result.residuals || []);
            setWarnings(result.warnings || []);
            residualSourceRef.current?.clear();
            result.residuals?.forEach(
              (residual: {
                actual_map_x: number;
                actual_map_y: number;
                predicted_map_x: number;
                predicted_map_y: number;
              }) => {
                residualSourceRef.current?.addFeature(
                  new Feature(
                    new LineString([
                      transform(
                        [residual.actual_map_x, residual.actual_map_y],
                        "EPSG:23700",
                        "EPSG:3857",
                      ),
                      transform(
                        [residual.predicted_map_x, residual.predicted_map_y],
                        "EPSG:23700",
                        "EPSG:3857",
                      ),
                    ]),
                  ),
                );
              },
            );
            setGeorefStatus("completed");
          }
        })
        .catch(() => setGeorefStatus("error"));
    }, 1500);
    return () => window.clearInterval(interval);
  }, [georefStatus, projectId]);

  function updateGcp(index: number, field: "map_x" | "map_y", value: number) {
    setGcps((current) =>
      current.map((gcp, currentIndex) =>
        currentIndex === index ? { ...gcp, [field]: value } : gcp,
      ),
    );
  }

  function submitGeoreferencing() {
    if (gcps.length < 3 || !projectId) return;
    fetch(`${apiBase}/api/v1/projects/${projectId}/georef`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transform_method: transformMethod,
        target_crs: "EPSG:23700",
        points: gcps,
      }),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Georeferencing request failed");
        const result = (await response.json()) as { job_id: string };
        setJobId(result.job_id);
        setConfirmSubmit(false);
        setJobProgress({ stage: "queued", progress_percent: 0 });
        setGeorefStatus("queued");
      })
      .catch(() => setGeorefStatus("error"));
  }

  async function cancelJob() {
    if (!jobId) return;
    const response = await fetch(`${apiBase}/api/v1/jobs/${jobId}/cancel`, { method: "POST" });
    if (response.ok) setGeorefStatus("error");
  }

  async function retryJob() {
    if (!jobId) return;
    const response = await fetch(`${apiBase}/api/v1/jobs/${jobId}/retry`, { method: "POST" });
    if (!response.ok) return;
    setJobProgress({ stage: "queued", progress_percent: 0 });
    setGeorefStatus("queued");
  }

  async function handleReferenceUpload(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    if (!file || !projectId || !referenceMapRef.current) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("crs", "EPSG:23700");
    const response = await fetch(
      `${apiBase}/api/v1/projects/${projectId}/georef/reference`,
      { method: "POST", body: formData },
    );
    if (!response.ok) return;
    const result = (await response.json()) as {
      reference_id: string;
      filename: string;
      format: string;
      url: string;
    };
    const referenceLayer =
      result.format === "tif" || result.format === "tiff"
        ? new TileLayer({
            source: new GeoTIFF({
              sources: [{ url: `${apiBase}${result.url}` }],
              projection: "EPSG:23700",
            }),
          })
        : new VectorLayer({
            source: new VectorSource({
              features: new GeoJSON().readFeatures(
                await fetch(`${apiBase}${result.url}`).then(
                  (referenceResponse) => referenceResponse.json(),
                ),
                {
                  dataProjection: "EPSG:23700",
                  featureProjection: "EPSG:3857",
                },
              ),
            }),
            style: new Style({
              stroke: new Stroke({ color: "#e36d50", width: 3 }),
              fill: new Fill({ color: "rgba(227, 109, 80, 0.12)" }),
            }),
          });
    referenceMapRef.current.addLayer(referenceLayer);
    referenceLayerRef.current = referenceLayer;
    setReferenceLayerName(result.filename);
    setReferenceLayerVisible(true);
  }

  function toggleReferenceLayer(visible: boolean) {
    setReferenceLayerVisible(visible);
    referenceLayerRef.current?.setVisible(visible);
  }

  function handlePlanClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!planMapRef.current || !metadata) return;
    const pixelFromMap = planMapRef.current.getCoordinateFromPixel(
      planMapRef.current.getEventPixel(event.nativeEvent),
    );
    const bounds = event.currentTarget.getBoundingClientRect();
    const pixelCoordinate = pixelFromMap ?? [
      ((event.clientX - bounds.left) / bounds.width) * metadata.width,
      ((event.clientY - bounds.top) / bounds.height) * metadata.height,
    ];
    const pixel: [number, number] = [pixelCoordinate[0], pixelCoordinate[1]];
    pendingPixelRef.current = pixel;
    setPendingPixel(pixel);
  }

  function handleReferenceClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!referenceMapRef.current || !pendingPixelRef.current) return;
    const coordinateFromMap = referenceMapRef.current.getCoordinateFromPixel(
      referenceMapRef.current.getEventPixel(event.nativeEvent),
    );
    const bounds = event.currentTarget.getBoundingClientRect();
    const coordinate =
      coordinateFromMap ??
      referenceMapRef.current.getCoordinateFromPixel([
        event.clientX - bounds.left,
        event.clientY - bounds.top,
      ]) ??
      referenceMapRef.current.getView().getCenter();
    if (!coordinate) return;
    const [longitude, latitude] = toLonLat(coordinate);
    const [mapX, mapY] = transform(
      [longitude, latitude],
      "EPSG:4326",
      "EPSG:23700",
    );
    const pixel = pendingPixelRef.current;
    const id = `gcp_${gcpCountRef.current + 1}`;
    setGcps((current) => [
      ...current,
      { id, pixel_x: pixel[0], pixel_y: pixel[1], map_x: mapX, map_y: mapY },
    ]);
    pendingPixelRef.current = null;
    setPendingPixel(null);
  }

  return (
    <main className="georef-page">
      <nav className="nav shell-width" aria-label={content.navigation.main}>
        <Link className="brand" href="/">
          <span className="brand-mark">V</span> VectoryAI
        </Link>
        <div className="nav-links">
          <Link className="back-link" href="/upload">
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
      <section className="georef-shell shell-width">
        <div className="georef-heading">
          <p className="eyebrow">
            <span className="eyebrow-dot" /> {content.upload.label}
          </p>
          <h1>
            {content.upload.georefTitle}
            <br />
            <em>{content.upload.georefTitleEmphasis}</em>
          </h1>
          <p className="lede">{content.upload.georefIntro}</p>
        </div>
        {!metadata && (
          <p className="upload-error">
            {projectId
              ? content.upload.apiUnavailable
              : content.upload.georefError}
          </p>
        )}
        {metadata && (
          <>
            <div className="map-panes">
              <div>
                <p className="section-kicker">{content.upload.planPane}</p>
                <div
                  ref={planElement}
                  className="map-pane"
                  onClick={handlePlanClick}
                />
              </div>
              <div>
                <p className="section-kicker">{content.upload.referencePane}</p>
                <div
                  ref={referenceElement}
                  className="map-pane"
                  onClick={handleReferenceClick}
                />
                <label className="reference-upload">
                  <span>
                    {referenceLayerName || content.upload.referenceUpload}
                  </span>
                  <input
                    type="file"
                    accept=".geojson,.json,.tif,.tiff"
                    onChange={handleReferenceUpload}
                  />
                </label>
                {referenceLayerName && (
                  <label className="reference-toggle">
                    <input
                      type="checkbox"
                      checked={referenceLayerVisible}
                      onChange={(event) =>
                        toggleReferenceLayer(event.target.checked)
                      }
                    />{" "}
                    {content.upload.referenceToggle}
                  </label>
                )}
                <p className="upload-hint">{content.upload.referenceFormat}</p>
              </div>
            </div>
            <p className="upload-hint">
              {pendingPixel
                ? `${content.upload.gcps}: ${Math.round(pendingPixel[0])}, ${Math.round(pendingPixel[1])}`
                : content.upload.introHint}
            </p>
            <section className="gcp-panel">
              <h2>{content.upload.gcps}</h2>
              <label className="method-picker">
                {content.upload.method}
                <select
                  value={transformMethod}
                  onChange={(event) => setTransformMethod(event.target.value)}
                >
                  <option value="auto">{content.upload.methodAuto}</option>
                  <option value="affine">{content.upload.methodAffine}</option>
                  <option value="polynomial">
                    {content.upload.methodPolynomial}
                  </option>
                  <option value="tps">{content.upload.methodTps}</option>
                </select>
              </label>
              {gcps.length === 0 && (
                <p className="upload-hint">{content.upload.emptyGcps}</p>
              )}
              {gcps.map((gcp, index) => (
                <div className="gcp-row" key={gcp.id}>
                  <span>{gcp.id}</span>
                  <input
                    aria-label={`${content.upload.easting} ${gcp.id}`}
                    type="number"
                    value={gcp.map_x}
                    onChange={(event) =>
                      updateGcp(index, "map_x", Number(event.target.value))
                    }
                  />
                  <input
                    aria-label={`${content.upload.northing} ${gcp.id}`}
                    type="number"
                    value={gcp.map_y}
                    onChange={(event) =>
                      updateGcp(index, "map_y", Number(event.target.value))
                    }
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setGcps((current) =>
                        current.filter(
                          (_, currentIndex) => currentIndex !== index,
                        ),
                      )
                    }
                  >
                    {content.upload.remove}
                  </button>
                </div>
              ))}
              {residuals.length > 0 && (
                <div className="residual-list">
                  {residuals.map((residual) => (
                    <span key={residual.id}>
                      {residual.id}: {residual.residual_m.toFixed(3)} m
                    </span>
                  ))}
                </div>
              )}
            </section>
            <div className="georef-actions">
              <button
                className="button button-primary"
                type="button"
                disabled={gcps.length < 3 || georefStatus === "queued"}
                onClick={() => setConfirmSubmit(true)}
              >
                {content.upload.submitGeoref}{" "}
                <span aria-hidden="true">&#8599;</span>
              </button>
              {georefStatus === "queued" && (
                <span className="upload-hint">
                  {content.upload.georefQueued} {jobProgress ? `(${jobProgress.stage} ${Math.round(jobProgress.progress_percent)}%)` : ""}
                  <button className="secondary-button" type="button" onClick={cancelJob}>{content.upload.cancelJob}</button>
                </span>
              )}
              {georefStatus === "completed" && (
                <span className="upload-success">
                  {content.upload.georefComplete}: {content.upload.rmse}{" "}
                  {rmse?.toFixed(3)} m <br />
                  <Link
                    className="upload-next-link"
                    href={`/viewer?project=${projectId}`}
                  >
                    {content.upload.openViewer} &#8599;
                  </Link>
                </span>
              )}
              {georefStatus === "error" && (
                <span className="upload-error">
                  {content.upload.georefError}
                  {jobId && <button className="secondary-button" type="button" onClick={retryJob}>{content.upload.retryJob}</button>}
                </span>
              )}
            </div>
            {warnings.length > 0 && (
              <div className="georef-warnings">
                <strong>{content.upload.warnings}</strong>
                {warnings.map((warning) => (
                  <span key={warning}>{warning}</span>
                ))}
              </div>
            )}
            {confirmSubmit && (
              <div className="georef-confirm">
                <strong>{content.upload.confirmGeoref}</strong>
                <p>{content.upload.confirmGeorefText}</p>
                <div>
                  <button
                    className="button button-primary"
                    type="button"
                    onClick={submitGeoreferencing}
                  >
                    {content.upload.confirm}
                  </button>
                  <button
                    className="text-link"
                    type="button"
                    onClick={() => setConfirmSubmit(false)}
                  >
                    {content.upload.cancel}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
