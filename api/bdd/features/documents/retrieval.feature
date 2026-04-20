@documents
Feature: Document Retrieval
  As an authenticated user
  I want to retrieve document content
  So that I can view uploaded reference materials

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"
    And the confab has a document "guide.pdf" with content

  @positive
  Scenario: Get document metadata
    When I get document metadata for "guide.pdf"
    Then the response status should be 200
    And the response should contain:
      | field          |
      | id             |
      | document_uuid  |
      | filename       |
      | content_type   |
      | status         |
      | version_count  |
      | created_at     |

  @positive
  Scenario: Get document content
    When I get document content for "guide.pdf"
    Then the response status should be 200
    And the response should contain:
      | field          |
      | content_base64 |
      | original_size  |
      | filename       |
      | content_type   |

  @positive
  Scenario: Document content is decompressed on retrieval
    Given the document was uploaded with compression
    When I get document content for "guide.pdf"
    Then the content should be decompressed
    And the original_size should match the original file size

  @positive
  Scenario: Get extracted text from document
    Given the document has extracted text
    When I get document content for "guide.pdf"
    Then the response should include extracted_text

  @positive @wip
  Scenario: Get document by UUID
    # Note: UUID lookup endpoint not yet implemented
    Given I have the document UUID
    When I get document by UUID
    Then the response status should be 200
    And the response should contain the document details

  @negative
  Scenario: Get non-existent document
    When I get document ID 99999
    Then the response status should be 404
    And the response should contain error "Document not found"

  @negative @wip
  Scenario: Get archived document metadata
    # Note: API behavior for archived documents needs verification
    Given the document is archived
    When I get document metadata for "guide.pdf"
    Then the response status should be 404
    And the response should contain error "Document not found"

  @negative
  Scenario: Get document from another user's confab
    Given another user "other@example.com" has a confab with a document
    When I try to get that document
    Then the response status should be 404

  @negative
  Scenario: Get document without authentication
    Given I am not authenticated
    When I get document ID 1
    Then the response status should be 401

  @positive @wip
  Scenario: Document includes source information
    # Note: URL upload feature not tested - source is always "upload"
    Given the document was uploaded from URL "https://example.com/guide.pdf"
    When I get document metadata for "guide.pdf"
    Then the response should contain:
      | source     | source_url                    |
      | url        | https://example.com/guide.pdf |
