import { useId } from "react";

interface CompositionDatum {
  readonly label: string;
  readonly valueCents: number;
}

function barWidth(valueCents: number, maximumCents: number): number {
  if (valueCents <= 0 || maximumCents <= 0) return 0;
  return Math.max(6, (valueCents / maximumCents) * 280);
}

export function CompositionChart({
  title,
  first,
  second,
}: {
  readonly title: string;
  readonly first: CompositionDatum;
  readonly second: CompositionDatum;
}): React.JSX.Element {
  const accessibleId = useId();
  const values = [first.valueCents, second.valueCents];
  const maximumCents = Math.max(0, ...values);
  const isNeutral = values.some((value) => value <= 0);
  const description = isNeutral
    ? "Las cantidades nulas o negativas se señalan de forma neutral; los importes firmados exactos figuran junto al gráfico."
    : "Dos bandas comparan las magnitudes actuales; los importes exactos figuran junto al gráfico.";

  return (
    <svg
      viewBox="0 0 320 72"
      width="100%"
      height="72"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-labelledby={`${accessibleId}-title ${accessibleId}-description`}
      data-chart-state={isNeutral ? "neutral" : "comparative"}
      className="composition-chart"
    >
      <title id={`${accessibleId}-title`}>{title}</title>
      <desc id={`${accessibleId}-description`}>{description}</desc>
      {[first, second].map((datum, index) => {
        const y = 8 + index * 36;
        const width = barWidth(datum.valueCents, maximumCents);
        return (
          <g key={datum.label}>
            <rect
              x="20"
              y={y}
              width="280"
              height="20"
              rx="10"
              fill="var(--color-border)"
            />
            {width > 0 ? (
              <rect
                x="20"
                y={y}
                width={width}
                height="20"
                rx="10"
                fill={
                  index === 0
                    ? "var(--color-primary)"
                    : "var(--color-text-muted)"
                }
              />
            ) : (
              <path
                d={`M 24 ${y + 4} L 36 ${y + 16} M 36 ${y + 4} L 24 ${y + 16}`}
                stroke="var(--color-text-muted)"
                strokeWidth="2"
                strokeLinecap="round"
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
