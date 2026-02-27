import React from "react";

interface StepProps {
  title: string;
  children: React.ReactNode;
}

export function Step({ title, children }: StepProps) {
  return (
    <div className="step-item">
      <div className="step-header">
        <div className="step-number" />
        <h3 className="step-title">{title}</h3>
      </div>
      <div className="step-content">{children}</div>
    </div>
  );
}

interface StepsProps {
  children: React.ReactNode;
}

export default function Steps({ children }: StepsProps) {
  return <div className="steps-container">{children}</div>;
}
