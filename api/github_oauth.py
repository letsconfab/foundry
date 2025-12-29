from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/auth/github/callback")

github_auth_router = APIRouter()

class GitHubTokenResponse(BaseModel):
    access_token: str
    token_type: str
    scope: str

class GitHubUser(BaseModel):
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None

class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    owner: Dict[str, Any]
    permissions: Dict[str, str]

@github_auth_router.get("/authorize")
async def github_authorize():
    """Redirect to GitHub for authorization."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub client ID not configured"
        )
    
    auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"redirect_uri={GITHUB_REDIRECT_URI}&"
        f"scope=repo user:email"
    )
    
    return RedirectResponse(url=auth_url)

@github_auth_router.get("/callback")
async def github_callback(code: str):
    """Handle GitHub OAuth callback."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not properly configured"
        )
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received"
            )
    
    # Get user information
    user_data = await get_github_user(access_token)
    
    # Redirect to frontend with token and user info
    frontend_url = (
        f"{GITHUB_REDIRECT_URI}?"
        f"access_token={access_token}&"
        f"github_id={user_data.id}&"
        f"github_username={user_data.login}"
    )
    
    return RedirectResponse(url=frontend_url)

async def get_github_user(access_token: str) -> GitHubUser:
    """Get GitHub user information using access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user information"
            )
        
        user_data = response.json()
        return GitHubUser(**user_data)

async def get_github_repos(access_token: str) -> List[GitHubRepo]:
    """Get GitHub repositories for the authenticated user."""
    async with httpx.AsyncClient() as client:
        # Get user repos
        response = await client.get(
            "https://api.github.com/user/repos?type=owner&per_page=100",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub repositories"
            )
        
        repos_data = response.json()
        
        # Get organizations and their repos
        orgs_response = await client.get(
            "https://api.github.com/user/orgs",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if orgs_response.status_code == 200:
            orgs = orgs_response.json()
            for org in orgs:
                org_repos_response = await client.get(
                    f"https://api.github.com/orgs/{org['login']}/repos?per_page=100",
                    headers={"Authorization": f"token {access_token}"}
                )
                if org_repos_response.status_code == 200:
                    repos_data.extend(org_repos_response.json())
        
        return [GitHubRepo(**repo) for repo in repos_data]

async def get_github_orgs(access_token: str) -> List[Dict[str, Any]]:
    """Get GitHub organizations for the authenticated user."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/orgs",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub organizations"
            )
        
        return response.json()

async def check_repo_permissions(access_token: str, repo_owner: str, repo_name: str) -> Dict[str, str]:
    """Check if the user has write permissions to a repository."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found or no access"
            )
        
        repo_data = response.json()
        return repo_data.get("permissions", {})
