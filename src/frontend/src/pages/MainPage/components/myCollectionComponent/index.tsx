import ComponentsComponent from "../components";

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
      <ComponentsComponent key={key} is_component={is_component} />
    </>
  );
};
export default MyCollectionComponent;
