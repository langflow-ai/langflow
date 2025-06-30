import { Switch } from "@/components/ui/switch";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";

type UsageDataFormComponentProps = {
  usageData: boolean;
  setUsageData: (usageData: boolean) => void;
};
const UsageDataFormComponent = ({
  usageData,
  setUsageData,
}: UsageDataFormComponentProps) => {
  return (
    <Card x-chunk="dashboard-04-chunk-1">
      <CardHeader>
        <CardTitle>Usage Data</CardTitle>
        <CardDescription>
          <div className="flex items-center justify-between gap-2">
            <span>Share anonymous usage data to help us improve Langflow.</span>
            <div className="relative bottom-3">
              <Switch onCheckedChange={setUsageData} checked={usageData} />
            </div>
          </div>
        </CardDescription>
      </CardHeader>
    </Card>
  );
};
export default UsageDataFormComponent;
