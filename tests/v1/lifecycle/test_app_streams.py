from datetime import date
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from roadmap.common import decode_header
from roadmap.common import query_rbac
from roadmap.config import Settings
from roadmap.data.app_streams import AppStreamEntity
from roadmap.models import SupportStatus
from roadmap.v1.lifecycle.app_streams import AppStreamImplementation
from roadmap.v1.lifecycle.app_streams import RelevantAppStream
from roadmap.v1.lifecycle.app_streams import StringPackage
from tests.utils import SUPPORT_STATUS_TEST_CASES


def test_get_app_streams(api_prefix, client):
    result = client.get(f"{api_prefix}/lifecycle/app-streams")
    data = result.json().get("data", [])

    assert result.status_code == 200
    assert len(data) > 0


def test_get_app_streams_filter(api_prefix, client):
    result = client.get(
        f"{api_prefix}/lifecycle/app-streams", params={"kind": "package", "application_stream_name": "nginx"}
    )
    data = result.json().get("data", [])

    assert result.status_code == 200
    assert len(data) > 0


@pytest.mark.parametrize("version", (8, 9))
def test_get_app_streams_by_version(api_prefix, client, version):
    result = client.get(f"{api_prefix}/lifecycle/app-streams/{version}")
    data = result.json().get("data", [])

    assert result.status_code == 200
    assert len(data) > 0


def test_get_app_streams_by_name(api_prefix, client):
    result = client.get(f"{api_prefix}/lifecycle/app-streams", params={"name": "nginx"})
    data = result.json().get("data", [])
    names = set(item["name"] for item in data)

    assert result.status_code == 200
    assert len(data) > 0
    assert names == {"nginx"}


@pytest.mark.parametrize("version", (8, 9))
def test_get_app_stream_package_names(api_prefix, client, version):
    result = client.get(f"{api_prefix}/lifecycle/app-streams/{version}/packages")
    names = result.json().get("data", [])

    assert result.status_code == 200
    assert len(names) > 0


@pytest.mark.parametrize("version", (8, 9))
def test_get_app_stream_stream_names(api_prefix, client, version):
    result = client.get(f"{api_prefix}/lifecycle/app-streams/{version}/streams")
    names = result.json().get("data", [])

    assert result.status_code == 200
    assert len(names) > 0


def test_get_app_stream_module_info(api_prefix, client):
    result = client.get(f"{api_prefix}/lifecycle/app-streams/8", params={"name": "nginx"})
    data = result.json().get("data", "")
    module_names = set(module["name"] for module in data)

    assert result.status_code == 200
    assert len(data) > 0
    assert module_names == {"nginx"}


def test_get_app_stream_module_info_not_found(api_prefix, client):
    result = client.get(f"{api_prefix}/lifecycle/app-streams/8", params={"name": "NOPE"})
    data = result.json().get("data", "")

    assert result.status_code == 200
    assert len(data) == 0


def test_get_relevant_app_stream(api_prefix, client):
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
    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")
    data = result.json().get("data", "")

    assert result.status_code == 200
    assert len(data) > 0


def test_get_relevant_app_stream_error(api_prefix, client, mocker):
    def settings_override():
        return Settings(rbac_hostname="example.com")

    mocker.patch(
        "roadmap.common.urllib.request.urlopen",
        side_effect=HTTPError(url="url", code=400, hdrs=Message(), msg="Raised intentionally", fp=BytesIO()),
    )
    client.app.dependency_overrides = {}
    client.app.dependency_overrides[Settings.create] = settings_override

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")
    detail = result.json().get("detail", "")

    assert result.status_code == 400
    assert detail == "Raised intentionally"


def test_get_relevant_app_stream_error_building_response(api_prefix, client, mocker):
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
    mocker.patch("roadmap.v1.lifecycle.app_streams.RelevantAppStream", side_effect=ValueError("Raised intentionally"))

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")
    detail = result.json().get("detail", "")

    assert result.status_code == 400
    assert detail == "Raised intentionally"


def test_get_relevant_app_stream_no_rbac_access(api_prefix, client):
    async def query_rbac_override():
        return [{}]

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[query_rbac] = query_rbac_override

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")

    assert result.status_code == 403


def test_get_relevant_app_stream_resource_definitions(api_prefix, client):
    async def query_rbac_override():
        return [
            {
                "permission": "inventory:*:*",
                "resourceDefinitions": [
                    {
                        "attributeFilter": {
                            "key": "group_id",
                            "value": ["ebeaf62a-9713-4dad-8d63-32b51cadbda3"],
                            "operation": "in",
                        },
                    }
                ],
            }
        ]

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[query_rbac] = query_rbac_override

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")

    assert result.status_code == 501
    assert "not yet implemented" in result.json()["detail"].casefold()


