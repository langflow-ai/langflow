import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";

import PageLayout from "../../components/pageLayout";

export default function GlobalVariablesPage() {
  return (
    <PageLayout
      title="Global Variables"
      description="Manage and assign global variables to default fields."
      button={
        <>
          <Button data-testid="api-key-button-store" variant="primary">
            <IconComponent name="Plus" className="mr-2 w-4" />
            Add Global Variables
          </Button>
        </>
      }
    >
      <div className="flex h-full w-full flex-col justify-between">Page</div>
    </PageLayout>
  );
}
