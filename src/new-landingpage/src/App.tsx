import "./App.css";

const features = [
  "Visual builder for complex AI flows",
  "One-click deployment",
  "Extensible component catalog",
  "Bring your own keys and data"
];

export default function App() {
  return (
    <main className="hero">
      <section>
        <p className="eyebrow">Introducing</p>
        <h1>Langflow Landing Page</h1>
        <p className="description">
          This lightweight Vite application is served from <code>/new/landingpage</code>
          and helps demonstrate how nginx can multiplex between Langflow and
          standalone marketing pages inside a single container image.
        </p>
        <div className="cta-row">
          <a className="cta" href="https://github.com/langflow-ai/langflow" target="_blank" rel="noreferrer">
            Visit GitHub
          </a>
          <a className="secondary" href="https://docs.langflow.org" target="_blank" rel="noreferrer">
            Explore Docs
          </a>
        </div>
      </section>
      <section className="feature-card">
        <h2>Why Langflow?</h2>
        <ul>
          {features.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}