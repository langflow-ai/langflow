import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import type { DeploymentProvider, ProviderAccount } from "../types";
import ProviderCredentialsForm from "./provider-credentials-form";
import { RadioSelectItem } from "./radio-select-item";

const PROVIDERS: DeploymentProvider[] = [
  {
    id: "watsonx",
    type: "watsonx",
    name: "watsonx Orchestrate",
    icon: "WatsonxOrchestrate",
  },
];

type EnvironmentTab = "existing" | "new";

function EnvironmentTabToggle({
  activeTab,
  onTabChange,
}: {
  activeTab: EnvironmentTab;
  onTabChange: (tab: EnvironmentTab) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted p-1">
      <div className="grid grid-cols-2 gap-4">
        {(["existing", "new"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => onTabChange(tab)}
            className={cn(
              "rounded-lg py-2 text-sm transition-colors",
              activeTab === tab
                ? "bg-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab === "existing"
              ? "Choose existing environment"
              : "Add new environment"}
          </button>
        ))}
      </div>
    </div>
  );
}

function EnvironmentList({
  environments,
  selectedEnvironment,
  onSelectEnvironment,
}: {
  environments: ProviderAccount[];
  selectedEnvironment: ProviderAccount | null;
  onSelectEnvironment: (environment: ProviderAccount) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-sm text-muted-foreground">
        Select from your existing environments
      </span>
      <div
        role="radiogroup"
        aria-label="Existing environments"
        className="flex flex-col gap-3"
      >
        {environments.map((environment) => {
          const isSelected = selectedEnvironment?.id === environment.id;
          return (
            <RadioSelectItem
              key={environment.id}
              name="environment"
              value={environment.id}
              selected={isSelected}
              onChange={() => onSelectEnvironment(environment)}
              data-testid={`provider-item-${environment.id}`}
            >
              <span className="flex flex-col">
                <span className="text-sm font-medium leading-tight">
                  {environment.name}
                </span>
                <span className="text-sm leading-tight text-muted-foreground">
                  {typeof environment.provider_data?.url === "string"
                    ? environment.provider_data.url
                    : "—"}
                </span>
              </span>
            </RadioSelectItem>
          );
        })}
      </div>
    </div>
  );
}

export default function StepProvider() {
  const {
    setSelectedProvider,
    selectedInstance,
    setSelectedInstance,
    credentials,
    setCredentials,
  } = useDeploymentStepper();
  const { data: providerAccountsData } = useGetProviderAccounts({});
  const environments = providerAccountsData?.provider_accounts ?? [];

  useEffect(() => {
    setSelectedProvider(PROVIDERS[0]);
  }, [setSelectedProvider]);

  const provider = PROVIDERS[0];
  const hasEnvironments = environments.length > 0;

  const [environmentTab, setEnvironmentTab] = useState<EnvironmentTab>("new");

  useEffect(() => {
    if (environments.length > 0) {
      setEnvironmentTab("existing");
    }
  }, [environments.length]);

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      <h2 className="text-lg font-semibold">Provider</h2>

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3 rounded-lg border border-border bg-muted p-3">
          <ForwardedIconComponent
            name={provider.icon}
            className="h-8 w-8 text-foreground"
          />
          <span className="text-sm font-medium">{provider.name}</span>
          <Badge variant="purpleStatic" size="xq" className="shrink-0">
            Beta
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Configure your watsonx Orchestrate credentials below. Sign in or sign
          up to{" "}
          <a
            href="https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary hover:underline"
          >
            find your credentials
          </a>
          .
        </p>
      </div>

      {hasEnvironments ? (
        <div className="flex flex-col gap-4">
          <EnvironmentTabToggle
            activeTab={environmentTab}
            onTabChange={setEnvironmentTab}
          />
          {environmentTab === "existing" ? (
            <EnvironmentList
              environments={environments}
              selectedEnvironment={selectedInstance}
              onSelectEnvironment={setSelectedInstance}
            />
          ) : (
            <ProviderCredentialsForm
              credentials={credentials}
              onCredentialsChange={setCredentials}
              layout="two-column"
            />
          )}
        </div>
      ) : (
        <ProviderCredentialsForm
          credentials={credentials}
          onCredentialsChange={setCredentials}
          layout="two-column"
        />
      )}
    </div>
  );
}
