@auth
Feature: User Login
  As a registered user
  I want to log into my account
  So that I can access my confabs

  Background:
    Given the API is available
    And a user exists with:
      | email            | password   | name     |
      | user@example.com | SecureP@ss | Test User|

  @positive
  Scenario: Successful login with valid credentials
    When I login with email "user@example.com" and password "SecureP@ss"
    Then the response status should be 200
    And the response should contain an access token
    And the response should contain user details:
      | name      | email            |
      | Test User | user@example.com |

  @positive @wip
  Scenario: Login returns GitHub connection status
    # Note: Requires GitHub account setup in test
    Given the user has connected their GitHub account
    When I login with email "user@example.com" and password "SecureP@ss"
    Then the response status should be 200
    And the user should have GitHub connected

  @negative
  Scenario: Login fails with wrong password
    When I login with email "user@example.com" and password "WrongPassword"
    Then the response status should be 401
    And the response should contain error "Invalid credentials"

  @negative
  Scenario: Login fails with non-existent email
    When I login with email "nobody@example.com" and password "SecureP@ss"
    Then the response status should be 401
    And the response should contain error "Invalid credentials"

  @negative @validation
  Scenario: Login fails with invalid email format
    When I login with email "not-an-email" and password "SecureP@ss"
    Then the response status should be 422
    And the response should contain a validation error for "email"

  @negative
  Scenario: Login fails with empty password
    When I login with email "user@example.com" and password ""
    Then the response status should be 401
    And the response should contain error "Invalid credentials"
