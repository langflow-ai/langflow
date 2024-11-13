interface QueryParams {
  [key: string]: any;
}

const buildQueryStringUrl = (baseUrl: string, params: QueryParams): string => {
  const queryParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      if (typeof value === "boolean") {
        queryParams.append(key, value ? "true" : "false");
      } else {
        queryParams.append(key, value.toString());
      }
    }
  });

  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

export default buildQueryStringUrl;
