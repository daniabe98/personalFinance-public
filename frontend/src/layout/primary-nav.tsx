import { NavLink } from "react-router-dom";

import { Icon, type IconName } from "../ui/icons";

const destinations: readonly {
  readonly to: string;
  readonly label: string;
  readonly icon: IconName;
}[] = [
  { to: "/resumen", label: "Resumen", icon: "summary" },
  { to: "/movimientos", label: "Movimientos", icon: "movement" },
  { to: "/conciliar", label: "Conciliar", icon: "reconcile" },
  { to: "/organizar", label: "Organizar", icon: "organize" },
  { to: "/ajustes", label: "Ajustes", icon: "settings" },
];

export function PrimaryNav(): React.JSX.Element {
  return (
    <nav className="glass-strong primary-nav" aria-label="Navegación principal">
      <NavLink
        className="brand"
        to="/resumen"
        aria-label="Self-Report, ir al resumen"
      >
        Self-Report
      </NavLink>
      <ul>
        {destinations.map((destination) => (
          <li key={destination.to}>
            <NavLink to={destination.to}>
              <Icon name={destination.icon} />
              <span>{destination.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
