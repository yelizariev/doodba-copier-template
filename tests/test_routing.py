import uuid
from pathlib import Path

import pytest
import requests
from copier import copy
from plumbum import local
from plumbum.cmd import docker_compose
from plumbum.machines.local import LocalCommand
from requests.exceptions import ConnectionError


def test_multiple_domains(
    cloned_template: Path,
    docker: LocalCommand,  # Just as a marker
    supported_odoo_version: float,
    tmp_path: Path,
    traefik_host: str,
):
    """Test multiple domains are produced properly."""
    data = {
        "odoo_version": supported_odoo_version,
        "project_name": uuid.uuid4().hex,
        "domains_prod": {
            f"main.{traefik_host}.sslip.io": [
                f"alt0.main.{traefik_host}.sslip.io",
                f"alt1.main.{traefik_host}.sslip.io",
            ],
            f"secondary.{traefik_host}.sslip.io": [
                f"alt0.secondary.{traefik_host}.sslip.io",
                f"alt1.secondary.{traefik_host}.sslip.io",
            ],
            f"third.{traefik_host}.sslip.io": [],
        },
        "domains_staging": [
            f"demo0.{traefik_host}.sslip.io",
            f"demo1.{traefik_host}.sslip.io",
        ],
    }
    with local.cwd(tmp_path):
        copy(
            src_path=str(cloned_template),
            dst_path=".",
            vcs_ref="test",
            force=True,
            data=data,
        )
        try:
            docker_compose("-f", "prod.yaml", "up", "-d")
            for main_domain, alt_list in data["domains_prod"].items():
                for alt_domain in alt_list + [main_domain]:
                    response = requests.get(f"http://{alt_domain}/web/login")
                    assert response.ok
                    assert response.url == f"http://{main_domain}/web/login"
            with pytest.raises(ConnectionError):
                requests.get(f"http://missing.{traefik_host}.sslip.io")
            docker_compose("-f", "prod.yaml", "down")
            docker_compose("-f", "test.yaml", "up", "-d")
            for staging_domain in data["domains_staging"]:
                response = requests.get(f"http://{staging_domain}/web/login")
                assert response.ok
                assert response.url == f"http://{staging_domain}/web/login"
            with pytest.raises(ConnectionError):
                requests.get(f"http://missing.{traefik_host}.sslip.io")
        finally:
            docker_compose("-f", "test.yaml", "down", "--volumes")
