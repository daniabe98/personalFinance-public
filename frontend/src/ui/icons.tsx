export type IconName =
  | "summary"
  | "movement"
  | "reconcile"
  | "organize"
  | "settings"
  | "check"
  | "draft"
  | "void"
  | "warning";

const paths: Readonly<Record<IconName, string>> = {
  summary: "M4 19V9m6 10V5m6 14v-7m4 7H2",
  movement: "M4 7h13m0 0-3-3m3 3-3 3M20 17H7m0 0 3-3m-3 3 3 3",
  reconcile: "m5 12 4 4L19 6M4 4h7M4 20h16",
  organize: "M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4M10 16v4",
  settings:
    "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM19.4 15a1.8 1.8 0 0 0 .36 1.98l.06.06-2 3.46-.08-.02a1.8 1.8 0 0 0-1.9.68l-.42.72h-4l-.42-.72a1.8 1.8 0 0 0-1.9-.68l-.08.02-2-3.46.06-.06A1.8 1.8 0 0 0 7.44 15L7 14.25v-4.5L7.44 9a1.8 1.8 0 0 0-.36-1.98l-.06-.06 2-3.46.08.02a1.8 1.8 0 0 0 1.9-.68l.42-.72h4l.42.72a1.8 1.8 0 0 0 1.9.68l.08-.02 2 3.46-.06.06A1.8 1.8 0 0 0 19.4 9l.44.75v4.5Z",
  check: "m5 12 4 4L19 6",
  draft: "M5 4h10l4 4v12H5ZM14 4v5h5M8 14h8M8 17h5",
  void: "M6 6l12 12M18 6 6 18",
  warning: "M12 4 3 20h18ZM12 9v5m0 3v.01",
};

export function Icon({
  name,
  label,
}: {
  readonly name: IconName;
  readonly label?: string;
}): React.JSX.Element {
  return (
    <svg
      aria-hidden={label === undefined}
      aria-label={label}
      className="icon"
      fill="none"
      height="24"
      role={label === undefined ? undefined : "img"}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      width="24"
    >
      <path d={paths[name]} />
    </svg>
  );
}
