import { Route, Routes } from "react-router-dom";
import StripePaymentPage from "./index";
import PaymentSuccessPage from "./PaymentSuccessPage";
import BillingSettingsPage from "./BillingSettingsPage";

export default function PaymentRoutes() {
  return (
    <Routes>
      <Route path="/" element={<StripePaymentPage />} />
      <Route path="/success" element={<PaymentSuccessPage />} />
      <Route path="/settings/billing" element={<BillingSettingsPage />} />
    </Routes>
  );
}