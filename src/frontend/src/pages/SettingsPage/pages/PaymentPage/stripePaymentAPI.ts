import axios from "axios";
import { useMutation, useQuery } from "@tanstack/react-query";

// Types for the Stripe API
export interface CheckoutSessionRequest {
  priceId: string;
  successUrl: string;
  cancelUrl: string;
  customerEmail?: string;
}

export interface CreditPurchaseRequest {
  amount: number;
  successUrl: string;
  cancelUrl: string;
  customerEmail?: string;
}

export interface PaymentMethodResponse {
  id: string;
  brand: string;
  last4: string;
  expMonth: number;
  expYear: number;
  isDefault: boolean;
}

export interface SubscriptionResponse {
  id: string;
  status: "active" | "canceled" | "incomplete" | "past_due" | "trialing";
  currentPeriodEnd: string;
  planId: string;
  planName: string;
  amount: number;
  interval: "month" | "year";
}

export interface UserCreditsResponse {
  totalCredits: number;
  usedCredits: number;
  availableCredits: number;
}

// API functions
export const createCheckoutSession = async (data: CheckoutSessionRequest) => {
  const response = await axios.post<{ url: string }>("/api/payments/create-checkout-session", data);
  return response.data;
};

export const createCreditPurchaseSession = async (data: CreditPurchaseRequest) => {
  const response = await axios.post<{ url: string }>("/api/payments/create-credit-purchase", data);
  return response.data;
};

export const getUserPaymentMethods = async () => {
  const response = await axios.get<PaymentMethodResponse[]>("/api/payments/payment-methods");
  return response.data;
};

export const getUserSubscription = async () => {
  const response = await axios.get<SubscriptionResponse | null>("/api/payments/subscription");
  return response.data;
};

export const getUserCredits = async () => {
  const response = await axios.get<UserCreditsResponse>("/api/payments/credits");
  return response.data;
};

export const cancelSubscription = async () => {
  const response = await axios.post("/api/payments/cancel-subscription");
  return response.data;
};

// React Query hooks
export const useCreateCheckoutSession = () => {
  return useMutation({
    mutationFn: createCheckoutSession,
  });
};

export const useCreateCreditPurchase = () => {
  return useMutation({
    mutationFn: createCreditPurchaseSession,
  });
};

export const useGetUserPaymentMethods = () => {
  return useQuery({
    queryKey: ["paymentMethods"],
    queryFn: getUserPaymentMethods,
  });
};

export const useGetUserSubscription = () => {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: getUserSubscription,
  });
};

export const useGetUserCredits = () => {
  return useQuery({
    queryKey: ["credits"],
    queryFn: getUserCredits,
  });
};

export const useCancelSubscription = () => {
  return useMutation({
    mutationFn: cancelSubscription,
  });
};