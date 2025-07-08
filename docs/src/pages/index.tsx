import React from "react";
import Layout from "@theme/Layout";
import Link from "@docusaurus/Link";
import ThemedImage from "@theme/ThemedImage";
import {
  CirclePlay,
  Server,
  ArrowRight,
  MonitorDown,
  AppWindow,
  HardDriveUpload,
  Code,
  Star,
  LifeBuoy,
  SquareArrowOutUpRight,
  GraduationCap,
  BookMarked,
} from "lucide-react";
import CustomIcon from "../components/CustomIcon";
import styles from "./index.module.css";

export default function Home() {
  return (
    <Layout
      title="Build smarter AI apps with Langflow"
      description="Find all the guides and resources you need to build powerful AI applications with Langflow's visual framework."
    >
      <main className={styles.main}>
        {/* Header Section */}
        <div className={styles.heroSection}>
          <div className={styles.heroContent}>
            <h1 className={styles.heroTitle}>
              Build smarter AI apps with Langflow
            </h1>
            <p className={styles.heroDescription}>
              Langflow empowers developers to rapidly prototype and build AI
              applications with a user-friendly visual interface and powerful
              features. Whether you're a seasoned AI developer or just starting
              out, Langflow provides the tools you need to bring your AI ideas
              to life.
            </p>
          </div>
          <div className={styles.heroImage}>
            <ThemedImage
              alt="Langflow MCP Server with GitPoet agent example"
              sources={{
                light: "img/lf-agent-light.png",
                dark: "img/lf-agent-dark.png",
              }}
              className={styles.heroImageContent}
            />
          </div>
        </div>

        {/* Quick Links Section */}
        <div className={styles.quickLinksSection}>
          <Link to="/get-started-quickstart" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <CirclePlay size={32} strokeWidth={1.25} />
            </div>
            <h2 className={styles.quickLinkTitle}>Quickstart</h2>
            <p className={styles.quickLinkDescription}>
            Build and run your first flow in minutes.
            </p>
          </Link>
          <Link to="/agents" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <CustomIcon name="agents" size={32} />
            </div>
            <h2 className={styles.quickLinkTitle}>Agents</h2>
            <p className={styles.quickLinkDescription}>
            Build agentic flows with your favorite models, custom
            instructions, and tools.
            </p>
          </Link>
          <Link to="/mcp-server" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <Server size={32} strokeWidth={1.25} />
            </div>
            <h2 className={styles.quickLinkTitle}>MCP</h2>
            <p className={styles.quickLinkDescription}>
              Use Langflow as both an MCP server and an MCP client.
            </p>
          </Link>
        </div>

        {/* Use Cases Section */}
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Learn more</h3>
          <div className={styles.cardsGrid}>
          <Link to="/" className={styles.card}>
              <div className={styles.cardIcon}>
                <BookMarked size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>About Langflow</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/get-started-installation" className={styles.card}>
              <div className={styles.cardIcon}>
                <MonitorDown size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Install Langflow</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/" className={styles.card}>
              <div className={styles.cardIcon}>
                <GraduationCap size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Tutorial</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/api-reference-api-examples" className={styles.card}>
              <div className={styles.cardIcon}>
                <Code size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>API reference</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/develop-application" className={styles.card}>
              <div className={styles.cardIcon}>
                <AppWindow size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Develop applications</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/deployment-overview" className={styles.card}>
              <div className={styles.cardIcon}>
                <HardDriveUpload size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Deploy servers</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <Link to="/troubleshoot" className={styles.card}>
              <div className={styles.cardIcon}>
                <LifeBuoy size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Support</div>
              </div>
              <div className={styles.cardArrow}>
                <ArrowRight size={20} strokeWidth={1.25} />
              </div>
            </Link>
            <a
              href="https://github.com/langflow-ai/langflow/releases/latest"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.card}
            >
              <div className={styles.cardIcon}>
                <Star size={16} strokeWidth={1.25} />
              </div>
              <div className={styles.cardContent}>
                <div className={styles.cardTitle}>Release notes</div>
              </div>
              <div className={styles.cardArrow}>
                <SquareArrowOutUpRight size={20} strokeWidth={1.25} />
              </div>
            </a>
          </div>
        </section>

        {/* Community Section */}
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Need help getting started?</h3>
          <div className={styles.communityGrid}>
            <a
              href="https://github.com/langflow-ai/langflow"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.communityCard}
            >
              <div className={styles.communityIcon}>
                <CustomIcon name="github" size={32} />
              </div>
              <div className={styles.communityTitle}>Star the repo</div>
              <div className={styles.communityDescription}>
                Follow development, star the repo, and contribute to Langflow.
              </div>
            </a>
            <a
              href="https://discord.gg/EqksyE2EX9"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.communityCard}
            >
              <div className={styles.communityIcon}>
                <CustomIcon name="discord" size={32} />
              </div>
              <div className={styles.communityTitle}>Join the Discord</div>
              <div className={styles.communityDescription}>
                Join builders, ask questions, and show off your agents.
              </div>
            </a>
          </div>
        </section>
      </main>
    </Layout>
  );
}
