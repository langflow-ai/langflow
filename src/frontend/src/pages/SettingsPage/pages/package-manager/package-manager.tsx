import { useState } from "react";
import ForwardedIconComponent from "../../../../components/common/genericIconComponent";
import { Button } from "../../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../../../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../components/ui/select";
import useAlertStore from "../../../../stores/alertStore";

interface PackageItem {
  id: string;
  name: string;
  description: string;
  installed: boolean;
}

const AVAILABLE_PACKAGES = [
  {
    id: "audio",
    name: "Audio",
    description: "Audio processing capabilities with webrtcvad",
  },
  {
    id: "postgresql",
    name: "PostgreSQL",
    description: "PostgreSQL database support with psycopg2 and psycopg",
  },
  {
    id: "local",
    name: "Local LLMs",
    description:
      "Local language models support (llama-cpp-python, sentence-transformers, ctransformers)",
  },
  {
    id: "all",
    name: "All Packages",
    description: "All optional packages combined",
  },
];

export default function PackageManagerPage() {
  const [installedPackages, setInstalledPackages] = useState<PackageItem[]>([
    {
      id: "audio",
      name: "Audio",
      description: "Audio processing capabilities with webrtcvad",
      installed: true,
    },
  ]);

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState<string>("");
  const [isInstalling, setIsInstalling] = useState(false);
  const [isUninstalling, setIsUninstalling] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const availableToInstall = AVAILABLE_PACKAGES.filter(
    (pkg) => !installedPackages.some((installed) => installed.id === pkg.id),
  );

  const handleInstallPackage = () => {
    if (!selectedPackage) return;

    const packageToInstall = AVAILABLE_PACKAGES.find(
      (pkg) => pkg.id === selectedPackage,
    );
    if (!packageToInstall) return;

    setIsInstalling(true);
    setIsAddDialogOpen(false);

    // Simulate installation process with 5-second timeout
    setTimeout(() => {
      setInstalledPackages((prev) => [
        ...prev,
        { ...packageToInstall, installed: true },
      ]);
      setSelectedPackage("");
      setIsInstalling(false);

      setSuccessData({
        title: `${packageToInstall.name} installed successfully`,
      });
    }, 5000);
  };

  const handleUninstallPackage = (packageId: string) => {
    const packageToRemove = installedPackages.find(
      (pkg) => pkg.id === packageId,
    );
    if (!packageToRemove) return;

    setIsUninstalling(true);

    // Simulate uninstallation process with 5-second timeout
    setTimeout(() => {
      setInstalledPackages((prev) =>
        prev.filter((pkg) => pkg.id !== packageId),
      );
      setIsUninstalling(false);

      setSuccessData({
        title: `${packageToRemove.name} uninstalled successfully`,
      });
    }, 5000);
  };

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Package Manager
            <ForwardedIconComponent
              name="Package"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage optional packages to extend Langflow functionality.
          </p>
        </div>
        <div>
          <Dialog
            open={isAddDialogOpen}
            onOpenChange={(open) =>
              !isInstalling && !isUninstalling && setIsAddDialogOpen(open)
            }
          >
            <DialogTrigger asChild>
              <Button
                variant="primary"
                className="flex gap-2"
                disabled={isInstalling || isUninstalling}
              >
                <ForwardedIconComponent name="Plus" className="w-4" />
                Add Package
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Install Package</DialogTitle>
                <DialogDescription>
                  Select a package to install from the available options.
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <Select
                  value={selectedPackage}
                  onValueChange={setSelectedPackage}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a package to install" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableToInstall.map((pkg) => (
                      <SelectItem key={pkg.id} value={pkg.id}>
                        <div className="flex flex-col">
                          <span className="font-medium">{pkg.name}</span>
                          <span className="text-xs text-muted-foreground">
                            {pkg.description}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setIsAddDialogOpen(false)}
                  disabled={isInstalling || isUninstalling}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleInstallPackage}
                  disabled={!selectedPackage || isInstalling || isUninstalling}
                >
                  Install
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Installation Loading Dialog */}
          <Dialog open={isInstalling} onOpenChange={() => {}}>
            <DialogContent hideTitle closeButtonClassName="hidden">
              <div className="flex flex-col items-center gap-6 py-8">
                <div className="relative">
                  <div className="h-12 w-12 animate-spin rounded-full border-4 border-muted border-t-primary"></div>
                  <ForwardedIconComponent
                    name="Package"
                    className="absolute inset-0 m-auto h-6 w-6 text-primary"
                  />
                </div>
                <div className="text-center space-y-2">
                  <h3 className="text-lg font-semibold">Installing Package</h3>
                  <p className="text-sm text-muted-foreground">
                    Please wait while the package is being installed...
                  </p>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Uninstallation Loading Dialog */}
          <Dialog open={isUninstalling} onOpenChange={() => {}}>
            <DialogContent hideTitle closeButtonClassName="hidden">
              <div className="flex flex-col items-center gap-6 py-8">
                <div className="relative">
                  <div className="h-12 w-12 animate-spin rounded-full border-4 border-muted border-t-destructive"></div>
                  <ForwardedIconComponent
                    name="Trash2"
                    className="absolute inset-0 m-auto h-6 w-6 text-destructive"
                  />
                </div>
                <div className="text-center space-y-2">
                  <h3 className="text-lg font-semibold">
                    Uninstalling Package
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Please wait while the package is being removed...
                  </p>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-6 pb-8">
        <div>
          <h3 className="text-base font-medium mb-4">Installed Packages</h3>
          {installedPackages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ForwardedIconComponent
                name="Package"
                className="h-12 w-12 text-muted-foreground mb-4"
              />
              <h3 className="text-lg font-medium">No packages installed</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Install optional packages to extend Langflow functionality.
              </p>
              <Button
                onClick={() => setIsAddDialogOpen(true)}
                variant="outline"
                disabled={isInstalling || isUninstalling}
              >
                <ForwardedIconComponent name="Plus" className="w-4 mr-2" />
                Install First Package
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {installedPackages.map((pkg) => (
                <div
                  key={pkg.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-start space-x-4">
                    <ForwardedIconComponent
                      name="Package"
                      className="h-5 w-5 mt-0.5 text-green-600"
                    />
                    <div>
                      <h4 className="font-medium">{pkg.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {pkg.description}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleUninstallPackage(pkg.id)}
                    disabled={isInstalling || isUninstalling}
                  >
                    <ForwardedIconComponent
                      name="Trash2"
                      className="w-4 mr-2"
                    />
                    Uninstall
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
