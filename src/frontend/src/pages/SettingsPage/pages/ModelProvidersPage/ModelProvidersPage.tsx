import { useState } from "react";
import ModelProvidersHeader from "./components/ModelProvidersHeader";
import Providers from "./components/Providers";

const ModelProvidersPage = () => {
  const [showExperimental, setShowExperimental] = useState(false);

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <ModelProvidersHeader
        showExperimental={showExperimental}
        onToggleExperimental={setShowExperimental}
      />
      <Providers type="enabled" showExperimental={showExperimental} />
      <Providers type="available" showExperimental={showExperimental} />
    </div>
  );
};

export default ModelProvidersPage;
