import type { SVGProps } from "react";

export type IconName = "overview" | "data" | "scenario" | "compare" | "activity" |
  "pin" | "arrow" | "grid" | "site" | "clock" | "check" | "report" | "database" | "studio";

const paths: Record<IconName, string> = {
  studio: "M4 20V9l7-5 9 5v11M4 9l7 5 9-5M11 14v6M8 17h.01M16 17h.01",
  overview: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z",
  data: "m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5",
  scenario: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6",
  compare: "M4 19V5m0 14h16M8 15v-4m5 4V6m5 9V9",
  activity: "M3 12h4l3-7 4 14 3-7h4",
  pin: "M19 10c0 5-7 10-7 10S5 15 5 10a7 7 0 1 1 14 0ZM12 10h.01",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  site: "M8 3h8v5h5v8h-5v5H8v-5H3V8h5z",
  clock: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 7v5l3 2",
  check: "M4 12l5 5L20 6",
  report: "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7m-7 4h7",
  database: "M4 6c0-4 16-4 16 0s-16 4-16 0Zm0 0v12c0 4 16 4 16 0V6M4 12c0 4 16 4 16 0",
};

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    <path d={paths[name]} />
  </svg>;
}
