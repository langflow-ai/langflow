import React, { useEffect, useState } from "react";
import Link from "@docusaurus/Link";
import { useLocation } from "@docusaurus/router";
import useBaseUrl from "@docusaurus/useBaseUrl";
import {
  ThumbsUp as ThumbsUpIcon,
  ThumbsDown as ThumbsDownIcon,
  LifeBuoy as LifeBuoyIcon,
} from "lucide-react";
import {
  identifyUser,
  trackEvent,
} from "@site/src/plugins/segment/analytics-helpers";
import styles from "./PageFeedback.module.css";

type Feedback = "good" | "bad";

const GITHUB_REPO = "https://github.com/langflow-ai/langflow";

function buildIssueUrl(pageUrl: string): string {
  const title = `[DOCS] Feedback on ${pageUrl}`;
  const body = [
    `**Page:** ${pageUrl}`,
    "",
    "**What can we improve on this page?**",
    "",
  ].join("\n");
  const params = new URLSearchParams({
    title,
    body,
    labels: "documentation",
  });
  return `${GITHUB_REPO}/issues/new?${params.toString()}`;
}

export function PageFeedback(): JSX.Element {
  const { pathname } = useLocation();
  const supportUrl = useBaseUrl("/contributing-github-issues");
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  // Reset when navigating to another doc page.
  useEffect(() => {
    setFeedback(null);
  }, [pathname]);

  const submitFeedback = (value: Feedback) => {
    setFeedback(value);
    // Dedicated event (instead of the generic data-attribute "UI Interaction")
    // so feedback can be queried directly by the `helpful` boolean.
    identifyUser();
    trackEvent("Docs Feedback", {
      helpful: value === "good",
      action: "clicked",
      channel: "docs",
      elementId: `page-feedback-${value}`,
      namespace: "doc-footer",
      platformTitle: "Langflow",
    });
  };

  const pageUrl =
    typeof window !== "undefined"
      ? window.location.href
      : `https://docs.langflow.org${pathname}`;

  return (
    <div className={styles.root}>
      <p className={styles.title}>Was this page helpful?</p>
      <div className={styles.row}>
        <div className={styles.buttons}>
          {feedback === null ? (
            <>
              <button
                type="button"
                className={styles.button}
                onClick={() => submitFeedback("good")}
              >
                <ThumbsUpIcon size={14} strokeWidth={2} aria-hidden="true" />
                <span>Good</span>
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => submitFeedback("bad")}
              >
                <ThumbsDownIcon size={14} strokeWidth={2} aria-hidden="true" />
                <span>Bad</span>
              </button>
            </>
          ) : (
            <p className={styles.thanks} role="status">
              Thanks for your feedback!{" "}
              {feedback === "bad" && (
                <>
                  Help us improve this page by{" "}
                  <a
                    href={buildIssueUrl(pageUrl)}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-event="UI Interaction"
                    data-action="clicked"
                    data-channel="docs"
                    data-element-id="page-feedback-github-issue"
                    data-namespace="doc-footer"
                    data-platform-title="Langflow"
                  >
                    opening a GitHub issue
                  </a>
                  .
                </>
              )}
            </p>
          )}
        </div>
        <Link
          to={supportUrl}
          className={styles.supportLink}
          data-event="UI Interaction"
          data-action="clicked"
          data-channel="docs"
          data-element-id="page-feedback-support"
          data-namespace="doc-footer"
          data-platform-title="Langflow"
        >
          <LifeBuoyIcon size={14} strokeWidth={2} aria-hidden="true" />
          <span>Support</span>
        </Link>
      </div>
    </div>
  );
}
