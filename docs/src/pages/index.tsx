import React from "react";
import Layout from "@theme/Layout";
import Link from "@docusaurus/Link";
import {
  Play,
  Bot,
  Layers,
  Link as LinkIcon,
  Github,
  MessageCircle,
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
            {/* Placeholder for hero image */}
            <span className={styles.placeholder}>Hero Image Coming Soon</span>
          </div>
        </div>

        {/* Quick Links Section */}
        <div className={styles.quickLinksSection}>
          <Link to="/get-started-quickstart" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <Play size={24} />
            </div>
            <h2 className={styles.quickLinkTitle}>Quickstart</h2>
            <p className={styles.quickLinkDescription}>
              Run your first flow in minutes.
            </p>
          </Link>
          <Link to="/agents" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <CustomIcon name="agents" size={24} />
            </div>
            <h2 className={styles.quickLinkTitle}>Agents</h2>
            <p className={styles.quickLinkDescription}>
              Langflow's Agent component provides everything you need to create
              an agent, including support for multiple LLM providers, custom
              instructions, and tools.
            </p>
          </Link>
          <Link to="/mcp-server" className={styles.quickLinkCard}>
            <div className={styles.quickLinkIcon}>
              <Layers size={24} />
            </div>
            <h2 className={styles.quickLinkTitle}>MCP</h2>
            <p className={styles.quickLinkDescription}>
              You can use Langflow as both an MCP server and an MCP client.
            </p>
          </Link>
        </div>

        {/* Use Cases Section */}
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Use cases</h3>
          <div className={styles.cardsGrid}>
            {[...Array(6)].map((_, i) => (
              <div key={i} className={styles.card}>
                <div className={styles.cardIcon}>
                  <LinkIcon size={16} />
                </div>
                <div className={styles.cardContent}>
                  <div className={styles.cardTitle}>
                    Basic Prompting (Hello, World)
                  </div>
                  <div className={styles.cardDescription}>
                    A chatbot that helps developers ide...
                  </div>
                </div>
              </div>
            ))}
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
                <Github size={32} />
              </div>
              <div className={styles.communityTitle}>Star the repo</div>
              <div className={styles.communityDescription}>
                Follow development, star the repo, and shape the future.
              </div>
            </a>
            <a
              href="https://discord.gg/EqksyE2EX9"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.communityCard}
            >
              <div className={styles.communityIcon}>
                <MessageCircle size={32} />
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
