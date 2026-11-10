import { render, screen, within } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { findDecisionEvidence } from "../decision-evidence";
import DecisionInspection from "../index";
import {
  acceptedChoice,
  belowThreshold,
  decisionModelNoulRefusal,
  decisionModelScore,
  malformedToElse,
  noulAccepted,
  refusedToElse,
  scoreAccepted,
  transportStopped,
} from "./decision-fixtures";

const renderEvidence = (value: unknown) =>
  render(<DecisionInspection evidence={findDecisionEvidence(value)!} />);

describe("DecisionInspection", () => {
  it("shows a successful route with its distribution, threshold and model", () => {
    renderEvidence(acceptedChoice);

    expect(screen.getByTestId("decision-tone")).toHaveTextContent("Accepted");
    expect(screen.getByTestId("decision-branch")).toHaveTextContent(
      "Branch: Billing",
    );
    expect(screen.getByTestId("decision-reason")).toHaveTextContent(
      "Billing had 100%, meeting its minimum probability of 50%.",
    );
    const billing = screen.getByTestId("decision-row-category_5_result");
    expect(within(billing).getByText("Activated")).toBeInTheDocument();
    expect(within(billing).getByText("Provider's pick")).toBeInTheDocument();
    expect(screen.getByTestId("decision-model")).toHaveTextContent(
      "OpenAI · gpt-6-luna",
    );
    expect(screen.getByTestId("decision-confidence")).toHaveTextContent("100%");
    expect(screen.queryByTestId("decision-failure")).not.toBeInTheDocument();
  });

  it("shows an uncertain answer sent to Else with the threshold it missed", () => {
    renderEvidence(belowThreshold);

    expect(screen.getByTestId("decision-tone")).toHaveTextContent("Uncertain");
    expect(screen.getByTestId("decision-branch")).toHaveTextContent(
      "Branch: Else",
    );
    expect(screen.getByTestId("decision-reason")).toHaveTextContent(
      "Threshold not met: Billing had 78%, below its minimum probability of 99%.",
    );
    // The provider's top pick is shown, but nothing was activated on a route.
    expect(screen.queryByText("Activated")).not.toBeInTheDocument();
    expect(screen.getByText("Provider's pick")).toBeInTheDocument();
  });

  it("says a missing confidence is not reported rather than zero", () => {
    renderEvidence(belowThreshold);

    expect(screen.getByTestId("decision-confidence")).toHaveTextContent(
      "Not reported",
    );
  });

  it("shows Noul P(true) apart from the provider's confidence", () => {
    renderEvidence(noulAccepted);

    expect(screen.getByTestId("decision-probability-true")).toHaveTextContent(
      "98%",
    );
    expect(screen.getByTestId("decision-confidence")).toHaveTextContent(
      "Not reported",
    );
    expect(screen.getByTestId("decision-row-no_result")).toHaveTextContent(
      "2%",
    );
  });

  it("shows a score on its ordered scale with no minimum probability", () => {
    renderEvidence(scoreAccepted);

    expect(screen.getByTestId("decision-score")).toHaveTextContent(
      "1.99 on a 0–2 scale",
    );
    expect(screen.queryByText("Minimum")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("decision-minimum-probability"),
    ).not.toBeInTheDocument();
    const rows = screen.getAllByTestId(/^decision-row-/);
    expect(rows.map((row) => row.textContent?.slice(0, 4))).toEqual([
      "0Low",
      "1Med",
      "2Hig",
    ]);
  });

  it("shows a refusal explicitly instead of a false answer", () => {
    renderEvidence(refusedToElse);

    expect(screen.getByTestId("decision-tone")).toHaveTextContent("Refused");
    expect(screen.getByTestId("decision-refusal")).toHaveTextContent(
      "The provider gave no reason.",
    );
    expect(screen.getAllByText("Not reported").length).toBeGreaterThan(0);
  });

  it("separates an operational error sent to Else from uncertainty", () => {
    renderEvidence(malformedToElse);

    expect(screen.getByTestId("decision-tone")).toHaveTextContent(
      "Operational error",
    );
    expect(screen.getByTestId("decision-branch")).toHaveTextContent("Else");
    const failure = screen.getByTestId("decision-failure");
    expect(failure).toHaveTextContent("Malformed response");
    expect(failure).toHaveTextContent(
      "OpenAI sent an answer Langflow couldn't read (request req_1). Try again.",
    );
  });

  it("says the run stopped when the error action stops it", () => {
    renderEvidence(transportStopped);

    expect(screen.getByTestId("decision-branch")).toHaveTextContent(
      "None, the run stopped",
    );
    expect(screen.getByTestId("decision-failure")).toHaveTextContent(
      "Connection failed",
    );
    expect(screen.getByTestId("decision-model")).toHaveTextContent(
      "Not reported",
    );
  });

  it("shows an unknown failure category as the backend sent it", () => {
    renderEvidence({
      ...malformedToElse,
      error: { category: "quota_window", message: "" },
    });

    expect(screen.getByTestId("decision-failure")).toHaveTextContent(
      "quota_window",
    );
    expect(
      screen.queryByTestId("decision-failure-message"),
    ).not.toBeInTheDocument();
  });

  it("shows a Decision Model's question and no branch", () => {
    renderEvidence(decisionModelScore);

    expect(screen.getByTestId("decision-question")).toHaveTextContent(
      "How urgent is this message?",
    );
    expect(screen.queryByTestId("decision-branch")).not.toBeInTheDocument();
    expect(screen.getByTestId("decision-tone")).toHaveTextContent("Answered");
    expect(screen.getByTestId("decision-reason")).toHaveTextContent(
      "A Decision Model applies no routing policy.",
    );
  });

  it("renders supplied refusal text as text, never as markup", () => {
    const { container } = renderEvidence(decisionModelNoulRefusal);

    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByTestId("decision-refusal")).toHaveTextContent(
      "<img src=x onerror=alert(1)> I can't judge this content.",
    );
    expect(screen.getByTestId("decision-probability-true")).toHaveTextContent(
      "Not reported",
    );
  });

  it.each([
    ["accepted", acceptedChoice],
    ["uncertain", belowThreshold],
    ["score", scoreAccepted],
    ["refused", refusedToElse],
    ["malformed", malformedToElse],
    ["failed", transportStopped],
    ["decision model", decisionModelScore],
  ])("has no accessibility violations when %s", async (_label, value) => {
    const { container } = renderEvidence(value);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("is labelled by its heading for assistive technology", () => {
    renderEvidence(acceptedChoice);

    expect(screen.getByRole("region", { name: "Decision" })).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Options the model evaluated" }),
    ).toBeVisible();
  });
});
