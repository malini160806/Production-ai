/**
 * Validated default data-viz palette (see dataviz skill references/palette.md).
 * Categorical hues are assigned in this fixed order, never cycled or reassigned
 * when a filter changes which series are visible.
 */
export const CATEGORICAL: Array<{ light: string; dark: string }> = [
  { light: "#2a78d6", dark: "#3987e5" }, // blue
  { light: "#eb6834", dark: "#d95926" }, // orange
  { light: "#1baf7a", dark: "#199e70" }, // aqua
  { light: "#eda100", dark: "#c98500" }, // yellow
  { light: "#e87ba4", dark: "#d55181" }, // magenta
  { light: "#008300", dark: "#008300" }, // green
  { light: "#4a3aa7", dark: "#9085e9" }, // violet
  { light: "#e34948", dark: "#e66767" }, // red
];

// Fixed, mode-invariant status colors (never reused for categorical series).
export const STATUS = {
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
};

export const SEQUENTIAL_BLUE = [
  "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
  "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
];

export const CHROME = {
  surface: { light: "#fcfcfb", dark: "#1a1a19" },
  primaryInk: { light: "#0b0b0b", dark: "#ffffff" },
  secondaryInk: { light: "#52514e", dark: "#c3c2b7" },
  mutedInk: { light: "#898781", dark: "#898781" },
  gridline: { light: "#e1e0d9", dark: "#2c2c2a" },
  baseline: { light: "#c3c2b7", dark: "#383835" },
};

export function categoricalColor(index: number, theme: "light" | "dark"): string {
  const slot = CATEGORICAL[index % CATEGORICAL.length];
  return theme === "dark" ? slot.dark : slot.light;
}

export function chrome(role: keyof typeof CHROME, theme: "light" | "dark"): string {
  return CHROME[role][theme];
}
