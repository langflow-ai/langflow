import { AnimatePresence, motion, type SVGMotionProps } from "framer-motion";
import { useState, type SVGProps } from "react";
import { useCookies } from "react-cookie";
import { useAuth } from "@clerk/clerk-react";
import { Link } from "react-router-dom";
import VisualWorkflow from "./new-assets/VisualWorkflow.webp";
import demoWalkthrough from "./new-assets/demo-walkthrough.webp";
import logoicon from "./new-assets/visualailogo.png";
import {
  clearStoredOrgSelection,
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "./session";

/* -------------------- Icons -------------------- */

function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      <path
        d="M20.285 6.709a1 1 0 0 1 0 1.414l-9.192 9.192a1 1 0 0 1-1.414 0L3.715 11.55a1 1 0 0 1 1.414-1.415l5.136 5.136 8.485-8.485a1 1 0 0 1 1.535-.077z"
        fill="currentColor"
      />
    </svg>
  );
}

function PlayIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      <path d="M8 5v14l11-7z" fill="currentColor" />
    </svg>
  );
}

function AnimatedArrowIcon(props: SVGMotionProps<SVGSVGElement>) {
  return (
    <motion.svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      {...props}
      animate={{ x: [0, 4, 0] }}
      transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
    >
      <path
        d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"
        fill="currentColor"
      />
    </motion.svg>
  );
}

/* -------------------- Component -------------------- */

