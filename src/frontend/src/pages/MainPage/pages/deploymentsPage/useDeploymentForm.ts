import { useState } from "react";
import {
  type DeploymentType,
  type EnvVar,
  TOTAL_STEPS,
  type VariableScope,
} from "./constants";

export const useDeploymentForm = () => {
  const [newDeploymentOpen, setNewDeploymentOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [deploymentType, setDeploymentType] = useState<DeploymentType>("Agent");
  const [deploymentName, setDeploymentName] = useState("");
  const [deploymentDescription, setDeploymentDescription] = useState("");
  const [deploymentUrl, setDeploymentUrl] = useState("");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [variableScope, setVariableScope] = useState<VariableScope>("coarse");

  const resetForm = () => {
    setCurrentStep(1);
    setDeploymentName("");
    setDeploymentDescription("");
    setDeploymentUrl("");
    setDeploymentType("Agent");
    setSelectedItems(new Set());
    setEnvVars([]);
    setVariableScope("coarse");
  };

  const handleBack = () => setCurrentStep((s) => Math.max(1, s - 1));
  const handleNext = () => setCurrentStep((s) => Math.min(TOTAL_STEPS, s + 1));

  const handleSubmit = () => {
    setNewDeploymentOpen(false);
    resetForm();
  };

  const handleOpenChange = (open: boolean) => {
    setNewDeploymentOpen(open);
    if (!open) resetForm();
  };

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return {
    newDeploymentOpen,
    setNewDeploymentOpen,
    currentStep,
    deploymentType,
    setDeploymentType,
    deploymentName,
    setDeploymentName,
    deploymentDescription,
    setDeploymentDescription,
    deploymentUrl,
    setDeploymentUrl,
    selectedItems,
    setSelectedItems,
    envVars,
    setEnvVars,
    variableScope,
    setVariableScope,
    handleBack,
    handleNext,
    handleSubmit,
    handleOpenChange,
    toggleItem,
  };
};
