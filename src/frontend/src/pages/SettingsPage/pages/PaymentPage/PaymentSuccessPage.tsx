import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useGetUserSubscription, useGetUserCredits } from "./stripePaymentAPI";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

export default function PaymentSuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isSubscription, setIsSubscription] = useState(true);
  const [creditAmount, setCreditAmount] = useState(0);
  
  const { data: subscription, isLoading: isLoadingSubscription } = useGetUserSubscription();
  const { data: credits, isLoading: isLoadingCredits } = useGetUserCredits();

  useEffect(() => {
    // Check if this was a credit purchase by looking at URL params
    const params = new URLSearchParams(location.search);
    const creditsParam = params.get("credits");
    
    if (creditsParam) {
      setIsSubscription(false);
      setCreditAmount(parseInt(creditsParam));
    }
  }, [location]);

  const goToDashboard = () => {
    navigate("/dashboard");
  };

  const goToPaymentSettings = () => {
    navigate("/settings/billing");
  };

  return (
    <div className="container mx-auto py-16 px-4 flex items-center justify-center min-h-screen">
      <div className="rounded-lg border p-6 max-w-md w-full">
        <div className="text-center pb-6">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <ForwardedIconComponent name="CheckCircle" className="h-8 w-8 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold">Payment Successful!</h2>
        </div>
        
        <div className="text-center space-y-4">
          {isSubscription ? (
            <>
              <p>
                Thank you for subscribing to LangFlow. Your subscription is now active.
              </p>
              {!isLoadingSubscription && subscription && (
                <div className="bg-muted p-4 rounded-lg">
                  <p className="font-medium">Subscription Details</p>
                  <p className="text-sm text-muted-foreground">
                    {subscription.planName} ({subscription.interval === "month" ? "Monthly" : "Yearly"})
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Renews on {new Date(subscription.currentPeriodEnd).toLocaleDateString()}
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <p>
                Thank you for purchasing credits. They have been added to your account.
              </p>
              <div className="bg-muted p-4 rounded-lg">
                <p className="font-medium">Credit Purchase</p>
                <p className="text-sm text-muted-foreground">
                  {creditAmount} credits added
                </p>
                {!isLoadingCredits && credits && (
                  <p className="text-sm text-muted-foreground">
                    Total available: {credits.availableCredits} credits
                  </p>
                )}
              </div>
            </>
          )}
        </div>
        
        <div className="flex flex-col space-y-2 mt-6">
          <button 
            onClick={goToDashboard}
            className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            Go to Dashboard
          </button>
          <button 
            onClick={goToPaymentSettings}
            className="inline-flex w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            View Billing Settings
          </button>
        </div>
      </div>
    </div>
  );
}