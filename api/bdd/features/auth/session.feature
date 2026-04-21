@auth
Feature: Session Management
  As an authenticated user
  I want my session to be properly managed
  So that my account remains secure

  Background:
    Given the API is available

  @positive
  Scenario: Access protected endpoint with valid token
    Given I am logged in as "user@example.com"
    When I request my user profile
    Then the response status should be 200
    And the response should contain my user details

  @negative
  Scenario: Access protected endpoint without token
    When I request my user profile without authentication
    Then the response status should be 401
    And the response should contain error "Not authenticated"

  @negative
  Scenario: Access protected endpoint with invalid token
    Given I have an invalid auth token "invalid.token.here"
    When I request my user profile
    Then the response status should be 401
    And the response should contain error "Invalid credentials"

  @negative
  Scenario: Access protected endpoint with malformed token
    Given I have an invalid auth token "not-even-a-jwt"
    When I request my user profile
    Then the response status should be 401

  @negative
  Scenario: Access protected endpoint with expired token
    Given I have an expired auth token
    When I request my user profile
    Then the response status should be 401
    And the response should contain error "Token has expired"

  @positive
  Scenario: Token contains correct user information
    Given I am logged in as "user@example.com"
    When I request my user profile
    Then the response should contain:
      | field |
      | email |
      | name  |
      | id    |
