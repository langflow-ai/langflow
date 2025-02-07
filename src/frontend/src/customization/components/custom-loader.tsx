import LoadingComponent from "@/components/common/loadingComponent";
import { ENABLE_DATASTAX_LANGFLOW } from "../feature-flags";

const CustomLoader = () => {
  return ENABLE_DATASTAX_LANGFLOW ? <></> : <LoadingComponent remSize={30} />;
};

export default CustomLoader;
