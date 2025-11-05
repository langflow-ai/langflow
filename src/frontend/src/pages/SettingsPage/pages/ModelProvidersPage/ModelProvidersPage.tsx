import ModelProvidersHeader from "./components/model-providers-header";
import ProviderList from "./components/provider-list";

const ModelProvidersPage = () => {
  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <ModelProvidersHeader />
      <ProviderList type="enabled" />
      <ProviderList type="available" />
    </div>
  );
};

export default ModelProvidersPage;
