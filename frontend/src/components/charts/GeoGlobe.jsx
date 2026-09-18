import { useEffect, useRef, useMemo } from "react";

const CENTROIDS = {
  AF: [33.94, 67.71],  AL: [41.15, 20.17],  DZ: [28.03, 1.66],
  AO: [-11.20, 17.87], AR: [-38.42, -63.62], AM: [40.07, 45.04],
  AU: [-25.27, 133.78], AT: [47.52, 14.55],  AZ: [40.14, 47.58],
  BH: [26.00, 50.55],  BD: [23.68, 90.36],   BY: [53.71, 27.95],
  BE: [50.83, 4.47],   BZ: [17.19, -88.50],  BJ: [9.31, 2.32],
  BT: [27.51, 90.43],  BO: [-16.29, -63.59], BA: [43.92, 17.68],
  BW: [-22.33, 24.68], BR: [-14.24, -51.93], BN: [4.54, 114.73],
  BG: [42.73, 25.49],  BF: [12.36, -1.56],   BI: [-3.37, 29.92],
  KH: [12.57, 104.99], CM: [7.37, 12.35],    CA: [56.13, -106.35],
  CF: [6.61, 20.94],   TD: [15.45, 18.73],   CL: [-35.68, -71.54],
  CN: [35.86, 104.20], CO: [4.57, -74.30],   CD: [-4.04, 21.76],
  CG: [-0.23, 15.83],  CR: [9.75, -83.75],   HR: [45.10, 15.20],
  CU: [21.52, -77.78], CY: [35.13, 33.43],   CZ: [49.82, 15.47],
  DK: [56.26, 9.50],   DJ: [11.83, 42.59],   DO: [18.74, -70.16],
  EC: [-1.83, -78.18], EG: [26.82, 30.80],   SV: [13.79, -88.90],
  GQ: [1.65, 10.27],   ER: [15.18, 39.78],   EE: [58.60, 25.01],
  ET: [9.15, 40.49],   FI: [61.92, 25.75],   FR: [46.23, 2.21],
  GA: [-0.80, 11.61],  GM: [13.44, -15.31],  GE: [42.32, 43.36],
  DE: [51.17, 10.45],  GH: [7.95, -1.02],    GR: [39.07, 21.82],
  GT: [15.78, -90.23], GN: [9.95, -11.82],   GW: [11.80, -15.18],
  GY: [4.86, -58.93],  HT: [18.97, -72.29],  HN: [15.20, -86.24],
  HU: [47.16, 19.50],  IS: [64.96, -19.02],  IN: [20.59, 78.96],
  ID: [-0.79, 113.92], IR: [32.43, 53.69],   IQ: [33.22, 43.68],
  IE: [53.41, -8.24],  IL: [31.05, 34.85],   IT: [41.87, 12.57],
  JM: [18.11, -77.30], JP: [36.20, 138.25],  JO: [30.59, 36.24],
  KZ: [48.02, 66.92],  KE: [-0.02, 37.91],   KP: [40.34, 127.51],
  KR: [35.91, 127.77], KW: [29.31, 47.48],   KG: [41.20, 74.77],
  LA: [19.86, 102.50], LV: [56.88, 24.60],   LB: [33.89, 35.50],
  LS: [-29.61, 28.23], LR: [6.43, -9.43],    LY: [26.34, 17.23],
  LT: [55.17, 23.88],  LU: [49.82, 6.13],    MK: [41.61, 21.75],
  MG: [-18.77, 46.87], MW: [-13.25, 34.30],  MY: [4.21, 101.98],
  MV: [3.20, 73.22],   ML: [17.57, -3.99],   MT: [35.94, 14.37],
  MR: [21.01, -10.94], MX: [23.63, -102.55], MD: [47.41, 28.37],
  MN: [46.86, 103.85], ME: [42.71, 19.37],   MA: [31.79, -7.09],
  MZ: [-18.67, 35.53], NA: [-22.96, 18.49],  NP: [28.39, 84.12],
  NL: [52.13, 5.29],   NZ: [-40.90, 174.89], NI: [12.87, -85.21],
  NE: [17.61, 8.08],   NG: [9.08, 8.68],     NO: [60.47, 8.47],
  OM: [21.51, 55.92],  PK: [30.38, 69.35],   PA: [8.54, -80.78],
  PG: [-6.31, 143.96], PY: [-23.44, -58.44], PE: [-9.19, -75.02],
  PH: [12.88, 121.77], PL: [51.92, 19.15],   PT: [39.40, -8.22],
  QA: [25.35, 51.18],  RO: [45.94, 24.97],   RU: [61.52, 105.32],
  RW: [-1.94, 29.87],  SA: [23.89, 45.08],   SN: [14.50, -14.45],
  RS: [44.02, 21.01],  SC: [-4.68, 55.49],   SL: [8.46, -11.78],
  SG: [1.35, 103.82],  SK: [48.67, 19.70],   SI: [46.15, 14.99],
  SO: [5.15, 46.20],   ZA: [-30.56, 22.94],  SS: [6.88, 31.31],
  ES: [40.46, -3.75],  LK: [7.87, 80.77],    SD: [12.86, 30.22],
  SR: [3.92, -56.03],  SZ: [-26.52, 31.47],  SE: [60.13, 18.64],
  CH: [46.82, 8.23],   SY: [34.80, 38.99],   TW: [23.70, 120.96],
  TJ: [38.86, 71.28],  TZ: [-6.37, 34.89],   TH: [15.87, 100.99],
  TL: [-8.87, 125.73], TG: [8.62, 0.82],     TT: [10.69, -61.22],
  TN: [33.89, 9.54],   TR: [38.96, 35.24],   TM: [38.97, 59.56],
  UG: [1.37, 32.29],   UA: [48.38, 31.17],   AE: [23.42, 53.85],
  GB: [55.38, -3.44],  US: [37.09, -95.71],  UY: [-32.52, -55.77],
  UZ: [41.38, 64.59],  VE: [6.42, -66.59],   VN: [14.06, 108.28],
  YE: [15.55, 48.52],  ZM: [-13.13, 27.85],  ZW: [-20.02, 29.15],
  HK: [22.40, 114.11], PS: [31.95, 35.23],   XK: [42.60, 20.90],
  MO: [22.19, 113.55], PR: [18.22, -66.59],  CW: [12.17, -68.99],
};

