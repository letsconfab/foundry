@errors @security
Feature: Unauthorized Access (401)
  As the system
  I want to reject unauthenticated requests
  So that protected resources remain secure

  Background:
    Given the API is available
    And I am not authenticated

  @auth
  Scenario Outline: Protected auth endpoints require authentication
    When I make a <method> request to "<endpoint>"
    Then the response status should be 401
    And the response should contain error "Not authenticated"

    Examples:
      | method | endpoint              |
      | GET    | /auth/me              |
      | POST   | /auth/github/connect  |
      | GET    | /auth/github/repos    |

  @confab
  Scenario Outline: Protected confab endpoints require authentication
    When I make a <method> request to "<endpoint>"
    Then the response status should be 401

    Examples:
      | method | endpoint                                    |
      | GET    | /confabs                                    |
      | POST   | /confabs                                    |
      | GET    | /confabs/1                                  |
      | PUT    | /confabs/1                                  |
      | DELETE | /confabs/1                                  |
      | POST   | /confabs/1/definition-files/refresh         |
      | POST   | /confabs/1/definition-files/accept-and-commit|

  @documents
  Scenario Outline: Protected document endpoints require authentication
    When I make a <method> request to "<endpoint>"
    Then the response status should be 401

    Examples:
      | method | endpoint                            |
      | GET    | /confabs/1/documents                |
      | POST   | /confabs/1/documents                |
      | GET    | /confabs/1/documents/1              |
      | DELETE | /confabs/1/documents/1              |
      | GET    | /confabs/1/documents/1/versions/latest |

  @conversations
  Scenario Outline: Protected conversation endpoints require authentication
    When I make a <method> request to "<endpoint>"
    Then the response status should be 401

    Examples:
      | method | endpoint                         |
      | POST   | /conversations/foreman/1/resume  |
      | GET    | /threads/1                       |
      | POST   | /threads/1/chat                  |

  Scenario: Invalid token returns 401
    Given I have an invalid auth token "invalid.jwt.token"
    When I make a GET request to "/confabs"
    Then the response status should be 401
    And the response should contain error "Invalid credentials"

  Scenario: Malformed authorization header returns 401
    Given I have authorization header "NotBearer token123"
    When I make a GET request to "/confabs"
    Then the response status should be 401

  Scenario: Empty authorization header returns 401
    Given I have authorization header ""
    When I make a GET request to "/auth/me"
    Then the response status should be 401

  Scenario: Expired token returns 401
    Given I have an expired auth token
    When I make a GET request to "/confabs"
    Then the response status should be 401
    And the response should contain error "Token has expired"
