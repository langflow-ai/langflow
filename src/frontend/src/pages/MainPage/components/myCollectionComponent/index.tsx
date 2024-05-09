import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  key: string;
  is_component: boolean;
};

const MyCollectionComponent = ({
  key,
  is_component,
}: MyCollectionComponentProps) => {
  return (
    <>
      <HeaderTabsSearchComponent />
      <div className="mt-5">
        <ComponentsComponent key={key} is_component={is_component} />
      </div>
    </>
  );
};
export default MyCollectionComponent;
