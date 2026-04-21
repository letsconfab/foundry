@errors @validation
Feature: Validation Errors (422)
  As the system
  I want to reject invalid input
  So that data integrity is maintained

  Background:
    Given the API is available

  @auth
  Scenario: Registration with invalid email format
    When I register with email "not-an-email"
    Then the response status should be 422
    And the response should contain a validation error for "email"
    And the error should mention "valid email"

  @auth
  Scenario: Registration with password too short
    When I register with password "Short1"
    Then the response status should be 422
    And the response should contain a validation error for "password"
    And the error should mention minimum length of 8 characters

  @auth
  Scenario: Registration with missing required fields
    When I register with only:
      | email           |
      | test@example.com|
    Then the response status should be 422
    And the response should contain validation errors for:
      | field    |
      | name     |
      | password |
      | country  |
      | timezone |

  @auth
  Scenario: Login with invalid email format
    When I login with email "invalid-email" and password "password123"
    Then the response status should be 422
    And the response should contain a validation error for "email"

  @confab
  Scenario: Create confab with empty name
    Given I am logged in as "user@example.com"
    When I create a confab with:
      | name |
      |      |
    Then the response status should be 422
    And the response should contain a validation error for "name"

  @confab
  Scenario: Create confab with name exceeding 100 characters
    Given I am logged in as "user@example.com"
    When I create a confab with a name of 101 characters
    Then the response status should be 422
    And the response should contain a validation error for "name"
    And the error should mention maximum length of 100 characters

  @confab
  Scenario: Create confab with temperature below 0
    Given I am logged in as "user@example.com"
    When I create a confab with:
      | name  | temperature |
      | Test  | -0.5        |
    Then the response status should be 422
    And the response should contain a validation error for "temperature"
    And the error should mention "greater than or equal to 0"

  @confab
  Scenario: Create confab with temperature above 2.0
    Given I am logged in as "user@example.com"
    When I create a confab with:
      | name  | temperature |
      | Test  | 2.5         |
    Then the response status should be 422
    And the response should contain a validation error for "temperature"
    And the error should mention "less than or equal to 2"

  @confab
  Scenario: Create confab with invalid status
    Given I am logged in as "user@example.com"
    When I create a confab with:
      | name  | status       |
      | Test  | not-a-status |
    Then the response status should be 422
    And the response should contain a validation error for "status"

  @confab
  Scenario: Update confab with invalid status
    Given I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    When I update the confab with:
      | status  |
      | invalid |
    Then the response status should be 422

  @documents
  Scenario: Upload document without filename
    Given I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    When I upload a document without filename
    Then the response status should be 422
    And the response should contain a validation error for "filename"

  @documents
  Scenario: Upload document without content
    Given I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    When I upload a document without content_base64
    Then the response status should be 422
    And the response should contain a validation error for "content_base64"

  @documents
  Scenario: Upload document with invalid base64
    Given I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    When I upload a document with content_base64 "!!!not-base64!!!"
    Then the response status should be 400
    And the response should contain error about invalid content

  Scenario: Invalid JSON body returns 422
    Given I am logged in as "user@example.com"
    When I send invalid JSON to "/confabs"
    Then the response status should be 422

  Scenario: Wrong content type returns 422
    Given I am logged in as "user@example.com"
    When I POST to "/confabs" with content-type "text/plain"
    Then the response status should be 422