def test_get_relevant_app_stream_resource_definitions_with_group_restriction(api_prefix, client):
    """Testing a specific case that used to cause 501s"""

    async def query_rbac_override():
        return [
            {"permission": "inventory:hosts:read", "resourceDefinitions": []},
            {"permission": "inventory:groups:write", "resourceDefinitions": []},
            {"permission": "inventory:groups:read", "resourceDefinitions": []},
            {
                "permission": "inventory:groups:read",
                "resourceDefinitions": [
                    {
                        "attributeFilter": {
                            "key": "group.id",
                            "operation": "in",
                            "value": ["c22abc43-62f9-4a03-94e0-2a49d0e3c3d8"],
                        }
                    }
                ],
            },
        ]

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[query_rbac] = query_rbac_override

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams")

    assert result.status_code == 200


def test_get_revelent_app_stream_related(api_prefix, client, mocker):
    async def query_rbac_override():
        return [
            {
                "permission": "inventory:*:*",
                "resourceDefinitions": [],
            }
        ]

    async def decode_header_override():
        return "1234"

    # Set a specific date for today in order to test that app streams that are
    # already retired are not returned in the results.
    #
    # This test is specifically using the end_date of a FreeRADIUS 3.0
    # app stream that is 2029-05-31.
    #
    # The test data has a host with FreeRADIUS 2.8.
    mock_date = mocker.patch("roadmap.v1.lifecycle.app_streams.date", wraps=date)
    mock_date.today.return_value = date(2030, 6, 1)

    client.app.dependency_overrides = {}
    client.app.dependency_overrides[query_rbac] = query_rbac_override
    client.app.dependency_overrides[decode_header] = decode_header_override

    result = client.get(f"{api_prefix}/relevant/lifecycle/app-streams", params={"related": True})
    data = result.json().get("data", "")
    related_count = sum(1 for item in data if item["related"])
    free_radius_streams = [n for n in data if "freeradius" in n["display_name"].casefold()]

    assert len(free_radius_streams) <= 2, "Got too many related app streams for FreeRADIUS"
    assert related_count, "No related items were returned"
    assert result.status_code == 200
    assert len(data) > 0


def test_app_stream_missing_lifecycle_data():
    """Given a RHEL major version that there is no lifecycle data for,
    ensure the dates are set as expected.
    """
    app_stream = RelevantAppStream(
        name="something",
        display_name="Something 1",
        application_stream_name="App Stream Name",
        start_date=None,
        end_date=None,
        os_major=1,
        support_status=SupportStatus.supported,
        count=4,
        impl=AppStreamImplementation.package,
        rolling=True,
        systems=[],
    )

    assert app_stream.start_date is None


def test_app_stream_package_no_start_date():
    """If no start_date is supplied, ensure the correct start date is added
    based on the initial_product_version.
    """
    package = AppStreamEntity(
        name="aardvark-dns",
        application_stream_name="container-tools",
        end_date=date(1111, 11, 11),
        initial_product_version="9.2",
        stream="1.5.0",
        lifecycle=0,
        rolling=True,
        impl=AppStreamImplementation.package,
    )

    assert package.start_date == date(2023, 5, 10)


def test_app_stream_package_missing_rhel_data():
    """If no start_date is supplied and there is no RHEL lifecycle data available
    ensure the date is set to 1111-11-11.
    """
    package = AppStreamEntity(
        name="aardvark-dns",
        application_stream_name="container-tools",
        end_date=date(1111, 11, 11),
        initial_product_version="5.0",
        stream="1.5.0",
        lifecycle=0,
        rolling=True,
        impl=AppStreamImplementation.package,
    )

    assert package.start_date is None


def test_app_stream_package_single_digit():
    """If a single digit is given for initial_product_version,
    os_minor should be set to None.
    """
    package = AppStreamEntity(
        name="aardvark-dns",
        application_stream_name="container-tools",
        end_date=date(1111, 11, 11),
        initial_product_version="9",
        stream="1.5.0",
        lifecycle=0,
        rolling=True,
        impl=AppStreamImplementation.package,
    )

    assert package.os_minor is None


@pytest.mark.parametrize(
    ("current_date", "app_stream_start", "app_stream_end", "expected_status"), SUPPORT_STATUS_TEST_CASES
)
def test_calculate_support_status_appstream(mocker, current_date, app_stream_start, app_stream_end, expected_status):
    # cannot mock the datetime.date.today directly as it's written in C
    # https://docs.python.org/3/library/unittest.mock-examples.html#partial-mocking
    mock_date = mocker.patch("roadmap.v1.lifecycle.app_streams.date", wraps=date)
    mock_date.today.return_value = current_date

    app_stream = RelevantAppStream(
        name="pkg-name",
        display_name="Pkg Name 1",
        application_stream_name="Pkg Name",
        os_major=1,
        os_minor=1,
        count=4,
        impl=AppStreamImplementation.package,
        rolling=False,
        start_date=app_stream_start,
        end_date=app_stream_end,
        systems=[],
    )

    assert app_stream.support_status == expected_status


@pytest.mark.parametrize(
    ("package", "expected"),
    (
        ("cairo-1.15.12-3.el8.x86_64", ("cairo", "1")),
        ("rpm-build-libs-0:4.16.1.3-29.el9.x86_64", ("rpm-build-libs", "4")),
    ),
)
def test_from_string(package, expected):
    package = StringPackage.from_string(package)

    assert (package.name, package.major) == expected
