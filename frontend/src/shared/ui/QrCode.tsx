import QRCode from "qrcode";
import { useMemo } from "react";

const QUIET_ZONE = 4; // modules of white margin required around a QR code

/** The modules of a QR code (true = dark), built locally: the link never leaves the browser. */
export function qrModules(text: string): boolean[][] {
  const { modules } = QRCode.create(text, { errorCorrectionLevel: "M" });
  const rows: boolean[][] = [];
  for (let y = 0; y < modules.size; y += 1) {
    const row: boolean[] = [];
    for (let x = 0; x < modules.size; x += 1) row.push(modules.get(x, y) === 1);
    rows.push(row);
  }
  return rows;
}

/** A standalone SVG document of the QR code, for download (black on white, any size). */
export function qrSvgDocument(text: string): string {
  const rows = qrModules(text);
  const size = rows.length + QUIET_ZONE * 2;
  const path = rows
    .flatMap((row, y) =>
      row.map((dark, x) => (dark ? `M${x + QUIET_ZONE} ${y + QUIET_ZONE}h1v1h-1z` : "")),
    )
    .join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" ` +
    `shape-rendering="crispEdges"><rect width="${size}" height="${size}" fill="#fff"/>` +
    `<path d="${path}" fill="#000"/></svg>`
  );
}

/** Rendered with React elements only (no innerHTML): compatible with the strict CSP. */
export function QrCode({
  text,
  label,
  className,
}: {
  text: string;
  label: string;
  className?: string | undefined;
}) {
  const rows = useMemo(() => qrModules(text), [text]);
  const size = rows.length + QUIET_ZONE * 2;
  const path = rows
    .flatMap((row, y) =>
      row.map((dark, x) => (dark ? `M${x + QUIET_ZONE} ${y + QUIET_ZONE}h1v1h-1z` : "")),
    )
    .join("");
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${size} ${size}`}
      shapeRendering="crispEdges"
      className={className}
    >
      <rect width={size} height={size} fill="#fff" />
      <path d={path} fill="#000" />
    </svg>
  );
}
