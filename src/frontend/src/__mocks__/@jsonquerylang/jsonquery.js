// Mock for @jsonquerylang/jsonquery package to handle ES module in Jest
const jsonquery = jest.fn((data) => {
  // Simple mock implementation that returns the data as-is
  // In a real scenario, this would execute the JSON query
  return data;
});

module.exports = { jsonquery };
