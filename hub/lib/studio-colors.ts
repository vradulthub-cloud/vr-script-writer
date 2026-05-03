export const STUDIO_COLOR: Record<string, string> = {
  FuckPassVR: "var(--color-fpvr)",
  VRHush:     "var(--color-vrh)",
  VRAllure:   "var(--color-vra)",
  NaughtyJOI: "var(--color-njoi)",
}

export const STUDIO_ABBR: Record<string, string> = {
  FuckPassVR: "FPVR",
  VRHush:     "VRH",
  VRAllure:   "VRA",
  NaughtyJOI: "NJOI",
}

export function studioColor(studio: string): string {
  return STUDIO_COLOR[studio] ?? "var(--color-text-muted)"
}

export function studioAbbr(studio: string): string {
  return STUDIO_ABBR[studio] ?? studio
}
