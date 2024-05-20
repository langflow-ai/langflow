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
      <div className="mt-5">
        <ComponentsComponent key={key} type={type} />
      </div>
    </>
  );
};
export default MyCollectionComponent;
