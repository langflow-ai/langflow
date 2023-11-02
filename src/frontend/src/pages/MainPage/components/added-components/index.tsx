import { useContext, useEffect, useState } from "react";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import { alertContext } from "../../../../contexts/alertContext";
import {
  getStoreComponents,
  getStoreSavedComponents,
} from "../../../../controllers/API";
import { storeComponent } from "../../../../types/store";
import { MarketCardComponent } from "../../../StorePage/components/market-card";

export default function AddedComponents(): JSX.Element {
  const [data, setData] = useState<storeComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(0, 10000)
      .then((res) => {
        handleAddedOnly(res);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  function handleAddedOnly(components: storeComponent[]) {
    getStoreSavedComponents()
      .then((res) => {
        const idSet = new Set(res.map((item) => item.id));
        const filteredArray = components.filter((item) => idSet.has(item.id));
        setData(filteredArray);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  }

  return (
    <CardsWrapComponent isLoading={loading}>
      {data
        .filter(
          (f) =>
            Array.from(filteredCategories).length === 0 ||
            filteredCategories.has(f.is_component)
        )
        .map((item, idx) => (
          <MarketCardComponent key={idx} data={item} />
        ))}
    </CardsWrapComponent>
  );
}
