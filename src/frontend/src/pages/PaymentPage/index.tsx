import Header from "../../components/headerComponent";
import {Button} from "@mui/material";
import {attemptSubscribe} from "../../controllers/API";
import {useContext} from "react";
import {alertContext} from "../../contexts/alertContext";

export default function PaymentPage() {
  const { setErrorData } = useContext(alertContext);

  const handleAttemptSubscribe = (priceId: string) => {
    attemptSubscribe(priceId)
      .then((location) => {
        window.location.replace(location);
      })
      .catch((error) => {
        setErrorData({
          title: "Error attempting subscribe"
        });
        return;
      });
  }

  return (
    <>
      <Header />
      <Button onClick={() => handleAttemptSubscribe("price_1NtcjoK6DS7qXvgo53NcXvTV")}>
        Subscribe for 1 month for $10
      </Button>
      <Button onClick={() => handleAttemptSubscribe("price_1NtckOK6DS7qXvgogdVkzdWO")}>
        Subscribe for 12 month for $100
      </Button>
    </>
  )
}