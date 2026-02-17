"""
GitHub Contents API helper — commit config-wijzigingen naar de repository.
Zorgt dat config-wijzigingen persistent zijn over Render redeploys.
"""

import os
import json
import base64
import logging

import httpx

logger = logging.getLogger("nat-api")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "HondsrugFinance/NAT-hypotheek-API")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_API = "https://api.github.com"


async def commit_config_to_github(
    filename: str,
    content: dict,
    message: str,
) -> bool:
    """
    Commit een config-bestand naar GitHub via de Contents API.

    Args:
        filename: Config-naam zonder extensie (bijv. "fiscaal-frontend")
        content: Dict met de volledige config-inhoud
        message: Git commit bericht

    Returns:
        True bij succes, False bij fout (logt de error)
    """
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN niet ingesteld — skip GitHub commit")
        return False

    path = f"config/{filename}.json"
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Haal huidige SHA op (vereist voor update)
            resp = await client.get(
                url, headers=headers, params={"ref": GITHUB_BRANCH}
            )
            if resp.status_code != 200:
                logger.error(
                    "GitHub GET %s failed: %s %s", path, resp.status_code, resp.text
                )
                return False

            current_sha = resp.json()["sha"]

            # 2. PUT met nieuwe content
            new_content = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
            encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")

            put_resp = await client.put(
                url,
                headers=headers,
                json={
                    "message": message,
                    "content": encoded,
                    "sha": current_sha,
                    "branch": GITHUB_BRANCH,
                },
            )

            if put_resp.status_code in (200, 201):
                commit_sha = put_resp.json().get("commit", {}).get("sha", "?")
                logger.info("GitHub commit geslaagd: %s → %s", path, commit_sha[:8])
                return True
            else:
                logger.error(
                    "GitHub PUT %s failed: %s %s",
                    path,
                    put_resp.status_code,
                    put_resp.text,
                )
                return False

    except httpx.TimeoutException:
        logger.error("GitHub API timeout voor %s", path)
        return False
    except Exception as e:
        logger.error("GitHub sync fout voor %s: %s", path, e, exc_info=True)
        return False
