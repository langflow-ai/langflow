import { useContext } from "react";
import { CardComponent } from "../../../../components/cardComponent";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import { alertContext } from "../../../../contexts/alertContext";
import { FlowsContext } from "../../../../contexts/flowsContext";

export default function ComponentsComponent() {
  const { flows, removeFlow, uploadFlow, isLoading } = useContext(FlowsContext);
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
      isLoading={isLoading && flows.length == 0}
      dragMessage={"Drop your component here"}
    >
      {flows
        .filter((flow) => flow.is_component)
        .map((flow, idx) => (
          <CardComponent
            key={idx}
            data={flow}
            onDelete={() => {
              removeFlow(flow.id);
            }}
          />
        ))}
    </CardsWrapComponent>
  );
}
