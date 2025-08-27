import { useEffect, useState } from "react";
import { useDarkStore } from "@/stores/darkStore";
import IconComponent from "../../components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import BaseModal from "../baseModal";
import { api } from "@/controllers/API/api";

interface SandboxSupportedComponent {
  class_name: string;
  display_name: string;
  notes: string;
  force_sandbox: boolean;
}

interface SandboxInfoResponse {
  sandbox_enabled: boolean;
  components: SandboxSupportedComponent[];
}

interface SandboxInfoModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

export default function SandboxInfoModal({
  open,
  setOpen,
}: SandboxInfoModalProps) {
  const isDark = useDarkStore((state) => state.dark);
  const [sandboxInfo, setSandboxInfo] = useState<SandboxInfoResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      fetchSandboxInfo();
    }
  }, [open]);

  const fetchSandboxInfo = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/v1/sandbox/supported-components");
      // Sort components alphabetically by display name
      const sortedComponents = (response.data.components || []).sort((a: SandboxSupportedComponent, b: SandboxSupportedComponent) => 
        a.display_name.localeCompare(b.display_name)
      );
      setSandboxInfo({
        ...response.data,
        components: sortedComponents
      });
    } catch (error) {
      console.error("Failed to fetch sandbox info:", error);
      setSandboxInfo({
        sandbox_enabled: false,
        components: []
      });
    } finally {
      setLoading(false);
    }
  };

  const ComponentCard = ({ component }: { component: SandboxSupportedComponent }) => (
    <div className="group relative overflow-hidden transition-all duration-200">
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-gray-300 dark:border-gray-200">
            <IconComponent name={component.icon} className="h-5 w-5 text-gray-500 dark:text-gray-200" />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-1">
            <h4 className="font-semibold text-sm text-foreground">
              {component.display_name}
            </h4>
            {component.force_sandbox && (
              <Badge variant="primary" className="text-xs px-2 py-0.5 border-orange-200 bg-orange-100 text-orange-800 dark:bg-purple-800 dark:border-purple-900 dark:text-purple-200">
                <IconComponent name="Lock" className="w-3 h-3 mr-1" />
                Force Sandbox
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {component.notes}
          </p>
        </div>
      </div>
    </div>
  );

  return (
    <BaseModal open={open} setOpen={setOpen} size="small-h-full">
      <BaseModal.Header description="When sandboxing is enabled, component security is enforced through code verification.">
        <span className="pr-2">Sandbox Information</span>
        <IconComponent name="ShieldAlert" className="w-6 h-6 text-primary" />
      </BaseModal.Header>

      <BaseModal.Content>
        <div className="space-y-6">
          {/* How Sandboxing Works */}
          <div className="space-y-4">
            <h3 className="font-semibold flex items-center space-x-2">
              <span>How It Works</span>
            </h3>

            <div className="space-y-3 text-sm text-muted-foreground">
              <ul className="space-y-2 ml-4">
                <li className="flex items-start space-x-2">
                  <IconComponent name="Check" className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                  <span><strong>Unmodified components</strong> run with full system access when their code matches known signatures</span>
                </li>
                <li className="flex items-start space-x-2">
                  <IconComponent name="ShieldAlert" className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span><strong>Sandbox-compatible components</strong> can have their code modified, but will be considered untrusted, and will run with security restrictions</span>
                </li>
                <li className="flex items-start space-x-2">
                  <IconComponent name="Lock" className="w-4 h-4 text-orange-500 dark:text-purple-400 mt-0.5 flex-shrink-0" />
                  <span><strong>Forced-sandboxing</strong> is applied to sensitive components (e.g. Custom Components)</span>
                </li>
                <li className="flex items-start space-x-2">
                  <IconComponent name="X" className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                  <span><strong>Incompatible components</strong> cannot be modified from the frontend and will be blocked by server if otherwise manipulated</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Sandbox-Compatible Components */}
          <div className="space-y-4">
            <h3 className="font-semibold flex items-center space-x-2">
              <span>Sandbox-Compatible Components</span>
            </h3>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <IconComponent name="Loader2" className="w-6 h-6 animate-spin" />
                <span className="ml-2 text-sm text-muted-foreground">Loading components...</span>
              </div>
            ) : sandboxInfo?.components && sandboxInfo.components.length > 0 ? (
              <div className="flex flex-col gap-y-4">
                {sandboxInfo.components.map((component) => (
                  <ComponentCard key={component.class_name} component={component} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <IconComponent name="ShieldAlert" className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No sandbox-compatible components found</p>
              </div>
            )}
          </div>
        </div>
      </BaseModal.Content>

      <BaseModal.Footer>
        <Button
          onClick={() => setOpen(false)}
          variant="outline"
        >
          Close
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}