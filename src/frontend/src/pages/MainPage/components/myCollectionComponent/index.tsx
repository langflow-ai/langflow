import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  type: string;
};

const MyCollectionComponent = ({ type }: MyCollectionComponentProps) => {
  return (
    <>
      <HeaderTabsSearchComponent />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent key={type} type={type} />
      </div>
    </>
  );
};
export default MyCollectionComponent;
