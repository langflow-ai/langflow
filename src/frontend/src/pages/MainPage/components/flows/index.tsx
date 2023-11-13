import { useContext } from "react";
import { Link } from "react-router-dom";
import { CardComponent } from "../../../../components/cardComponent";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";
import { alertContext } from "../../../../contexts/alertContext";
import { TabsContext } from "../../../../contexts/tabsContext";

export default function FlowsComponent() {
  const { uploadFlow, removeFlow, flows, isLoading } = useContext(TabsContext);
  const { setErrorData } = useContext(alertContext);

  const onFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      if (e.dataTransfer.files.item(0).type === "application/json") {
        uploadFlow(true, e.dataTransfer.files.item(0)!);
      } else {
        setErrorData({
          title: "Invalid file type",
          list: ["Please upload a JSON file"],
        });
      }
    }
  };
  return (
    <CardsWrapComponent
      onFileDrop={onFileDrop}
      dragMessage={"Drag your flow here"}
      isLoading={isLoading && flows.length == 0}
    >
      {flows
        .filter((flow) => !flow.is_component)
        .reverse()
        .map((flow, idx) => (
          <CardComponent
            key={idx}
            data={flow}
            button={
              <Link to={"/flow/" + flow.id}>
                <Button
                  variant="outline"
                  size="sm"
                  className="whitespace-nowrap "
                >
                  <IconComponent
                    name="ExternalLink"
                    className="main-page-nav-button"
                  />
                  Edit Flow
                </Button>
              </Link>
            }
            onDelete={() => {
              removeFlow(flow.id);
            }}
          />
        ))}
    </CardsWrapComponent>
  );
}
