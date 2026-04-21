@auth
Feature: User Registration
  As a new user
  I want to create an account
  So that I can use the Foundry platform

  Background:
    Given the API is available

  @positive
  Scenario: Successful registration with valid data
    When I register with the following details:
      | name     | email              | password   | country | timezone     |
      | John Doe | john@example.com   | SecureP@ss1| US      | America/New_York |
    Then the response status should be 200
    And the response should contain an access token
    And the response should contain user details:
      | name     | email            | country | timezone         |
      | John Doe | john@example.com | US      | America/New_York |
    And the user should not have GitHub connected

  @positive
  Scenario: Registration with minimum required fields
    When I register with the following details:
      | name | email           | password   | country | timezone |
      | Jane | jane@test.com   | Password8! | other   | UTC      |
    Then the response status should be 200
    And the response should contain an access token

  @negative @validation @wip
  Scenario: Registration fails with duplicate email
    # Note: Test data isolation issue - email may already exist from previous runs
    Given a user exists with email "existing@example.com"
    When I register with the following details:
      | name    | email                | password   | country | timezone |
      | Another | existing@example.com | SecureP@ss | US      | UTC      |
    Then the response status should be 400
    And the response should contain error "Email already registered"

  @negative @validation
  Scenario: Registration fails with invalid email format
    When I register with the following details:
      | name | email       | password   | country | timezone |
      | Test | not-an-email| SecureP@ss | US      | UTC      |
    Then the response status should be 422
    And the response should contain a validation error for "email"

  @negative @validation
  Scenario: Registration fails with password too short
    When I register with the following details:
      | name | email           | password | country | timezone |
      | Test | test@test.com   | Short1!  | US      | UTC      |
    Then the response status should be 422
    And the response should contain a validation error for "password"
    And the error should mention minimum length of 8 characters

  @negative @validation
  Scenario: Registration fails with missing required fields
    When I register with the following details:
      | name | email         |
      | Test | test@test.com |
    Then the response status should be 422
    And the response should contain validation errors for missing fields

  @negative @validation
  Scenario: Registration fails with empty name
    When I register with the following details:
      | name | email           | password   | country | timezone |
      |      | test@test.com   | SecureP@ss | US      | UTC      |
    Then the response status should be 422
    And the response should contain a validation error for "name"
