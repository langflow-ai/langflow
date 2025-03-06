import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import * as Tabs from "@radix-ui/react-tabs";
// Import cụ thể từ RadioGroup thay vì namespace để tránh lỗi TypeScript
import { Root as RadioGroupRoot, Item as RadioGroupItem } from "@radix-ui/react-radio-group";
import * as Form from "@radix-ui/react-form";
import { Root as LabelRoot } from "@radix-ui/react-label";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useAlertStore from "@/stores/alertStore";

// Mock API hooks - would need to be implemented with real Stripe integration
const useCreateCheckoutSession = () => {
  return {
    mutateAsync: async (data: any) => {
      // In a real implementation, this would call your backend to create a Stripe checkout session
      console.log("Creating checkout session with data:", data);
      // Simulate redirect to Stripe checkout
      return { url: `https://checkout.stripe.com/mock-session/${data.priceId}` };
    },
    isLoading: false,
  };
};

const useCreateCreditPurchase = () => {
  return {
    mutateAsync: async (data: any) => {
      // In a real implementation, this would call your backend to create a Stripe payment intent
      console.log("Creating credit purchase with data:", data);
      // Simulate redirect to Stripe checkout
      return { url: `https://checkout.stripe.com/mock-session/credit-${data.amount}` };
    },
    isLoading: false,
  };
};

type PlanDuration = "monthly" | "yearly";

interface SubscriptionPlan {
  id: string;
  name: string;
  price: {
    monthly: number;
    yearly: number;
  };
  features: string[];
  popular?: boolean;
  priceIds: {
    monthly: string;
    yearly: string;
  };
}

