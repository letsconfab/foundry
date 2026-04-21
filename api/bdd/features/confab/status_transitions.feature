@confab
Feature: Confab Status Transitions
  As an authenticated user
  I want to manage confab status
  So that I can track the lifecycle of my AI agents

  Background:
    Given the API is available
    And I am logged in as "user@example.com"

  @positive
  Scenario: New confab starts in building status
    When I create a confab with:
      | name       |
      | New Agent  |
    Then the confab status should be "building"

  @positive
  Scenario: Transition from building to draft
    Given I have a confab in "building" status
    When I update the confab status to "draft"
    Then the response status should be 200
    And the confab status should be "draft"

  @positive
  Scenario: Transition from draft to published
    Given I have a confab in "draft" status
    When I update the confab status to "published"
    Then the response status should be 200
    And the confab status should be "published"

  @positive
  Scenario: Transition from published to archived
    Given I have a confab in "published" status
    When I update the confab status to "archived"
    Then the response status should be 200
    And the confab status should be "archived"

  @positive
  Scenario: Transition from archived back to draft
    Given I have a confab in "archived" status
    When I update the confab status to "draft"
    Then the response status should be 200
    And the confab status should be "draft"

  @positive
  Scenario: Transition directly from building to published
    Given I have a confab in "building" status
    When I update the confab status to "published"
    Then the response status should be 200
    And the confab status should be "published"

  @positive
  Scenario: Transition from any status to archived
    Given I have a confab in "building" status
    When I update the confab status to "archived"
    Then the response status should be 200
    And the confab status should be "archived"

  @positive
  Scenario Outline: Valid status transitions
    Given I have a confab in "<from_status>" status
    When I update the confab status to "<to_status>"
    Then the response status should be 200
    And the confab status should be "<to_status>"

    Examples:
      | from_status | to_status |
      | building    | draft     |
      | building    | published |
      | building    | archived  |
      | draft       | building  |
      | draft       | published |
      | draft       | archived  |
      | published   | draft     |
      | published   | archived  |
      | archived    | draft     |
      | archived    | building  |
