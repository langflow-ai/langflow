import { useContext, useEffect, useState } from "react";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import { alertContext } from "../../../../contexts/alertContext";
import { getStoreComponents } from "../../../../controllers/API";
import { storeComponent } from "../../../../types/store";
import { MarketCardComponent } from "../../../StorePage/components/market-card";

export default function AddedComponents(): JSX.Element {
  const [data, setData] = useState<storeComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(null, null, true, "name", null, true)
      .then((res) => {
        setLoading(false);
        setData(res?.results ?? []);
      })
      .catch((err) => {
        setData([]);
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  return (
    <CardsWrapComponent isLoading={loading}>
      {data.map((item, idx) => (
        <MarketCardComponent key={idx} data={item} installable />
      ))}
    </CardsWrapComponent>
  );
}
