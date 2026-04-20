@errors
Feature: Not Found Errors (404)
  As an authenticated user
  I want to receive proper 404 errors
  So that I know when resources don't exist

  Background:
    Given the API is available
    And I am logged in as "user@example.com"

  @confab
  Scenario: Get non-existent confab
    When I get confab with ID 99999
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @confab
  Scenario: Update non-existent confab
    When I update confab with ID 99999 with:
      | name      |
      | New Name  |
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @confab
  Scenario: Delete non-existent confab
    When I delete confab with ID 99999
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @documents
  Scenario: Get documents for non-existent confab
    When I list documents for confab ID 99999
    Then the response status should be 404

  @documents
  Scenario: Upload document to non-existent confab
    When I upload a document to confab ID 99999
    Then the response status should be 404

  @documents
  Scenario: Get non-existent document
    Given I have created a confab named "Test Agent"
    When I get document ID 99999 from the confab
    Then the response status should be 404
    And the response should contain error "Document not found"

  @documents
  Scenario: Archive non-existent document
    Given I have created a confab named "Test Agent"
    When I archive document ID 99999 from the confab
    Then the response status should be 404

  @documents
  Scenario: Get non-existent document version
    Given I have created a confab named "Test Agent"
    And the confab has a document "guide.pdf" with 2 versions
    When I get version 10 of the document
    Then the response status should be 404
    And the response should contain error "Version not found"

  @github
  Scenario: Refresh definition files for non-existent confab
    When I refresh definition files for confab ID 99999
    Then the response status should be 404

  @github
  Scenario: Commit definition files for non-existent confab
    When I commit definition files for confab ID 99999
    Then the response status should be 404

  @conversations
  Scenario: Resume conversation for non-existent confab
    When I resume foreman conversation for confab ID 99999
    Then the response status should be 404

  @conversations
  Scenario: Get non-existent thread
    When I get thread with ID 99999
    Then the response status should be 404

  Scenario: Invalid endpoint returns 404
    When I make a GET request to "/nonexistent/endpoint"
    Then the response status should be 404
