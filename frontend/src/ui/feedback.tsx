export function LoadingState({
  label = "Cargando…",
}: {
  readonly label?: string;
}): React.JSX.Element {
  return (
    <div className="surface-solid feedback" role="status" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorMessage({
  children,
}: {
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <p className="surface-solid error-message" role="alert">
      {children}
    </p>
  );
}

export function EmptyState({
  title,
  children,
}: {
  readonly title: string;
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <section className="surface-solid empty-state">
      <h2>{title}</h2>
      <p>{children}</p>
    </section>
  );
}
