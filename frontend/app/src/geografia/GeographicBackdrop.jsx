import { useMemo } from 'react';
import { geographicPaths } from './geography.js';

export default function GeographicBackdrop({ geography, layerRef }) {
  const countries = useMemo(() => geographicPaths(geography), [geography]);
  return <svg className="sdn-geographic-backdrop" aria-hidden="true">
    <g ref={layerRef}>{countries.map(country => <path key={country.name} d={country.path} />)}</g>
  </svg>;
}
