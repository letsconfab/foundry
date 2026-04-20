@errors @security
Feature: Forbidden Access (403/404)
  As the system
  I want to prevent users from accessing other users' resources
  So that data privacy is maintained

  Background:
    Given the API is available
    And I am logged in as "user@example.com"

  # Note: The API returns 404 instead of 403 for resources belonging to other users
  # This prevents information leakage about resource existence

  @confab
  Scenario: Cannot get another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I get confab with ID 100
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @confab
  Scenario: Cannot update another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I update confab with ID 100 with:
      | name     |
      | Hijacked |
    Then the response status should be 404

  @confab
  Scenario: Cannot delete another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I delete confab with ID 100
    Then the response status should be 404

  @confab
  Scenario: Listing confabs only returns own confabs
    Given another user "other@example.com" has 5 confabs
    And I have created 2 confabs
    When I list my confabs
    Then the response should contain 2 confabs
    And all confabs should belong to me

  @documents
  Scenario: Cannot list documents from another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I list documents for confab ID 100
    Then the response status should be 404

  @documents
  Scenario: Cannot upload document to another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I upload a document to confab ID 100
    Then the response status should be 404

  @documents
  Scenario: Cannot get document from another user's confab
    Given another user "other@example.com" has a confab with document ID 50
    When I get document ID 50 from confab ID 100
    Then the response status should be 404

  @documents
  Scenario: Cannot archive document from another user's confab
    Given another user "other@example.com" has a confab with document ID 50
    When I archive document ID 50 from confab ID 100
    Then the response status should be 404

  @github
  Scenario: Cannot commit definition files for another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I commit definition files for confab ID 100
    Then the response status should be 404

  @github
  Scenario: Cannot refresh definition files for another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I refresh definition files for confab ID 100
    Then the response status should be 404

  @conversations
  Scenario: Cannot resume conversation for another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I resume foreman conversation for confab ID 100
    Then the response status should be 404

  @learnings
  Scenario: Cannot view learnings for another user's confab
    Given another user "other@example.com" has a confab with learnings
    When I list learnings for that confab
    Then the response status should be 404

  @learnings
  Scenario: Cannot add learnings to another user's confab
    Given another user "other@example.com" has a confab with ID 100
    When I add a learning to confab ID 100
    Then the response status should be 404
