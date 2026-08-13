import os
import pytest


@pytest.mark.skipif(os.getenv('RUN_K8S_INTEGRATION') != '1', reason='Requires local k3d cluster')
def test_kubernetes_adapter_can_connect():
    from app.kubernetes.client import KubernetesPlatform
    KubernetesPlatform().ping()
