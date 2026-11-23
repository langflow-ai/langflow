import DeployButton from "@/components/core/flowToolbarComponent/components/deploy-button";

// OSS default: the canvas Deploy button as it is. An overlay can replace the
// whole button, which `useCustomDeployButton` cannot do while the
// `wxo_deployments` flag hides it.
export default function CustomDeployButton() {
  return <DeployButton />;
}
