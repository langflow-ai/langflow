import ModelProviderHeader from "./components/ModelProviderHeader";
import Providers from "./components/Providers";

const ModelProvidersPage = () => {
  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <ModelProviderHeader />
      <Providers type="enabled" />
      <Providers type="available" />
    </div>
  );
};

export default ModelProvidersPage;