export default function LandingPage(): JSX.Element {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { isSignedIn, signOut } = useAuth();
  const [, , removeCookie] = useCookies([
    LANGFLOW_ACCESS_TOKEN,
    LANGFLOW_REFRESH_TOKEN,
  ]);

  const handleLogout = async () => {
    await signOut();
    removeCookie(LANGFLOW_ACCESS_TOKEN, { path: "/" });
    removeCookie(LANGFLOW_REFRESH_TOKEN, { path: "/" });
    clearStoredOrgSelection();
  };

  const handleDashboardClick = () => {
    window.location.assign("/flows");
  };

  /* -------------------- UI (copied structure from second file) -------------------- */

  return (
    <div className="h-screen overflow-y-auto bg-[#0f1217] text-white">
      {/* Background accents */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-gradient-to-br from-teal-500 to-blue-500/20 blur-3xl" />
        <div className="absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-gradient-to-br from-purple-500 to-pink-500/20 blur-3xl" />
      </div>

      {/* Navbar */}
      <header className="sticky top-0 z-40 backdrop-blur supports-[backdrop-filter]:bg-neutral-900/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          {/* Logo */}
          <div className="flex items-center gap-2 select-none">
            <img
              src={logoicon}
              alt="Logo"
              className="h-8 w-8 object-contain drop-shadow-md"
            />
            <span className="whitespace-nowrap text-sm font-semibold tracking-wide text-white/90 md:hidden">
              Visual AI Agents Builder
            </span>
            <span className="hidden whitespace-nowrap text-sm font-semibold tracking-wide text-white/90 md:inline">
              Visual AI Agents Builder
            </span>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden items-center gap-8 md:flex">
            <a className="text-white/70 hover:text-white" href="#features">
              Features
            </a>
            <a className="text-white/70 hover:text-white" href="#how">
              How it Works
            </a>
            <a className="text-white/70 hover:text-white" href="#enterprise">
              Enterprise
            </a>
            <a className="text-white/70 hover:text-white" href="#pricing">
              Pricing
            </a>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* Mobile Menu Toggle */}
            <button
              className="md:hidden p-2 rounded-lg hover:bg-white/10"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
            >
              <div className="space-y-1">
                <span className="block h-0.5 w-6 bg-white"></span>
                <span className="block h-0.5 w-6 bg-white"></span>
                <span className="block h-0.5 w-6 bg-white"></span>
              </div>
            </button>

            {/* Signed in / Signed out states */}
            {isSignedIn ? (
              <>
                <button
                  onClick={handleLogout}
                  className="hidden md:inline-block rounded-xl bg-white px-4 py-2 text-sm font-semibold text-neutral-900 transition hover:opacity-90"
                >
                  Sign Out
                </button>
                <button
                  onClick={handleDashboardClick}
                  className="whitespace-nowrap rounded-xl bg-gradient-to-r from-teal-500 to-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 flex items-center gap-2"
                >
                  Dashboard
                  <AnimatedArrowIcon className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                <a
                  href="#demo"
                  className="hidden md:inline-block rounded-xl bg-white px-4 py-2 text-sm font-semibold text-neutral-900 transition hover:opacity-90"
                >
                  Book a Demo
                </a>

                <Link
                  to="/login"
                  className="whitespace-nowrap rounded-xl bg-white px-4 py-2 text-sm font-semibold text-neutral-900 transition hover:opacity-90"
                >
                  Log in
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {isMenuOpen && (
          <motion.div
            initial={{ opacity: 0, x: "100%" }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: "100%" }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-50 flex flex-col items-center justify-start bg-gradient-to-b from-[#0f1217] via-50% via-[#0f1217] to-transparent px-6 pt-24 backdrop-blur-md"
          >
            <button
              className="absolute top-4 right-4 p-2 rounded-lg hover:bg-white/10"
              onClick={() => setIsMenuOpen(false)}
            >
              ✕
            </button>
            <nav className="space-y-6 text-center text-x">
              <a
                className="block text-white/90 hover:text-white"
                href="#features"
                onClick={() => setIsMenuOpen(false)}
              >
                Features
              </a>
              <a
                className="block text-white/90 hover:text-white"
                href="#how"
                onClick={() => setIsMenuOpen(false)}
              >
                How it Works
              </a>
              <a
                className="block text-white/90 hover:text-white"
                href="#enterprise"
                onClick={() => setIsMenuOpen(false)}
              >
                Enterprise
              </a>
              <a
                className="block text-white/90 hover:text-white"
                href="#pricing"
                onClick={() => setIsMenuOpen(false)}
              >
                Pricing
              </a>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      {/* -------------------- HERO -------------------- */}

      <section className="relative mx-auto max-w-7xl px-4 pb-12 pt-20 sm:pt-28">
        <div className="grid items-center gap-10 md:grid-cols-2">
          <div>
            <p className="mb-4 inline-block rounded-full border border-white/10 px-3 py-1 text-xs text-white/70">
              Powered by Langflow + Enterprise Security
            </p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
              Build AI Agents in Minutes.
              <br />
              <span className="block bg-gradient-to-r from-teal-400 to-blue-400 bg-clip-text text-transparent pb-1">
                Drag, Drop & Deploy Securely.
              </span>
            </h1>
            <p className="mt-5 max-w-xl text-white/70">
              Visual AI Agents Builder brings you a no-/low-code interface on top
              of Langflow, with enterprise-grade tenancies, SSO, data isolation,
              audit logs & security out-of-the-box.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <a
                href="#demo"
                className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-neutral-900"
              >
                Book a Demo
              </a>
              <a
                href="#video"
                className="flex items-center gap-2 rounded-xl border border-white/15 px-5 py-3 text-sm text-white/90 hover:bg-white/5"
              >
                <PlayIcon className="h-4 w-4" /> Watch the Demo
              </a>
            </div>
            <div className="mt-6 flex items-center gap-6 text-xs text-white/60">
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4" />Visual drag-and-drop flows
              </div>
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4" />Deploy as API / MCP tools
              </div>
            </div>
          </div>

          <div className="relative">
            <img
              src={VisualWorkflow}
              alt="Visual workflow builder screenshot"
              className="w-full h-auto rounded-2xl border border-black/5 object-cover"
            />
            <div className="absolute -bottom-4 -right-4 hidden h-40 w-40 rounded-full bg-teal-500/20 blur-2xl md:block" />
          </div>
        </div>
      </section>

      {/* -------------------- FEATURES -------------------- */}

      <section id="features" className="mx-auto max-w-7xl px-4 py-20">
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Features</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {[
            {
              title: "Visual Flow Builder",
              desc: "Build and connect components, agents, memory, tools & prompts via drag-drop to design complex AI workflows without writing boilerplate code.",
            },
            {
              title: "Wide AI Stack Support",
              desc: "Use any leading LLM or vector database; support for custom components. Cloud or local deployment options including GPU acceleration.",
            },
            {
              title: "Real-Time Testing & Deployment",
              desc: "Test flows in real time using playground; deploy flows as APIs or MCP servers; version control and inference options.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-white/10 bg-[#0f1217] p-6"
            >
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-white/70">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------- HOW IT WORKS -------------------- */}

      <section id="how" className="mx-auto max-w-7xl px-4 py-20">
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">How it Works</h2>
          <a href="#docs" className="text-sm text-white/70 hover:text-white">
            Read the Docs →
          </a>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {[
            {
              step: "01",
              title: "Design Flow",
              desc: "Choose from prebuilt templates or start fresh: drag & drop components to build agents, tools, memory, and LLM calls.",
            },
            {
              step: "02",
              title: "Test & Tune",
              desc: "Use live playground; adjust prompts, test agents; monitor performance and debug before deploying live.",
            },
            {
              step: "03",
              title: "Deploy Securely",
              desc: "Deploy to enterprise cloud or on-prem; configure SSO, isolate data per-tenant; audit logs & compliance baked-in.",
            },
          ].map((step) => (
            <div
              key={step.title}
              className="relative rounded-2xl border border-white/10 p-6"
            >
              <span className="absolute -top-3 left-6 rounded-full border border-white/15 bg-[#0f1217] px-3 py-1 text-xs text-white/70">
                {step.step}
              </span>
              <h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-white/70">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------- ENTERPRISE -------------------- */}

      <section
        id="enterprise"
        className="mx-auto max-w-7xl rounded-2xl border border-white/10 bg-[#0f1217] px-4 py-20"
      >
        <h2 className="text-2xl font-semibold text-center">
          Enterprise-grade Capabilities
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-white/70">
          Everything you need for teams, security, compliance, and scale.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            {
              title: "Organization Tenancies & RBAC",
              desc: "Multiple teams under your account; fine-grained permissions; keep workspaces separated by team or business unit.",
            },
            {
              title: "Single Sign-On (SSO) & Audit Logs",
              desc: "Integrate SSO with your identity provider, get logs & user activity tracked for compliance & security reviews.",
            },
            {
              title: "Data Isolation & Security by Design",
              desc: "Isolated data per tenant; encrypted at rest & in transit; cloud or on-prem options; compliance support (GDPR, etc.).",
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-white/10 bg-[#0f1217] p-6"
            >
              <h3 className="text-lg font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm text-white/70">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------- STATS -------------------- */}

      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid gap-6 rounded-2xl border border-white/10 bg-[#0f1217] p-8 md:grid-cols-3">
          {[
            { k: "80%+", v: "reduction in development time" },
            { k: "Hundreds", v: "of LLMs & vector DBs supported" },
            { k: "Enterprise Ready", v: "SSO · Tenancies · Data Isolation" },
          ].map((item) => (
            <div key={item.k} className="text-center">
              <div className="text-4xl font-semibold tracking-tight">
                {item.k}
              </div>
              <div className="mt-1 text-sm text-white/70">{item.v}</div>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------- VIDEO SECTION -------------------- */}

      <section id="video" className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid items-center gap-8 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold">See it In Action</h2>
            <p className="mt-3 max-w-prose text-white/70">
              Watch our walkthrough of the visual flow builder, enterprise
              features, and how quickly you can build & deploy an AI agent.
            </p>

            <div className="mt-6 flex items-center gap-3 text-sm text-white/70">
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4" />Local & Cloud Deployment
              </div>
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4" />Observability & Logging
              </div>
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4" />Compliance & Security Controls
              </div>
            </div>
          </div>

          <div className="aspect-video w-full overflow-hidden rounded-2xl border border-white/10 bg-[#0f1217]">
            <img
              src={demoWalkthrough}
              alt="Demo video walkthrough"
              className="h-full w-full object-cover"
            />
          </div>
        </div>
      </section>

      {/* -------------------- PRICING -------------------- */}

      <section id="pricing" className="mx-auto max-w-7xl px-4 py-20">
        <div className="rounded-2xl border border-white/10 bg-[#0f1217] p-8">
          <div className="grid gap-10 md:grid-cols-2">
            <div>
              <h2 className="text-2xl font-semibold">Fair, Transparent Pricing</h2>
              <p className="mt-3 text-white/70">
                Free (for developers) plus paid plans for teams and enterprise
                with full security & support.
              </p>
              <ul className="mt-6 space-y-2 text-sm text-white/80">
                <li className="flex items-center gap-2">
                  <CheckIcon className="h-4 w-4" />Unlimited public flows
                </li>
                <li className="flex items-center gap-2">
                  <CheckIcon className="h-4 w-4" />Team seats & organization
                  tenancies
                </li>
                <li className="flex items-center gap-2">
                  <CheckIcon className="h-4 w-4" />Enterprise support & SLA
                </li>
              </ul>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-[#0f1217] p-6">
                <div className="text-sm text-white/60">Starter</div>
                <div className="mt-2 text-3xl font-semibold">Free</div>
                <p className="mt-2 text-sm text-white/70">
                  For personal projects, hobbyists. All core features except
                  enterprise.
                </p>
                <a
                  href="#signup"
                  className="mt-4 inline-block rounded-lg bg-white px-4 py-2 text-sm font-semibold text-neutral-900"
                >
                  Get Started Free
                </a>
              </div>

              <div className="rounded-xl border border-white/10 bg-[#0f1217] p-6">
                <div className="text-sm text-white/60">Enterprise</div>
                <div className="mt-2 text-3xl font-semibold">Contact Us</div>
                <p className="mt-2 text-sm text-white/70">
                  Includes SSO, data isolation, custom deployment, dedicated
                  support & SLAs.
                </p>
                <a
                  href="#contact"
                  className="mt-4 inline-block rounded-lg border border-white/15 px-4 py-2 text-sm"
                >
                  Contact Sales
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* -------------------- BLOG -------------------- */}

      <section id="blog" className="mx-auto max-w-7xl px-4 py-14">
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Latest from the Blog</h2>
          <a href="#all-posts" className="text-sm text-white/70 hover:text-white">
            View all →
          </a>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <article
              key={item}
              className="rounded-2xl border border-white/10 bg-[#0f1217] p-5"
            >
              <div className="aspect-[16/9] w-full rounded-lg bg-white/5" />
              <h3 className="mt-4 text-lg font-semibold">
                Blog post title {item}
              </h3>
              <p className="mt-1 text-sm text-white/70">
                Insights, tutorials & best practices on AI workflows, agents, and
                security.
              </p>
              <a
                href="#"
                className="mt-4 inline-block text-sm text-white/80 hover:text-white"
              >
                Read more →
              </a>
            </article>
          ))}
        </div>
      </section>

      {/* -------------------- FOOTER -------------------- */}

      <footer className="border-t border-white/10">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-4">
          <div className="flex flex-col items-start space-y-3 text-left">
            <img
              src={logoicon}
              alt="Logo"
              className="h-8 w-8 object-contain drop-shadow-md"
            />
            <p className="mt-3 max-w-xs text-sm text-white/70">
              Build, deploy and scale AI agents enterprise-securely, powered by
              Langflow.
            </p>
          </div>

          <div>
            <div className="text-sm font-semibold">Product</div>
            <ul className="mt-3 space-y-2 text-sm text-white/70">
              <li>
                <a href="#features">Features</a>
              </li>
              <li>
                <a href="#how">How it Works</a>
              </li>
              <li>
                <a href="#enterprise">Enterprise</a>
              </li>
            </ul>
          </div>

          <div>
            <div className="text-sm font-semibold">Support</div>
            <ul className="mt-3 space-y-2 text-sm text-white/70">
              <li>
                <a href="#docs">Docs</a>
              </li>
              <li>
                <a href="#blog">Blog</a>
              </li>
              <li>
                <a href="#contact">Contact</a>
              </li>
            </ul>
          </div>

          <div>
            <div className="text-sm font-semibold">Legal & Company</div>
            <ul className="mt-3 space-y-2 text-sm text-white/70">
              <li>
                <a href="#privacy">Privacy Policy</a>
              </li>
              <li>
                <a href="#terms">Terms of Service</a>
              </li>
              <li>
                <a href="#careers">Careers</a>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/10 py-6 text-center text-xs text-white/60">
          © {new Date().getFullYear()} Visual AI Agents Builder. All rights
          reserved.
        </div>
      </footer>
    </div>
  );
}
