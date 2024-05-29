import { useNavigate } from "react-router-dom";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";

type EmptyComponentProps = {};

const EmptyComponent = ({}: EmptyComponentProps) => {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const navigate = useNavigate();

  return (
    <>
      <div className="mt-6 flex w-full items-center justify-center text-center">
        <div className="flex-max-width h-full flex-col">
          <div className="flex w-full flex-col gap-4">
            <div className="grid w-full gap-4 text-muted-foreground">
              Flows and components can be created using Langflow.
            </div>
            <div className="align-center flex w-full justify-center gap-1 ">
              <span className="text-muted-foreground">New?</span>
              <span className="transition-colors hover:text-muted-foreground">
                <button
                  onClick={() => {
                    addFlow(true).then((id) => {
                      navigate("/flow/" + id);
                    });
                  }}
                  className="underline"
                >
                  Start Here
                </button>
                .
              </span>
              <span className="animate-pulse">🚀</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
export default EmptyComponent;
