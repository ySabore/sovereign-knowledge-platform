import { Link } from "react-router-dom";

export function PlaceholderPage({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="sk-layout">
      <aside className="sk-nav">
        <Link to="/home">← Home</Link>
        <h2 style={{ fontSize: "1rem", margin: "1rem 0 0.5rem" }}>{title}</h2>
        <p className="sk-muted" style={{ fontSize: "0.85rem" }}>
          Placeholder route — extend when you wire admin or onboarding flows.
        </p>
      </aside>
      <main className="sk-main">
        <h2 style={{ marginTop: 0 }}>{title}</h2>
        <p className="sk-muted">{detail}</p>
      </main>
    </div>
  );
}
