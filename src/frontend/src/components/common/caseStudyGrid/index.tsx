import { Badge } from "@/components/ui/badge";

interface CaseStudy {
  logo: React.ReactNode;
  industry: string;
  industryColor?: string;
  title: string;
  description: string;
  whyLangflow: string[];
  metrics: { label: string; color?: string }[];
}

const caseStudies: CaseStudy[] = [
  {
    logo: (
      <div className="flex items-center gap-2 text-xl font-bold">
        <span className="text-2xl">⊞</span> GIC
      </div>
    ),
    industry: "Sovereign Wealth Fund",
    title: "Investment Data Intelligence",
    description:
      "Building complex data pipelines with 100+ components for enterprise document analysis, automated investment reporting, and natural language querying of financial data sources.",
    whyLangflow: [
      "Governance & control via component-based permissions",
      "Production-ready API server architecture",
    ],
    metrics: [
      { label: "100+ components" },
      { label: "30-60 min/run" },
      { label: "API Endpoints" },
    ],
  },
  {
    logo: (
      <div className="text-xl font-bold tracking-wider text-blue-600">
        ○NFORCE.AI
      </div>
    ),
    industry: "AI Platform",
    industryColor: "bg-blue-100 text-blue-700",
    title: "Sales & Support Automation",
    description:
      "Flow-powered agents for HubSpot sales and WhatsApp lead qualification. RAG pipelines processing 1M+ support tickets with human-in-the-loop oversight and monitoring.",
    whyLangflow: [
      "Flow-powered agents vs simple prompt-based",
      "Extensible architecture for custom security",
    ],
    metrics: [
      { label: "1M+ tickets", color: "bg-emerald-100 text-emerald-700" },
      { label: "Multi-tenant", color: "bg-emerald-100 text-emerald-700" },
      { label: "Sandboxed", color: "bg-emerald-100 text-emerald-700" },
    ],
  },
  {
    logo: (
      <div className="flex items-center gap-2 text-xl font-bold">
        <span className="rounded bg-green-600 px-2 py-1 text-white">C</span>
        <span>Creditas</span>
      </div>
    ),
    industry: "Fintech · Brazil",
    industryColor: "bg-pink-100 text-pink-700",
    title: "Multi-Agent Sales Assistant",
    description:
      "WhatsApp sales assistant with multi-agent routing—Classifier routes to specialized FAQ, Closing, Offers, and General agents. Plus automated summarization for support teams.",
    whyLangflow: [
      "Open source with no vendor lock-in (100% MIT)",
      "Intuitive low-code interface for multi-team adoption",
    ],
    metrics: [
      { label: "192K summaries", color: "bg-pink-100 text-pink-700" },
      { label: "96.6% accuracy", color: "bg-pink-100 text-pink-700" },
      { label: "Multi-instance", color: "bg-pink-100 text-pink-700" },
    ],
  },
  {
    logo: (
      <div className="flex items-center gap-2 text-xl font-bold">
        <span className="text-purple-600">◆</span>
        <span>NEUROTECH</span>
      </div>
    ),
    industry: "AI & ML · Brazil",
    industryColor: "bg-emerald-100 text-emerald-700",
    title: "Debt Collection Call Analytics",
    description:
      "Processing 40K+ daily debt collection calls through AI: transcription, sentiment analysis, payment capacity extraction, and negotiation scoring to optimize recovery outcomes.",
    whyLangflow: [
      "Platform mindset with reusable, modular components",
      "Horizontal scaling for high-volume processing",
    ],
    metrics: [
      { label: "80K req/day", color: "bg-emerald-100 text-emerald-700" },
      { label: "60B tokens/mo", color: "bg-emerald-100 text-emerald-700" },
      { label: "77 workers", color: "bg-emerald-100 text-emerald-700" },
    ],
  },
];

function CaseStudyCard({ study }: { study: CaseStudy }) {
  return (
    <div className="flex flex-col rounded-lg border border-border bg-background p-6">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        {study.logo}
        <Badge
          variant="outline"
          className={study.industryColor || "bg-muted text-muted-foreground"}
        >
          {study.industry}
        </Badge>
      </div>

      {/* Title */}
      <h3 className="mb-2 text-lg font-semibold">{study.title}</h3>

      {/* Description */}
      <p className="mb-4 text-sm text-muted-foreground">{study.description}</p>

      {/* Why Langflow */}
      <div className="mb-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-600">
          Why Langflow
        </p>
        <ul className="space-y-1">
          {study.whyLangflow.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500" />
              {reason}
            </li>
          ))}
        </ul>
      </div>

      {/* Metrics */}
      <div className="mt-auto flex flex-wrap gap-2">
        {study.metrics.map((metric, idx) => (
          <Badge
            key={idx}
            variant="outline"
            className={metric.color || "bg-muted text-muted-foreground"}
          >
            {metric.label}
          </Badge>
        ))}
      </div>
    </div>
  );
}

export default function CaseStudyGrid() {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      {caseStudies.map((study, idx) => (
        <CaseStudyCard key={idx} study={study} />
      ))}
    </div>
  );
}
