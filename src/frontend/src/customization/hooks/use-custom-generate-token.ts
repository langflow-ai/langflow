export const useGenerateToken = (): any => {
  const tokenFunction = (() => {
    return "token";
  }) as any;
  tokenFunction.token = "token";
  return tokenFunction;
};
