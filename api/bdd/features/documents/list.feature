@documents
Feature: List Documents
  As an authenticated user
  I want to list documents attached to my confabs
  So that I can see what reference materials are available

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"

  @positive
  Scenario: List documents for confab
    Given the confab has documents:
      | filename    |
      | guide.pdf   |
      | readme.txt  |
      | config.json |
    When I list documents for the confab
    Then the response status should be 200
    And the response should contain 3 documents
    And the documents should include:
      | filename    |
      | guide.pdf   |
      | readme.txt  |
      | config.json |

  @positive
  Scenario: List documents returns only active documents
    Given the confab has documents:
      | filename    | status   |
      | active.pdf  | active   |
      | archived.pdf| archived |
    When I list documents for the confab
    Then the response status should be 200
    And the response should contain 1 document
    And the document should be "active.pdf"

  @positive
  Scenario: List documents returns empty when none exist
    When I list documents for the confab
    Then the response status should be 200
    And the response should contain 0 documents

  @positive
  Scenario: List documents includes version count
    Given the confab has a document "guide.pdf" with 3 versions
    When I list documents for the confab
    Then the response status should be 200
    And the document "guide.pdf" should have version_count 3

  @positive
  Scenario: List documents includes latest version info
    Given the confab has a document "guide.pdf" with versions:
      | version | size_kb |
      | 1       | 100     |
      | 2       | 150     |
    When I list documents for the confab
    Then the response should include latest_version with:
      | version_number | original_size |
      | 2              | 153600        |

  @positive
  Scenario: List documents sorted by creation date descending
    Given the confab has documents uploaded in order:
      | filename  | uploaded_at         |
      | first.pdf | 2024-01-01 10:00:00 |
      | second.pdf| 2024-01-02 10:00:00 |
      | third.pdf | 2024-01-03 10:00:00 |
    When I list documents for the confab
    Then the first document should be "third.pdf"
    And the last document should be "first.pdf"

  @negative
  Scenario: List documents for non-existent confab
    When I list documents for confab ID 99999
    Then the response status should be 404

  @negative
  Scenario: List documents for another user's confab
    Given another user "other@example.com" has a confab with documents
    When I list documents for that confab
    Then the response status should be 404

  @negative
  Scenario: List documents without authentication
    Given I am not authenticated
    When I list documents for confab ID 1
    Then the response status should be 401
