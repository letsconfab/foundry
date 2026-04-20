@documents
Feature: Document Versions
  As an authenticated user
  I want to manage document versions
  So that I can track changes to reference materials

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    And the confab has a document "guide.pdf"

  @positive
  Scenario: Upload new version of document
    When I upload a new version of "guide.pdf"
    Then the response status should be 200
    And the document should have version 2
    And the latest version number should be 2

  @positive
  Scenario: Upload multiple versions
    When I upload new versions of "guide.pdf" 3 times
    Then the document should have 4 versions total
    And the latest version number should be 4

  @positive
  Scenario: List all versions of a document
    Given the document has 3 versions
    When I list versions of "guide.pdf"
    Then the response status should be 200
    And the response should contain 3 versions
    And versions should be ordered newest first

  @positive
  Scenario: Each version has unique content hash
    Given the document has versions with different content
    When I list versions of "guide.pdf"
    Then each version should have a unique content_hash

  @positive
  Scenario: Version tracks original and compressed size
    When I upload a new version of "guide.pdf"
    Then the version should have:
      | field           |
      | original_size   |
      | compressed_size |
      | compression_ratio|

  @positive
  Scenario: Get specific version content
    Given the document has 3 versions
    When I get version 2 of "guide.pdf"
    Then the response status should be 200
    And the response should contain version 2 content

  @positive
  Scenario: Get latest version content
    Given the document has 3 versions
    When I get the latest version of "guide.pdf"
    Then the response status should be 200
    And the response should contain version 3 content

  @negative
  Scenario: Get non-existent version
    Given the document has 2 versions
    When I get version 5 of "guide.pdf"
    Then the response status should be 404
    And the response should contain error "Version not found"

  @negative
  Scenario: Upload version to archived document
    Given the document is archived
    When I upload a new version of "guide.pdf"
    Then the response status should be 404
    And the response should contain error "Document not found"

  @negative
  Scenario: Upload version without authentication
    Given I am not authenticated
    When I upload a new version of document ID 1
    Then the response status should be 401
