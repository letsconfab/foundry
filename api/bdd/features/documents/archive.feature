@documents
Feature: Archive Documents
  As an authenticated user
  I want to archive documents from my confabs
  So that I can remove outdated reference materials

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    And the confab has a document "guide.pdf"

  @positive
  Scenario: Archive a document
    When I archive the document "guide.pdf"
    Then the response status should be 200
    And the document status should be "archived"

  @positive
  Scenario: Archived document no longer appears in list
    When I archive the document "guide.pdf"
    And I list documents for the confab
    Then the response should contain 0 documents

  @positive
  Scenario: Archive document preserves versions
    Given the document has 3 versions
    When I archive the document "guide.pdf"
    Then the document should still have 3 versions
    And the document status should be "archived"

  @negative @wip
  Scenario: Archive already archived document
    # Note: API currently allows re-archiving (returns 200)
    Given the document is already archived
    When I archive the document "guide.pdf"
    Then the response status should be 400
    And the response should contain error "Document already archived"

  @negative
  Scenario: Archive non-existent document
    When I archive document ID 99999
    Then the response status should be 404
    And the response should contain error "Document not found"

  @negative
  Scenario: Archive document from another user's confab
    Given another user "other@example.com" has a confab with a document
    When I try to archive that document
    Then the response status should be 404

  @negative
  Scenario: Archive document without authentication
    Given I am not authenticated
    When I archive document ID 1 from confab ID 1
    Then the response status should be 401
