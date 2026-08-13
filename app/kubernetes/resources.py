def quota_body(namespace: str, cpu: str, memory: str, storage: str, max_pods: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {"name": "environment-quota", "namespace": namespace},
        "spec": {
            "hard": {
                "requests.cpu": cpu,
                "requests.memory": memory,
                "requests.storage": storage,
                "limits.cpu": cpu,
                "limits.memory": memory,
                "pods": str(max_pods),
                "persistentvolumeclaims": "4",
            }
        },
    }


def limit_range_body(namespace: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "LimitRange",
        "metadata": {"name": "defaults", "namespace": namespace},
        "spec": {
            "limits": [
                {
                    "type": "Container",
                    "defaultRequest": {"cpu": "100m", "memory": "128Mi"},
                    "default": {"cpu": "500m", "memory": "512Mi"},
                }
            ]
        },
    }