export default function StripePaymentPage() {
  const navigate = useNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [planDuration, setPlanDuration] = useState<PlanDuration>("monthly");
  const [creditAmount, setCreditAmount] = useState<number>(10);
  
  const { mutateAsync: createCheckoutSession, isLoading: isCreatingCheckout } = useCreateCheckoutSession();
  const { mutateAsync: createCreditPurchase, isLoading: isCreatingCreditPurchase } = useCreateCreditPurchase();

  // Subscription plans data
  const plans: SubscriptionPlan[] = [
    {
      id: "basic",
      name: "Basic",
      price: {
        monthly: 19,
        yearly: 19 * 11, // 12 months with 1 month free
      },
      features: [
        "5 flows",
        "100 API calls per day",
        "Basic components",
        "Community support",
      ],
      priceIds: {
        monthly: "price_basic_monthly",
        yearly: "price_basic_yearly"
      }
    },
    {
      id: "pro",
      name: "Professional",
      price: {
        monthly: 39,
        yearly: 39 * 11, // 12 months with 1 month free
      },
      features: [
        "20 flows",
        "500 API calls per day",
        "All components",
        "Priority support",
        "Team collaboration",
      ],
      popular: true,
      priceIds: {
        monthly: "price_pro_monthly",
        yearly: "price_pro_yearly"
      }
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: {
        monthly: 99,
        yearly: 99 * 11, // 12 months with 1 month free
      },
      features: [
        "Unlimited flows",
        "Unlimited API calls",
        "Custom components",
        "Premium support",
        "Advanced analytics",
        "SSO authentication",
      ],
      priceIds: {
        monthly: "price_enterprise_monthly",
        yearly: "price_enterprise_yearly"
      }
    },
  ];

  const handleSubscribe = async (plan: SubscriptionPlan) => {
    try {
      const priceId = planDuration === "monthly" 
        ? plan.priceIds.monthly 
        : plan.priceIds.yearly;
      
      const session = await createCheckoutSession({
        priceId,
        successUrl: `${window.location.origin}/payment/success`,
        cancelUrl: `${window.location.origin}/payment`,
      });
      
      // Redirect to Stripe checkout
      window.location.href = session.url;
    } catch (error) {
      console.error("Error creating checkout session:", error);
      setErrorData({
        title: "Payment Error",
        list: ["Unable to process your subscription. Please try again later."],
      });
    }
  };

  const handleCreditPurchase = async () => {
    try {
      if (creditAmount < 10) {
        setErrorData({
          title: "Invalid Amount",
          list: ["Minimum credit purchase is 10 credits."],
        });
        return;
      }
      
      const session = await createCreditPurchase({
        amount: creditAmount,
        successUrl: `${window.location.origin}/payment/success?credits=${creditAmount}`,
        cancelUrl: `${window.location.origin}/payment`,
      });
      
      // Redirect to Stripe checkout
      window.location.href = session.url;
    } catch (error) {
      console.error("Error creating credit purchase:", error);
      setErrorData({
        title: "Payment Error",
        list: ["Unable to process your credit purchase. Please try again later."],
      });
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <Tabs.Root defaultValue="subscription" className="mx-auto max-w-5xl">
        <Tabs.List className="flex space-x-1 border-b mb-8">
          <Tabs.Trigger 
            value="subscription" 
            className="px-4 py-2 flex-1 text-center hover:text-primary data-[state=active]:text-primary data-[state=active]:border-b-2 data-[state=active]:border-primary"
          >
            Subscription Plans
          </Tabs.Trigger>
          <Tabs.Trigger 
            value="credits" 
            className="px-4 py-2 flex-1 text-center hover:text-primary data-[state=active]:text-primary data-[state=active]:border-b-2 data-[state=active]:border-primary"
          >
            Purchase Credits
          </Tabs.Trigger>
        </Tabs.List>
        
        <Tabs.Content value="subscription" className="space-y-6">
          <div className="flex justify-center mb-6">
            {/* Sử dụng RadioGroupRoot thay vì RadioGroup.Root */}
            <RadioGroupRoot 
              className="flex items-center space-x-2 bg-muted p-1 rounded-lg"
              value={planDuration}
              onValueChange={(value) => setPlanDuration(value as PlanDuration)}
            >
              <div className="flex items-center space-x-2 px-3 py-2">
                {/* Sử dụng RadioGroupItem thay vì RadioGroup.Item */}
                <RadioGroupItem 
                  value="monthly" 
                  id="monthly"
                  className="sr-only"
                />
                <LabelRoot 
                  htmlFor="monthly" 
                  className={`cursor-pointer rounded-md px-2 py-1 ${planDuration === "monthly" ? "bg-background shadow-sm" : ""}`}
                >
                  Monthly
                </LabelRoot>
              </div>
              <div className="flex items-center space-x-2 px-3 py-2">
                <RadioGroupItem 
                  value="yearly" 
                  id="yearly"
                  className="sr-only"
                />
                <LabelRoot 
                  htmlFor="yearly" 
                  className={`cursor-pointer rounded-md px-2 py-1 flex items-center ${planDuration === "yearly" ? "bg-background shadow-sm" : ""}`}
                >
                  Yearly
                  <span className="ml-2 inline-flex h-5 items-center rounded-full bg-green-50 px-2 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                    1 month free
                  </span>
                </LabelRoot>
              </div>
            </RadioGroupRoot>
          </div>
          
          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <motion.div
                key={plan.id}
                whileHover={{ y: -5 }}
                transition={{ duration: 0.2 }}
              >
                <div 
                  className={`flex h-full flex-col rounded-lg border p-6 ${plan.popular ? "border-primary shadow-md" : "border-border"}`}
                >
                  <div className="mb-4">
                    {plan.popular && (
                      <span className="inline-flex h-5 items-center rounded-full bg-primary/10 px-2 text-xs font-medium text-primary mb-2">
                        Most Popular
                      </span>
                    )}
                    <h3 className="text-lg font-medium">{plan.name}</h3>
                    <div className="flex items-baseline mt-2">
                      <span className="text-3xl font-bold">${planDuration === "monthly" ? plan.price.monthly : plan.price.yearly}</span>
                      <span className="ml-1 text-muted-foreground">/{planDuration === "monthly" ? "month" : "year"}</span>
                    </div>
                  </div>
                  
                  <div className="flex-grow">
                    <ul className="space-y-2">
                      {plan.features.map((feature, i) => (
                        <li key={i} className="flex items-center">
                          <ForwardedIconComponent name="CheckCircle2" className="h-4 w-4 mr-2 text-green-500" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  <div className="mt-6">
                    <button 
                      className={`inline-flex w-full items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 ${plan.popular 
                        ? "bg-primary text-primary-foreground shadow hover:bg-primary/90" 
                        : "border border-input bg-background hover:bg-accent hover:text-accent-foreground"}`}
                      onClick={() => handleSubscribe(plan)}
                      disabled={isCreatingCheckout}
                    >
                      {isCreatingCheckout ? (
                        <>
                          <ForwardedIconComponent name="Loader2" className="mr-2 h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        `Subscribe Now`
                      )}
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </Tabs.Content>
        
        <Tabs.Content value="credits" className="space-y-4">
          <div className="rounded-lg border p-6">
            <div className="mb-4">
              <h3 className="text-lg font-medium">Purchase Credits</h3>
              <p className="text-sm text-muted-foreground">
                Credits can be used for pay-as-you-go usage. 10 credits = $1 USD.
              </p>
            </div>
            
            <div className="space-y-4">
              <div className="flex flex-col space-y-2">
                <LabelRoot htmlFor="credit-amount">Amount of Credits</LabelRoot>
                <div className="flex items-center space-x-4">
                  <button 
                    className="inline-flex items-center justify-center rounded-md border border-input bg-background p-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
                    onClick={() => setCreditAmount(Math.max(10, creditAmount - 10))}
                  >
                    <ForwardedIconComponent name="Minus" className="h-4 w-4" />
                  </button>
                  
                  <input
                    id="credit-amount"
                    type="number"
                    min="10"
                    step="10"
                    value={creditAmount}
                    onChange={(e) => setCreditAmount(parseInt(e.target.value) || 10)}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm text-center shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  
                  <button 
                    className="inline-flex items-center justify-center rounded-md border border-input bg-background p-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
                    onClick={() => setCreditAmount(creditAmount + 10)}
                  >
                    <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                  </button>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
                <div className="flex items-center">
                  <ForwardedIconComponent name="CreditCard" className="h-5 w-5 mr-2" />
                  <span>Total Cost</span>
                </div>
                <div className="text-xl font-bold">${(creditAmount / 10).toFixed(2)} USD</div>
              </div>
            </div>
            
            <div className="mt-6">
              <button 
                className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                onClick={handleCreditPurchase}
                disabled={isCreatingCreditPurchase}
              >
                {isCreatingCreditPurchase ? (
                  <>
                    <ForwardedIconComponent name="Loader2" className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  `Purchase Credits`
                )}
              </button>
            </div>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}