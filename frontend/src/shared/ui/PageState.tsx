type PageStateProps = { title: string; description: string; children: React.ReactNode };

export function PageState({ title, description, children }: PageStateProps) {
  return (
    <section className="route-view-intro" aria-labelledby="route-view-title">
      <h2 id="route-view-title">{title}</h2>
      <p className="muted">{description}</p>
      {children}
    </section>
  );
}
