/** Crop rectangle shared between the Trim page and the crop selector. */

/**
 * A crop rectangle normalized against the source video dimensions.
 * All values are fractions in the range 0-1.
 */
export interface CropRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Rectangle covering the whole frame. */
export const FULL_FRAME_CROP: CropRect = { x: 0, y: 0, width: 1, height: 1 };

/** Minimum crop size in source pixels. Matches MIN_CROP_PIXELS in backend/app/core/crop_utils.py. */
export const MIN_CROP_PIXELS = 16;

/** Largest difference treated as "the same rectangle" when comparing normalized crops. */
const CROP_EPSILON = 1e-4;

/**
 * Compare two crop rectangles, tolerating floating point drift.
 *
 * @param a First rectangle, or null for "no crop"
 * @param b Second rectangle, or null for "no crop"
 * @returns True when both describe the same region
 */
export function cropsEqual(a: CropRect | null, b: CropRect | null): boolean {
  if (a === null || b === null) return a === b;
  return (
    Math.abs(a.x - b.x) < CROP_EPSILON &&
    Math.abs(a.y - b.y) < CROP_EPSILON &&
    Math.abs(a.width - b.width) < CROP_EPSILON &&
    Math.abs(a.height - b.height) < CROP_EPSILON
  );
}

/** Return true when the rectangle covers the entire frame. */
export function isFullFrameCrop(rect: CropRect): boolean {
  return cropsEqual(rect, FULL_FRAME_CROP);
}

/**
 * Clamp a rectangle into the frame, honouring the minimum crop size.
 *
 * @param rect Rectangle to clamp
 * @param sourceWidth Source video width in pixels
 * @param sourceHeight Source video height in pixels
 * @returns A rectangle fully inside 0-1 on both axes
 */
export function clampCrop(rect: CropRect, sourceWidth: number, sourceHeight: number): CropRect {
  const minWidth = sourceWidth > 0 ? Math.min(MIN_CROP_PIXELS / sourceWidth, 1) : 0;
  const minHeight = sourceHeight > 0 ? Math.min(MIN_CROP_PIXELS / sourceHeight, 1) : 0;
  const width = Math.min(Math.max(rect.width, minWidth), 1);
  const height = Math.min(Math.max(rect.height, minHeight), 1);
  return {
    x: Math.min(Math.max(rect.x, 0), 1 - width),
    y: Math.min(Math.max(rect.y, 0), 1 - height),
    width,
    height,
  };
}
