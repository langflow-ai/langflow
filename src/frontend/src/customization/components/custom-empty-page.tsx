import { EmptyPageCommunity } from "@/pages/MainPage/pages/empty-page";

export const CustomEmptyPageCommunity = ({
  setOpenModal,
}: {
  setOpenModal: (open: boolean) => void;
}) => {
  return <EmptyPageCommunity setOpenModal={setOpenModal} />;
};
export default CustomEmptyPageCommunity;