function buildScene(data) {
  if (!data.length) return { points: [], arcs: [], rings: [] };

  const maxV = Math.max(...data.map((d) => d.visitors), 1);

  const mapped = data
    .filter((d) => CENTROIDS[d.country])
    .map((d) => {
      const [lat, lng] = CENTROIDS[d.country];
      const norm = d.visitors / maxV;
      return { lat, lng, norm, country: d.country, visitors: d.visitors };
    })
    .sort((a, b) => b.visitors - a.visitors);

  const points = mapped.map((d) => ({
    lat: d.lat,
    lng: d.lng,
    size: 0.25 + d.norm * 1.6,
    color: `rgba(${Math.round(96 + d.norm * 64)}, ${Math.round(165 + d.norm * 80)}, 250, ${0.55 + d.norm * 0.45})`,
    label: `${d.country}: ${d.visitors.toLocaleString()} visitors`,
  }));

  // Hub-and-spoke arcs from the top country to the next top 7
  const arcs = [];
  if (mapped.length >= 2) {
    const hub = mapped[0];
    mapped.slice(1, Math.min(8, mapped.length)).forEach((dst) => {
      arcs.push({
        startLat: hub.lat, startLng: hub.lng,
        endLat: dst.lat,   endLng: dst.lng,
        color: [
          "rgba(96,165,250,0)",
          "rgba(96,165,250,0.7)",
          "rgba(147,197,253,0.9)",
          "rgba(96,165,250,0.7)",
          "rgba(96,165,250,0)",
        ],
      });
    });
  }

  // Pulsing rings on the top 4 countries
  const rings = mapped.slice(0, 4).map((d, i) => ({
    lat: d.lat, lng: d.lng,
    maxR: 3.5 + d.norm * 1.5,
    propagationSpeed: 1.8 - i * 0.15,
    repeatPeriod: 900 + i * 200,
    color: (t) => `rgba(147,197,253,${(1 - t) * 0.8})`,
  }));

  return { points, arcs, rings };
}

export default function GeoGlobe({ data = [] }) {
  const containerRef = useRef(null);
  const globeRef = useRef(null);

  const scene = useMemo(() => buildScene(data), [data]);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;
    import("react-globe.gl").then((mod) => {
      if (cancelled || !containerRef.current) return;

      globeRef.current?._destructor?.();

      const globe = mod.default()(containerRef.current);
      globeRef.current = globe;

      globe
        .width(containerRef.current.offsetWidth)
        .height(containerRef.current.offsetHeight)
        .backgroundColor("rgba(0,0,0,0)")
        .globeImageUrl("//unpkg.com/three-globe/example/img/earth-night.jpg")
        .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
        .showAtmosphere(true)
        .atmosphereColor("#1a3f7a")
        .atmosphereAltitude(0.18)
        // Points
        .pointsData(scene.points)
        .pointLat("lat").pointLng("lng")
        .pointColor("color").pointRadius("size")
        .pointAltitude(0.01).pointLabel("label")
        // Arcs
        .arcsData(scene.arcs)
        .arcStartLat("startLat").arcStartLng("startLng")
        .arcEndLat("endLat").arcEndLng("endLng")
        .arcColor("color")
        .arcDashLength(0.35).arcDashGap(0.12)
        .arcDashAnimateTime(2400)
        .arcStroke(0.45)
        // Rings
        .ringsData(scene.rings)
        .ringLat("lat").ringLng("lng")
        .ringMaxRadius("maxR")
        .ringPropagationSpeed("propagationSpeed")
        .ringRepeatPeriod("repeatPeriod")
        .ringColor("color")
        .onGlobeReady(() => {
          globe.controls().autoRotate = true;
          globe.controls().autoRotateSpeed = 0.3;
          globe.controls().enableZoom = false;
          globe.pointOfView({ altitude: 2.4 });
        });
    });

    return () => {
      cancelled = true;
      globeRef.current?._destructor?.();
      globeRef.current = null;
    };
  }, []);

  // Reactively push data updates without recreating the globe
  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    g.pointsData(scene.points)
      .arcsData(scene.arcs)
      .ringsData(scene.rings);
  }, [scene]);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden glow">
      <div className="px-5 pt-4 pb-2">
        <p className="text-sm font-medium text-slate-300">Global Traffic</p>
        <p className="text-xs text-slate-500">Visitor origins — arcs show top traffic flows</p>
      </div>
      {data.length === 0 ? (
        <div className="flex items-center justify-center" style={{ height: 400 }}>
          <p className="text-slate-500 text-sm">No geographic data yet</p>
        </div>
      ) : (
        <div ref={containerRef} style={{ width: "100%", height: 400 }} />
      )}
    </div>
  );
}
