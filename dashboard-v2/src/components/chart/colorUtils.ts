/** Ported verbatim from gui.js:45-66 -- parses an optionally-alpha hex color. */
export function parseHexColor(hex: string): { rgb: string; alpha: number; hex: string } {
  const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
  const fullHex = hex.replace(shorthandRegex, (_m, r, g, b) => r + r + g + g + b + b);
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})?$/i.exec(fullHex);
  if (!result) {
    return { rgb: '128, 128, 128', alpha: 1.0, hex: '#808080' };
  }
  const r = parseInt(result[1], 16);
  const g = parseInt(result[2], 16);
  const b = parseInt(result[3], 16);
  const alpha = result[4] !== undefined ? parseInt(result[4], 16) / 255 : 1.0;
  return { rgb: `${r}, ${g}, ${b}`, alpha, hex: `#${result[1]}${result[2]}${result[3]}` };
}

export function hexToRgbaStr(hex: string): string {
  const parsed = parseHexColor(hex);
  return `rgba(${parsed.rgb}, ${parsed.alpha})`;
}
