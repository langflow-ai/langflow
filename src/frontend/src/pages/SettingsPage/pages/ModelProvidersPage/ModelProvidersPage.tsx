import ModelProvidersHeader from "./components/ModelProvidersHeader";
import Providers from "./components/Providers";

const ModelProvidersPage = () => {
  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <ModelProvidersHeader />
      <Providers type="enabled" />
      <Providers type="available" />
    </div>
  );
};

export default ModelProvidersPage;
