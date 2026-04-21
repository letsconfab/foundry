@documents
Feature: Document Upload
  As an authenticated user
  I want to upload documents to my confabs
  So that the AI agent can reference them

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Test Agent"

  @positive
  Scenario: Upload PDF document
    When I upload a document:
      | filename     | content_type    |
      | guide.pdf    | application/pdf |
    Then the response status should be 200
    And the response should contain document details:
      | filename  | content_type    | status |
      | guide.pdf | application/pdf | active |
    And the document should have a UUID
    And the document should have version 1

  @positive
  Scenario: Upload text file
    When I upload a document:
      | filename   | content_type |
      | readme.txt | text/plain   |
    Then the response status should be 200
    And the document should be uploaded successfully

  @positive
  Scenario: Upload markdown file
    When I upload a document:
      | filename    | content_type |
      | notes.md    | text/markdown|
    Then the response status should be 200

  @positive
  Scenario: Upload JSON file
    When I upload a document:
      | filename     | content_type     |
      | config.json  | application/json |
    Then the response status should be 200

  @positive
  Scenario: Upload YAML file
    When I upload a document:
      | filename    | content_type       |
      | spec.yaml   | application/x-yaml |
    Then the response status should be 200

  @positive
  Scenario: Upload image file (PNG)
    When I upload a document:
      | filename    | content_type |
      | diagram.png | image/png    |
    Then the response status should be 200

  @positive
  Scenario: Upload image file (JPEG)
    When I upload a document:
      | filename   | content_type |
      | photo.jpg  | image/jpeg   |
    Then the response status should be 200

  @positive
  Scenario: Upload CSV file
    When I upload a document:
      | filename  | content_type |
      | data.csv  | text/csv     |
    Then the response status should be 200

  @positive
  Scenario: Upload Excel file
    When I upload a document:
      | filename    | content_type                                                              |
      | report.xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet        |
    Then the response status should be 200

  @positive
  Scenario: Upload Word document
    When I upload a document:
      | filename    | content_type                                                                 |
      | doc.docx    | application/vnd.openxmlformats-officedocument.wordprocessingml.document      |
    Then the response status should be 200

  @positive
  Scenario: Document content is compressed
    When I upload a large document:
      | filename      | size_kb |
      | large.txt     | 100     |
    Then the response status should be 200
    And the compressed size should be less than the original size

  @negative @validation
  Scenario: Reject unsupported file format - executable
    When I upload a document:
      | filename    | content_type              |
      | malware.exe | application/x-executable  |
    Then the response status should be 400
    And the response should contain error about unsupported format

  @negative @validation
  Scenario: Reject unsupported file format - shell script
    When I upload a document:
      | filename  | content_type       |
      | script.sh | application/x-sh   |
    Then the response status should be 400

  @negative @validation
  Scenario: Reject unsupported file format - binary
    When I upload a document:
      | filename  | content_type             |
      | data.bin  | application/octet-stream |
    Then the response status should be 400

  @negative @validation
  Scenario: Reject file exceeding 50MB size limit
    When I upload a document exceeding 50MB
    Then the response status should be 400
    And the response should contain error about file size

  @positive @validation
  Scenario: Accept file at exactly 50MB
    When I upload a document of exactly 50MB
    Then the response status should be 200

  @negative @validation
  Scenario: Reject upload with missing filename
    When I upload a document without filename
    Then the response status should be 422
    And the response should contain a validation error for "filename"

  @negative @validation
  Scenario: Reject upload with missing content
    When I upload a document without content
    Then the response status should be 422
    And the response should contain a validation error for "content_base64"

  @negative @validation
  Scenario: Reject upload with invalid base64 content
    When I upload a document with invalid base64:
      | filename  | content_base64  |
      | test.txt  | not-valid-b64!  |
    Then the response status should be 400
    And the response should contain error about invalid content

  @negative
  Scenario: Upload to non-existent confab
    When I upload a document to confab ID 99999:
      | filename  |
      | test.txt  |
    Then the response status should be 404

  @negative
  Scenario: Upload to another user's confab
    Given another user "other@example.com" has a confab named "Other Agent"
    When I upload a document to that confab:
      | filename  |
      | test.txt  |
    Then the response status should be 404

  @negative
  Scenario: Upload without authentication
    Given I am not authenticated
    When I upload a document to my confab:
      | filename  |
      | test.txt  |
    Then the response status should be 401

  @positive
  Scenario: Upload document with duplicate filename creates new document
    Given I have uploaded a document named "guide.pdf"
    When I upload another document:
      | filename  |
      | guide.pdf |
    Then the response status should be 200
    And the confab should have 2 documents
