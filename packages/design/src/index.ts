export const light = {
  primary: "#5144E8", primaryDeep: "#3C32C2", lavender: "#EFEDFF",
  background: "#F7F7F4", surface: "#FFFFFF", elevated: "#F0F1F5",
  text: "#171821", muted: "#686B79", border: "#E6E7ED",
  coral: "#FF725E", citrus: "#D9F36A", accentInk: "#171821", onPrimary: "#FFFFFF",
  success: "#187A58", warning: "#A86216", error: "#BC3549", info: "#2769C9",
} as const;

export const dark = {
  primary: "#A69CFF", primaryDeep: "#BEB7FF", lavender: "#252242",
  background: "#10111A", surface: "#1B1D29", elevated: "#242738",
  text: "#F4F3F0", muted: "#A5A7B7", border: "#323448",
  coral: "#FF9586", citrus: "#E0F67C", accentInk: "#171821", onPrimary: "#171821",
  success: "#68DBB2", warning: "#F8C27C", error: "#FF9DB1", info: "#8BBAFF",
} as const;

export type Palette = { [K in keyof typeof light]: string };
export const partnerMarkPaths = [
  "M6 13a7 7 0 0 1 7-7h6c3.9 0 7 3.1 7 7v4h-8v-3h-4v8H6z",
  "M26 19a7 7 0 0 1-7 7h-6a7 7 0 0 1-7-7v-4h8v3h4v-8h8z",
] as const;
