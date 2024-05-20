import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  key: string;
  type: string;
};

const MyCollectionComponent = ({ key, type }: MyCollectionComponentProps) => {
  return (
    <>
      <HeaderTabsSearchComponent />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent key={key} type={type} />
      </div>
    </>
  );
};
export default MyCollectionComponent;
