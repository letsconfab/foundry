"""
Tests for GitHubService.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from github_service import (
    GitHubService,
    GitHubServiceError,
    BranchNotFoundError,
    FileNotFoundError,
    PRNotFoundError,
    USE_NEW_GITHUB_SERVICE
)


class TestGitHubServiceInit:
    """Tests for GitHubService initialization."""

    def test_init(self):
        """Test service initialization."""
        service = GitHubService(
            access_token="test-token",
            repo_owner="testowner",
            repo_name="testrepo"
        )
        assert service.access_token == "test-token"
        assert service.repo_owner == "testowner"
        assert service.repo_name == "testrepo"
        assert service.repo_path == "testowner/testrepo"

    def test_headers(self):
        """Test authorization headers are set correctly."""
        service = GitHubService("test-token", "owner", "repo")
        headers = service.headers
        assert headers["Authorization"] == "token test-token"
        assert "Accept" in headers


class TestGitHubServiceBranches:
    """Tests for branch operations."""

    @pytest.mark.asyncio
    async def test_branch_exists_true(self):
        """Test branch_exists returns True when branch exists."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            result = await service.branch_exists("main")
            assert result is True

    @pytest.mark.asyncio
    async def test_branch_exists_false(self):
        """Test branch_exists returns False when branch doesn't exist."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_request.return_value = mock_response

            result = await service.branch_exists("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_or_create_branch_existing(self):
        """Test get_or_create_branch returns existing branch."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "branch_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True

            result = await service.get_or_create_branch(123)
            assert result == "confab-123"

    @pytest.mark.asyncio
    async def test_get_or_create_branch_creates_new(self):
        """Test get_or_create_branch creates new branch when it doesn't exist."""
        service = GitHubService("token", "owner", "repo")
        service._default_branch = "main"

        with patch.object(service, "branch_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
                # Mock get ref response
                ref_response = MagicMock()
                ref_response.status_code = 200
                ref_response.json.return_value = {"object": {"sha": "abc123"}}

                # Mock create ref response
                create_response = MagicMock()
                create_response.status_code = 201

                mock_request.side_effect = [ref_response, create_response]

                result = await service.get_or_create_branch(456)
                assert result == "confab-456"


class TestGitHubServiceFiles:
    """Tests for file operations."""

    @pytest.mark.asyncio
    async def test_get_file_contents_success(self):
        """Test getting file contents."""
        service = GitHubService("token", "owner", "repo")
        service._default_branch = "main"

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            import base64
            content = base64.b64encode(b"# Test Content").decode()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "type": "file",
                "content": content
            }
            mock_request.return_value = mock_response

            result = await service.get_file_contents("README.md")
            assert result == "# Test Content"

    @pytest.mark.asyncio
    async def test_get_file_contents_not_found(self):
        """Test getting non-existent file raises error."""
        service = GitHubService("token", "owner", "repo")
        service._default_branch = "main"

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_request.return_value = mock_response

            with pytest.raises(FileNotFoundError):
                await service.get_file_contents("nonexistent.md")

    @pytest.mark.asyncio
    async def test_create_or_update_file_create(self):
        """Test creating a new file."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "get_file_sha", new_callable=AsyncMock) as mock_sha:
            mock_sha.return_value = None  # File doesn't exist

            with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
                mock_response = MagicMock()
                mock_response.status_code = 201
                mock_response.json.return_value = {"commit": {"sha": "newsha"}}
                mock_request.return_value = mock_response

                result = await service.create_or_update_file(
                    "test.md", "# Test", "main"
                )
                assert "commit" in result

    @pytest.mark.asyncio
    async def test_create_or_update_file_update(self):
        """Test updating an existing file."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "get_file_sha", new_callable=AsyncMock) as mock_sha:
            mock_sha.return_value = "existingsha"  # File exists

            with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"commit": {"sha": "updatedsha"}}
                mock_request.return_value = mock_response

                result = await service.create_or_update_file(
                    "test.md", "# Updated", "main"
                )
                assert "commit" in result


class TestGitHubServicePRs:
    """Tests for PR operations."""

    @pytest.mark.asyncio
    async def test_get_open_pr_found(self):
        """Test getting an open PR."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"number": 1, "head": {"ref": "confab-123"}}
            ]
            mock_request.return_value = mock_response

            result = await service.get_open_pr("confab-123")
            assert result["number"] == 1

    @pytest.mark.asyncio
    async def test_get_open_pr_not_found(self):
        """Test getting non-existent PR returns None."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_request.return_value = mock_response

            result = await service.get_open_pr("confab-123")
            assert result is None

    @pytest.mark.asyncio
    async def test_create_pr_success(self):
        """Test creating a new PR."""
        service = GitHubService("token", "owner", "repo")
        service._default_branch = "main"

        with patch.object(service, "get_open_pr", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # No existing PR

            with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
                mock_response = MagicMock()
                mock_response.status_code = 201
                mock_response.json.return_value = {
                    "number": 42,
                    "html_url": "https://github.com/owner/repo/pull/42"
                }
                mock_request.return_value = mock_response

                result = await service.create_pr(
                    "confab-123", "Test PR", "PR body"
                )
                assert result["number"] == 42

    @pytest.mark.asyncio
    async def test_create_pr_returns_existing(self):
        """Test create_pr returns existing PR if one exists."""
        service = GitHubService("token", "owner", "repo")
        service._default_branch = "main"  # Set default branch to avoid API call

        with patch.object(service, "get_open_pr", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"number": 99, "html_url": "existing"}

            result = await service.create_pr("confab-123", "Test", "Body")
            assert result["number"] == 99

    @pytest.mark.asyncio
    async def test_close_pr_success(self):
        """Test closing a PR."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            result = await service.close_pr(42)
            assert result is True


class TestGitHubServiceHighLevel:
    """Tests for high-level operations."""

    @pytest.mark.asyncio
    async def test_commit_confab_file(self):
        """Test committing a confab file."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "get_or_create_branch", new_callable=AsyncMock) as mock_branch:
            mock_branch.return_value = "confab-123"

            with patch.object(service, "create_or_update_file", new_callable=AsyncMock):
                with patch.object(service, "create_pr", new_callable=AsyncMock) as mock_pr:
                    mock_pr.return_value = {"html_url": "https://github.com/test/pull/1"}

                    result = await service.commit_confab_file(
                        "Test Confab", "PURPOSE.md", "# Purpose", 123
                    )
                    assert "github.com" in result

    @pytest.mark.asyncio
    async def test_create_confab_files(self):
        """Test creating all confab files."""
        service = GitHubService("token", "owner", "repo")

        with patch.object(service, "get_or_create_branch", new_callable=AsyncMock) as mock_branch:
            mock_branch.return_value = "confab-456"

            with patch.object(service, "create_or_update_file", new_callable=AsyncMock) as mock_file:
                with patch.object(service, "create_pr", new_callable=AsyncMock) as mock_pr:
                    mock_pr.return_value = {"html_url": "https://github.com/test/pull/2"}

                    result = await service.create_confab_files(
                        "New Confab",
                        {"description": "Test", "status": "building"},
                        456
                    )

                    # Should create 4 files
                    assert mock_file.call_count == 4
                    assert "github.com" in result
