Cypress.on("uncaught:exception", (err, runnable) => {
  return false;
});

describe("Auto_login tests", () => {
  it("auto_login sign in", () => {
    cy.visit("http://localhost:3000/");

    cy.contains("New Project", { matchCase: false }).click();
  });

  it("auto_login block_admin", () => {
    cy.visit("http://localhost:3000/");

    cy.contains("New Project", { matchCase: false }).click();
    cy.wait(5000);

    cy.visit("http://localhost:3000/login");
    cy.contains("New Project", { matchCase: false }).click();
    cy.wait(5000);

    cy.visit("http://localhost:3000/admin");
    cy.contains("New Project", { matchCase: false }).click();
    cy.wait(5000);

    cy.visit("http://localhost:3000/admin/login");
    cy.contains("New Project", { matchCase: false }).click();
    cy.wait(5000);
  });
});
