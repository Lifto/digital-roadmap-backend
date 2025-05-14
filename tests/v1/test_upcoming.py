from pathlib import Path

from roadmap.common import decode_header
from roadmap.common import query_rbac
from roadmap.config import Settings


def test_get_upcoming_changes(client, api_prefix):
    async def query_rbac_override():
        return [
            {
                "permission": "inventory:*:*",
                "resourceDefinitions": [],
            }
        ]

    async def decode_header_override():
        return "1234"

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[query_rbac] = query_rbac_override
    client.app.dependency_overrides[decode_header] = decode_header_override

    response = client.get(f"{api_prefix}/upcoming-changes")
    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "New CLI experience for RHEL Image Builder"


def test_get_upcoming_changes_with_env(client, api_prefix):
    def settings_override():
        return Settings(upcoming_json_path=Path(__file__).parent.parent.joinpath("fixtures").joinpath("upcoming.json"))

    async def query_rbac_override():
        return [
            {
                "permission": "inventory:*:*",
                "resourceDefinitions": [],
            }
        ]

    async def decode_header_override():
        return "1234"

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[Settings.create] = settings_override
    client.app.dependency_overrides[query_rbac] = query_rbac_override
    client.app.dependency_overrides[decode_header] = decode_header_override

    response = client.get(f"{api_prefix}/upcoming-changes")
    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "New CLI experience for RHEL Image Builder TEST"
