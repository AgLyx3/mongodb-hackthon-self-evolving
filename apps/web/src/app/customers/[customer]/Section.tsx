type SectionProps = { title: string; caption?: string; children: React.ReactNode };

export function Section({ title, caption, children }: SectionProps) {
  return (
    <section style={{ marginTop: "var(--space-8)" }} aria-label={title}>
      <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 600, margin: 0 }}>{title}</h2>
      {caption ? (
        <p className="muted prose-block" style={{ margin: "var(--space-1) 0 var(--space-3)" }}>
          {caption}
        </p>
      ) : null}
      {children}
    </section>
  );
}
