import os
import pytest


@pytest.mark.deployment_standalone
@pytest.mark.skipif(
    not os.getenv("ENABLE_DAB_TESTS"),
    reason="Skipping test because ENABLE_DAB_TESTS is not set"
)
def test_dab_collection_download_url_hostnames(settings, galaxy_client, published):
    """
    We want the download url to point at the gateway
    """
    gc = galaxy_client("admin")
    cv_url = 'v3/plugin/ansible/content/published/collections/index/'
    cv_url += f'{published.namespace}/{published.name}/versions/{published.version}/'
    cv_info = gc.get(cv_url)
    download_url = cv_info['download_url']
    assert download_url.startswith(gc.galaxy_root)

    # try to GET the tarball ...
    dl_resp = gc.get(download_url, parse_json=False)
    assert dl_resp.status_code == 200
    assert dl_resp.headers.get('Content-Type') == 'application/gzip'

    # make sure the final redirect was through the gateway ...
    expected_url = gc.galaxy_root.replace('/api/galaxy/', '')
    assert dl_resp.url.startswith(expected_url)

    # now check if we access it from localhost that the download url changes accordingly
    if gc.galaxy_root == "http://jwtproxy:8080/api/galaxy/":
        local_url = os.path.join(gc.galaxy_root, cv_url)
        local_url = local_url.replace("http://jwtproxy:8080", "http://localhost:5001")
        cv_info = gc.get(local_url, auth=("admin", "admin"))

        download_url = cv_info["download_url"]
        assert download_url.startswith("http://localhost:5001")

        # try to GET the tarball ...
        dl_resp = gc.get(download_url, parse_json=False, auth=("admin", "admin"))
        assert dl_resp.status_code == 200
        assert dl_resp.headers.get('Content-Type') == 'application/gzip'
        assert dl_resp.url.startswith("http://localhost:5001")
