/** Canvas arrow icons for deck.gl IconLayer (points up = north at 0°). */

const ICON_SIZE = 64;

export type VesselIconKind = "moving" | "idle" | "selected";

const ICON_COLORS: Record<VesselIconKind, { fill: string; stroke: string }> = {
  moving: { fill: "#4ecdc4", stroke: "#0d2a28" },
  idle: { fill: "#e8a838", stroke: "#3a2a0d" },
  selected: { fill: "#f2f6fa", stroke: "#4ecdc4" },
};

let cachedAtlas: string | null = null;

function drawArrow(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  kind: VesselIconKind,
) {
  const { fill, stroke } = ICON_COLORS[kind];
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  ctx.moveTo(0, -22);
  ctx.lineTo(10, 14);
  ctx.lineTo(0, 8);
  ctx.lineTo(-10, 14);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();
}

export function getArrowIconAtlas(): string {
  if (cachedAtlas) return cachedAtlas;

  const canvas = document.createElement("canvas");
  canvas.width = ICON_SIZE * 3;
  canvas.height = ICON_SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawArrow(ctx, ICON_SIZE / 2, ICON_SIZE / 2, "moving");
  drawArrow(ctx, ICON_SIZE + ICON_SIZE / 2, ICON_SIZE / 2, "idle");
  drawArrow(ctx, ICON_SIZE * 2 + ICON_SIZE / 2, ICON_SIZE / 2, "selected");

  cachedAtlas = canvas.toDataURL();
  return cachedAtlas;
}

export const ARROW_ICON_MAPPING = {
  moving: { x: 0, y: 0, width: ICON_SIZE, height: ICON_SIZE, anchorY: ICON_SIZE / 2 },
  idle: { x: ICON_SIZE, y: 0, width: ICON_SIZE, height: ICON_SIZE, anchorY: ICON_SIZE / 2 },
  selected: {
    x: ICON_SIZE * 2,
    y: 0,
    width: ICON_SIZE,
    height: ICON_SIZE,
    anchorY: ICON_SIZE / 2,
  },
} as const;

export function vesselIconKind(
  sog?: number | null,
  selected?: boolean,
): VesselIconKind {
  if (selected) return "selected";
  if (sog != null && sog > 0.5) return "moving";
  return "idle";
}

/** AIS heading 511 = not available; prefer COG when moving. */
export function vesselHeadingDegrees(
  heading?: number | null,
  cog?: number | null,
  sog?: number | null,
): number {
  const moving = sog != null && sog > 0.5;
  const course = moving ? cog : heading ?? cog;
  if (course == null || course < 0 || course >= 360 || course === 511) {
    return 0;
  }
  return course;
}

/** deck.gl IconLayer rotates counter-clockwise; AIS heading is clockwise from north. */
export function iconAngleFromHeading(
  heading?: number | null,
  cog?: number | null,
  sog?: number | null,
): number {
  return -vesselHeadingDegrees(heading, cog, sog);
}

export function vesselIconSize(sog?: number | null, selected?: boolean): number {
  if (selected) return 28;
  if (sog != null && sog > 0.5) return 18 + Math.min(sog / 2, 8);
  return 14;
}
