import httpx
from typing import Dict, Any, Optional
from base64 import b64encode
import json
from datetime import datetime

class ConfabManager:
    """Manages confab creation and updates in GitHub repositories."""
    
    def __init__(self):
        self.default_confab_template = {
            "name": "",
            "description": "",
            "version": "1.0.0",
            "created_at": "",
            "purpose": "",
            "guardrails": "",
            "tests": "",
            "configuration": {}
        }
    
    async def create_confab_in_github(
        self,
        confab_name: str,
        confab_data: Dict[str, Any],
        repo_owner: str,
        repo_name: str,
        access_token: Optional[str] = None
    ) -> str:
        """Create a new confab in GitHub repository."""
        
        # Prepare confab files
        files = self._prepare_confab_files(confab_name, confab_data)
        
        # Create branch for the confab
        branch_name = f"confab-{confab_name.lower().replace(' ', '-')}-{int(datetime.now().timestamp())}"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        
        if access_token:
            headers["Authorization"] = f"token {access_token}"
        
        async with httpx.AsyncClient() as client:
            # Get default branch
            repo_response = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}",
                headers=headers
            )
            
            if repo_response.status_code != 200:
                raise Exception(f"Repository {repo_owner}/{repo_name} not found")
            
            repo_data = repo_response.json()
            default_branch = repo_data["default_branch"]
            
            # Get base branch reference
            ref_response = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/ref/heads/{default_branch}",
                headers=headers
            )
            
            if ref_response.status_code != 200:
                raise Exception("Failed to get base branch reference")
            
            base_ref = ref_response.json()
            base_sha = base_ref["object"]["sha"]
            
            # Create new branch
            branch_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            branch_response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs",
                headers=headers,
                json=branch_data
            )
            
            if branch_response.status_code != 201:
                raise Exception("Failed to create branch")
            
            # Create files in the new branch
            confab_dir = f"confabs/{confab_name.lower().replace(' ', '-')}"
            
            for file_path, content in files.items():
                full_path = f"{confab_dir}/{file_path}"
                
                # Get file SHA if it exists
                existing_file_response = await client.get(
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{full_path}",
                    headers=headers
                )
                
                file_data = {
                    "message": f"Add {file_path} for confab {confab_name}",
                    "content": b64encode(content.encode()).decode(),
                    "branch": branch_name
                }
                
                if existing_file_response.status_code == 200:
                    # Update existing file
                    existing_data = existing_file_response.json()
                    file_data["sha"] = existing_data["sha"]
                
                file_response = await client.put(
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{full_path}",
                    headers=headers,
                    json=file_data
                )
                
                if file_response.status_code not in [200, 201]:
                    raise Exception(f"Failed to create/update {file_path}")
            
            # Create pull request
            pr_data = {
                "title": f"Add confab: {confab_name}",
                "body": f"Automated confab creation for {confab_name}\n\n{confab_data.get('description', '')}",
                "head": branch_name,
                "base": default_branch
            }
            
            pr_response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls",
                headers=headers,
                json=pr_data
            )
            
            if pr_response.status_code != 201:
                raise Exception("Failed to create pull request")
            
            pr_data = pr_response.json()
            return pr_data["html_url"]
    
    async def update_confab_in_github(
        self,
        confab_name: str,
        confab_data: Dict[str, Any],
        github_url: str,
        access_token: str
    ) -> str:
        """Update an existing confab in GitHub repository."""
        
        # Extract repo info from GitHub URL
        # Example: https://github.com/owner/repo/pull/123
        parts = github_url.split("/")
        repo_owner = parts[3]
        repo_name = parts[4]
        pr_number = parts[6]
        
        # Prepare updated confab files
        files = self._prepare_confab_files(confab_name, confab_data)
        
        # Create new branch for update
        branch_name = f"update-confab-{confab_name.lower().replace(' ', '-')}-{int(datetime.now().timestamp())}"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {access_token}"
        }
        
        async with httpx.AsyncClient() as client:
            # Get PR details to get base branch
            pr_response = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}",
                headers=headers
            )
            
            if pr_response.status_code != 200:
                raise Exception("Failed to get PR details")
            
            pr_data = pr_response.json()
            base_branch = pr_data["base"]["ref"]
            
            # Get base branch reference
            ref_response = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/ref/heads/{base_branch}",
                headers=headers
            )
            
            if ref_response.status_code != 200:
                raise Exception("Failed to get base branch reference")
            
            base_ref = ref_response.json()
            base_sha = base_ref["object"]["sha"]
            
            # Create new branch
            branch_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            branch_response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs",
                headers=headers,
                json=branch_data
            )
            
            if branch_response.status_code != 201:
                raise Exception("Failed to create branch")
            
            # Update files in the new branch
            confab_dir = f"confabs/{confab_name.lower().replace(' ', '-')}"
            
            for file_path, content in files.items():
                full_path = f"{confab_dir}/{file_path}"
                
                # Get existing file
                existing_file_response = await client.get(
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{full_path}",
                    headers=headers
                )
                
                if existing_file_response.status_code == 200:
                    existing_data = existing_file_response.json()
                    file_sha = existing_data["sha"]
                else:
                    file_sha = None
                
                file_data = {
                    "message": f"Update {file_path} for confab {confab_name}",
                    "content": b64encode(content.encode()).decode(),
                    "branch": branch_name
                }
                
                if file_sha:
                    file_data["sha"] = file_sha
                
                file_response = await client.put(
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{full_path}",
                    headers=headers,
                    json=file_data
                )
                
                if file_response.status_code not in [200, 201]:
                    raise Exception(f"Failed to update {file_path}")
            
            # Create pull request
            pr_data = {
                "title": f"Update confab: {confab_name}",
                "body": f"Automated confab update for {confab_name}\n\n{confab_data.get('description', '')}",
                "head": branch_name,
                "base": base_branch
            }
            
            pr_response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls",
                headers=headers,
                json=pr_data
            )
            
            if pr_response.status_code != 201:
                raise Exception("Failed to create pull request")
            
            new_pr_data = pr_response.json()
            return new_pr_data["html_url"]
    
    def _prepare_confab_files(self, confab_name: str, confab_data: Dict[str, Any]) -> Dict[str, str]:
        """Prepare confab files for GitHub repository."""
        
        # Create Confab.toml
        confab_toml = f"""[confab]
name = "{confab_name}"
description = "{confab_data.get('description', '')}"
version = "1.0.0"
created_at = "{datetime.now().isoformat()}"

[metadata]
author = "Let's Confab"
license = "MIT"
"""
        
        # Create PURPOSE.md
        purpose_md = f"""# Purpose: {confab_name}

{confab_data.get('purpose', f'This confab is designed to {confab_data.get("description", "perform specific tasks")}')}

## Primary Objectives
- {confab_data.get('description', 'Main functionality description')}

## Target Use Cases
- User interactions and scenarios where this confab excels
- Specific problems it solves

## Expected Behavior
- How the confab should respond in different situations
- Key features and capabilities
"""
        
        # Create GUARDRAILS.md
        guardrails_md = f"""# Guardrails: {confab_name}

## Safety Constraints
- Do not generate harmful, illegal, or unethical content
- Respect user privacy and data protection guidelines
- Avoid making claims beyond the confab's capabilities

## Behavioral Boundaries
- Stay within the defined scope of {confab_name}
- Do not impersonate individuals or organizations without permission
- Maintain professional and respectful communication

## Content Guidelines
- Ensure all generated content is accurate and helpful
- Provide citations or sources when making factual claims
- Acknowledge limitations when uncertain

## Error Handling
- Gracefully handle ambiguous or unclear requests
- Ask for clarification when needed
- Provide helpful error messages and suggestions
"""
        
        # Create TESTS.md
        tests_md = f"""# Tests: {confab_name}

## Unit Tests
### Basic Functionality
- [ ] Test basic conversation flow
- [ ] Test response accuracy
- [ ] Test error handling

### Edge Cases
- [ ] Test with ambiguous input
- [ ] Test with incomplete information
- [ ] Test with conflicting requests

## Integration Tests
### API Integration
- [ ] Test external API connections
- [ ] Test data flow between components
- [ ] Test error recovery

### User Interface
- [ ] Test user interaction patterns
- [ ] Test response formatting
- [ ] Test accessibility features

## Performance Tests
### Response Time
- [ ] Test under normal load
- [ ] Test under peak load
- [ ] Test with concurrent users

### Resource Usage
- [ ] Monitor memory usage
- [ ] Monitor CPU usage
- [ ] Test scalability limits

## Security Tests
### Input Validation
- [ ] Test for injection attacks
- [ ] Test for malicious input
- [ ] Test data sanitization

### Access Control
- [ ] Test authentication mechanisms
- [ ] Test authorization levels
- [ ] Test data privacy

## Test Scenarios
### Happy Path
1. User provides clear, valid input
2. Confab processes request correctly
3. Response is accurate and helpful

### Error Recovery
1. User provides invalid input
2. Confab identifies the issue
3. Confab provides helpful guidance

### Complex Queries
1. User asks multi-part questions
2. Confab addresses all components
3. Response is well-structured and complete
"""
        
        return {
            "Confab.toml": confab_toml,
            "PURPOSE.md": purpose_md,
            "GUARDRAILS.md": guardrails_md,
            "TESTS.md": tests_md
        }

# Global instance
confab_manager = ConfabManager()

# Convenience functions
async def create_confab_in_github(
    confab_name: str,
    confab_data: Dict[str, Any],
    repo_owner: str,
    repo_name: str,
    access_token: Optional[str] = None
) -> str:
    return await confab_manager.create_confab_in_github(
        confab_name, confab_data, repo_owner, repo_name, access_token
    )

async def update_confab_in_github(
    confab_name: str,
    confab_data: Dict[str, Any],
    github_url: str,
    access_token: str
) -> str:
    return await confab_manager.update_confab_in_github(
        confab_name, confab_data, github_url, access_token
    )
