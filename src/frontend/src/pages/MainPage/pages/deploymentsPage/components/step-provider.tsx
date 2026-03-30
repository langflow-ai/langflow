import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import type {
  DeploymentProvider,
  ProviderAccount,
  ProviderCredentials,
} from "../types";
import { RadioSelectItem } from "./radio-select-item";

// TODO: replace with real API data when multi-provider support is added
const PROVIDERS: DeploymentProvider[] = [
  {
    id: "watsonx",
    type: "watsonx",
    name: "watsonx Orchestrate",
    icon: "Bot",
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
            >
              <span className="flex flex-col">
                <span className="text-sm font-medium leading-tight">
                  {environment.name}
                </span>
                <span className="text-sm leading-tight text-muted-foreground">
                  {environment.provider_url}
                </span>
              </span>
            </RadioSelectItem>
          );
        })}
      </div>
    </div>
  );
}

function NewEnvironmentForm({
  provider,
  credentials,
  onCredentialsChange,
}: {
  provider: DeploymentProvider;
  credentials: ProviderCredentials;
  onCredentialsChange: (credentials: ProviderCredentials) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Configure your {provider.name} credentials below. Sign in or sign up to{" "}
        <span className="font-semibold text-foreground">
          find your credentials
        </span>
        .
      </p>
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          Name <span className="text-destructive">*</span>
        </span>
        <Input
          type="text"
          placeholder="e.g. Production"
          className="bg-muted"
          value={credentials.name}
          onChange={(e) =>
            onCredentialsChange({
              ...credentials,
              name: e.target.value,
            })
          }
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col">
          <span className="pb-2 text-sm font-medium">
            API Key <span className="text-destructive">*</span>
          </span>
          <Input
            type="password"
            placeholder="Enter your API key"
            className="bg-muted"
            value={credentials.api_key}
            onChange={(e) =>
              onCredentialsChange({
                ...credentials,
                api_key: e.target.value,
              })
            }
          />
        </div>
        <div className="flex flex-col">
          <span className="pb-2 text-sm font-medium">
            Service Environment URL <span className="text-destructive">*</span>
          </span>
          <Input
            type="url"
            placeholder="https://api.example.com"
            className="bg-muted"
            value={credentials.provider_url}
            onChange={(e) =>
              onCredentialsChange({
                ...credentials,
                provider_url: e.target.value,
              })
            }
          />
        </div>
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
  const environments = providerAccountsData?.providers ?? [];

  useEffect(() => {
    setSelectedProvider(PROVIDERS[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setSelectedProvider]);

  const provider = PROVIDERS[0];
  const hasEnvironments = environments.length > 0;

  const [environmentTab, setEnvironmentTab] = useState<EnvironmentTab>("new");
  const hasSetTabRef = useRef(false);

  if (!hasSetTabRef.current && environments.length > 0) {
    hasSetTabRef.current = true;
    setEnvironmentTab("existing");
  }

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      <h2 className="text-lg font-semibold">Provider</h2>

      <div className="flex items-center gap-3 rounded-lg border border-border bg-muted p-3">
        <ForwardedIconComponent
          name={provider.icon}
          className="h-8 w-8 text-foreground"
        />
        <span className="text-sm font-medium">{provider.name}</span>
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
            <NewEnvironmentForm
              provider={provider}
              credentials={credentials}
              onCredentialsChange={setCredentials}
            />
          )}
        </div>
      ) : (
        <NewEnvironmentForm
          provider={provider}
          credentials={credentials}
          onCredentialsChange={setCredentials}
        />
      )}
    </div>
  );
}
