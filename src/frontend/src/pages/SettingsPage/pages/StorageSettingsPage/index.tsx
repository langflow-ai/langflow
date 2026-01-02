import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  useGetStorageSettings,
  useUpdateStorageSettings,
} from "@/controllers/API/queries/storage-settings";
import useAlertStore from "@/stores/alertStore";

export default function StorageSettingsPage() {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: storageSettings, isLoading } = useGetStorageSettings();
  const { mutate: updateSettings, isPending } = useUpdateStorageSettings();

  const [storageLocation, setStorageLocation] = useState<string>("Local");
  const [awsAccessKey, setAwsAccessKey] = useState<string>("");
  const [awsSecretKey, setAwsSecretKey] = useState<string>("");
  const [awsBucket, setAwsBucket] = useState<string>("");
  const [awsRegion, setAwsRegion] = useState<string>("");
  const [gdriveServiceAccountKey, setGdriveServiceAccountKey] =
    useState<string>("");
  const [gdriveFolderId, setGdriveFolderId] = useState<string>("");

  // Initialize form when data loads / refetches
  useEffect(() => {
    if (!storageSettings) return;
    setStorageLocation(storageSettings.default_storage_location ?? "Local");
    setAwsAccessKey(storageSettings.component_aws_access_key_id ?? "");
    setAwsSecretKey(storageSettings.component_aws_secret_access_key ?? "");
    setAwsBucket(storageSettings.component_aws_default_bucket ?? "");
    setAwsRegion(storageSettings.component_aws_default_region ?? "");
    setGdriveServiceAccountKey(
      storageSettings.component_google_drive_service_account_key ?? "",
    );
    setGdriveFolderId(
      storageSettings.component_google_drive_default_folder_id ?? "",
    );
  }, [storageSettings]);

  const handleSave = () => {
    const updates: any = {
      default_storage_location: storageLocation,
    };

    // Only include AWS settings if AWS is selected and fields are not masked
    if (storageLocation === "AWS") {
      if (awsAccessKey) updates.component_aws_access_key_id = awsAccessKey;
      if (awsSecretKey && !awsSecretKey.startsWith("*"))
        updates.component_aws_secret_access_key = awsSecretKey;
      if (awsBucket) updates.component_aws_default_bucket = awsBucket;
      if (awsRegion) updates.component_aws_default_region = awsRegion;
    }

    // Only include Google Drive settings if Google Drive is selected and fields are not masked
    if (storageLocation === "Google Drive") {
      if (gdriveServiceAccountKey && !gdriveServiceAccountKey.startsWith("*")) {
        updates.component_google_drive_service_account_key =
          gdriveServiceAccountKey;
      }
      if (gdriveFolderId)
        updates.component_google_drive_default_folder_id = gdriveFolderId;
    }

    updateSettings(updates, {
      onSuccess: () => {
        setSuccessData({ title: "Storage settings saved successfully" });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Error saving storage settings",
          list: [error?.response?.data?.detail || "Unknown error"],
        });
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div>Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="storage-settings-header"
          >
            Storage Settings
            <ForwardedIconComponent
              name="HardDrive"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure default storage location and credentials for file
            components.
          </p>
        </div>
      </div>

      <div className="flex w-full flex-col gap-6 overflow-y-auto">
        {/* Storage Location Selector */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="storage-location">Default Storage Location</Label>
          <Select value={storageLocation} onValueChange={setStorageLocation}>
            <SelectTrigger id="storage-location" className="w-full">
              <SelectValue placeholder="Select storage location" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Local">Local</SelectItem>
              <SelectItem value="AWS">AWS S3</SelectItem>
              <SelectItem value="Google Drive">Google Drive</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            This will be the default storage used by Read File and Write File
            components.
          </p>
        </div>

        {/* AWS Configuration */}
        {storageLocation === "AWS" && (
          <div className="flex flex-col gap-4 rounded-lg border p-4">
            <h3 className="text-sm font-semibold">AWS S3 Configuration</h3>

            <div className="flex flex-col gap-2">
              <Label htmlFor="aws-access-key">Access Key ID</Label>
              <Input
                id="aws-access-key"
                type="text"
                value={awsAccessKey}
                onChange={(e) => setAwsAccessKey(e.target.value)}
                placeholder="Enter AWS Access Key ID"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="aws-secret-key">Secret Access Key</Label>
              <Input
                id="aws-secret-key"
                type="password"
                value={awsSecretKey}
                onChange={(e) => setAwsSecretKey(e.target.value)}
                placeholder="Enter AWS Secret Access Key"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="aws-bucket">Default Bucket Name</Label>
              <Input
                id="aws-bucket"
                type="text"
                value={awsBucket}
                onChange={(e) => setAwsBucket(e.target.value)}
                placeholder="my-bucket"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="aws-region">AWS Region</Label>
              <Input
                id="aws-region"
                type="text"
                value={awsRegion}
                onChange={(e) => setAwsRegion(e.target.value)}
                placeholder="us-east-1"
              />
            </div>
          </div>
        )}

        {/* Google Drive Configuration */}
        {storageLocation === "Google Drive" && (
          <div className="flex flex-col gap-4 rounded-lg border p-4">
            <h3 className="text-sm font-semibold">
              Google Drive Configuration
            </h3>

            <div className="flex flex-col gap-2">
              <Label htmlFor="gdrive-service-key">
                Service Account Key (JSON)
              </Label>
              <Textarea
                id="gdrive-service-key"
                value={gdriveServiceAccountKey}
                onChange={(e) => setGdriveServiceAccountKey(e.target.value)}
                placeholder="Paste your Google Cloud service account JSON key here"
                rows={6}
                className="font-mono text-xs"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="gdrive-folder-id">Default Folder ID</Label>
              <Input
                id="gdrive-folder-id"
                type="text"
                value={gdriveFolderId}
                onChange={(e) => setGdriveFolderId(e.target.value)}
                placeholder="Enter Google Drive folder ID"
              />
              <p className="text-xs text-muted-foreground">
                Find this in the folder URL: drive.google.com/drive/folders/
                <strong>FOLDER_ID</strong>
              </p>
            </div>
          </div>
        )}

        {/* Save Button */}
        <div className="flex justify-end">
          <Button
            onClick={handleSave}
            disabled={isPending}
            variant="primary"
            data-testid="save-storage-settings"
          >
            {isPending ? "Saving..." : "Save Settings"}
          </Button>
        </div>
      </div>
    </div>
  );
}
