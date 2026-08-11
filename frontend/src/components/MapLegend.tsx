export function MapLegend() {
  return (
    <div className="map-legend" aria-label="Map key">
      <div className="map-legend__title">Map key</div>
      <ul className="map-legend__list">
        <li className="map-legend__item">
          <span className="map-legend__swatch map-legend__swatch--moving" aria-hidden />
          Ship underway
        </li>
        <li className="map-legend__item">
          <span className="map-legend__swatch map-legend__swatch--idle" aria-hidden />
          Ship stopped
        </li>
        <li className="map-legend__item">
          <span className="map-legend__swatch map-legend__swatch--sar" aria-hidden />
          Radar detection
        </li>
        <li className="map-legend__item">
          <span className="map-legend__swatch map-legend__swatch--cable" aria-hidden />
          Undersea cable
        </li>
        <li className="map-legend__item">
          <span className="map-legend__swatch map-legend__swatch--corridor" aria-hidden />
          Monitored area
        </li>
      </ul>
    </div>
  );
}
