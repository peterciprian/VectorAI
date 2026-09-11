import TileLayer from "ol/layer/Tile";
import WMTS, { optionsFromCapabilities } from "ol/source/WMTS";
import WMTSCapabilities from "ol/format/WMTSCapabilities";
import type TileSource from "ol/source/Tile";

type WmtsConfig = {
  enabled: boolean;
  url: string | null;
  layer: string;
  matrix_set: string;
  style: string;
  format: string;
};

// Requests are routed through the API proxy so WMTS credentials never reach the browser.
function toProxyUrl(apiBase: string, upstreamUrl: string): string {
  const queryIndex = upstreamUrl.indexOf("?");
  const query = queryIndex >= 0 ? upstreamUrl.slice(queryIndex) : "";
  return `${apiBase}/api/v1/basemap/wmts${query}`;
}

/** Swaps the given base layer's source to the configured WMTS service, falling back to the existing (e.g. OSM) source on any failure. */
export async function applyWmtsBaseLayer(
  layer: TileLayer<TileSource>,
  apiBase: string,
): Promise<void> {
  const fallbackSource = layer.getSource();
  try {
    const configResponse = await fetch(`${apiBase}/api/v1/basemap/wmts/config`);
    if (!configResponse.ok) return;
    const config = (await configResponse.json()) as WmtsConfig;
    if (!config.enabled || !config.url) return;

    const capabilitiesResponse = await fetch(
      `${apiBase}${config.url}?service=WMTS&request=GetCapabilities&version=1.0.0`,
    );
    if (!capabilitiesResponse.ok) return;
    const capabilities = new WMTSCapabilities().read(
      await capabilitiesResponse.text(),
    );
    const availableLayers: { Identifier: string }[] =
      capabilities?.Contents?.Layer || [];
    const layerIdentifier = config.layer || availableLayers[0]?.Identifier;
    if (!layerIdentifier) return;

    const options = optionsFromCapabilities(capabilities, {
      layer: layerIdentifier,
      matrixSet: config.matrix_set || undefined,
      style: config.style || undefined,
      format: config.format || undefined,
    });
    if (!options) return;
    options.urls = (options.urls || []).map((url) => toProxyUrl(apiBase, url));

    const wmtsSource = new WMTS(options);
    // Tiles are requested lazily, so failures (e.g. rejected credentials) only surface after
    // setSource; revert to the original fallback source once a few tiles fail in a row.
    let consecutiveErrors = 0;
    let revertedToFallback = false;
    wmtsSource.on("tileloaderror", () => {
      consecutiveErrors += 1;
      if (!revertedToFallback && consecutiveErrors >= 3 && fallbackSource) {
        revertedToFallback = true;
        layer.setSource(fallbackSource);
      }
    });
    wmtsSource.on("tileloadend", () => {
      consecutiveErrors = 0;
    });

    layer.setSource(wmtsSource);
  } catch {
    // Keep the fallback source (e.g. OSM) on any error.
  }
}
