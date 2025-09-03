// Mock for vanilla-jsoneditor package
const createJSONEditor = jest.fn(() => ({
  set: jest.fn(),
  get: jest.fn(() => ({})),
  getText: jest.fn(() => "{}"),
  setText: jest.fn(),
  update: jest.fn(),
  refresh: jest.fn(),
  focus: jest.fn(),
  destroy: jest.fn(),
  updateProps: jest.fn(),
  transform: jest.fn(),
  validate: jest.fn(),
  acceptAutoRepair: jest.fn(),
  scrollTo: jest.fn(),
  findElement: jest.fn(),
}));

module.exports = {
  createJSONEditor,
  Mode: {
    text: "text",
    tree: "tree",
  },
};
