import base64
import logging
import secrets
import time
from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.client import ApiException

from app.config import get_settings
from app.kubernetes.resources import limit_range_body, quota_body
from app.models import Environment

log = logging.getLogger(__name__)


class ProvisioningError(RuntimeError):
    pass


@dataclass
class ComponentHealth:
    name: str
    healthy: bool
    message: str | None = None


class KubernetesPlatform:
    """Small, explicit Kubernetes adapter.

    Resources use deterministic names and server-side patch/create behavior. That makes
    provisioning safe to retry after an API or worker restart instead of assuming a clean slate.
    """

    def __init__(self):
        s = get_settings()
        config.load_kube_config(config_file=s.kubeconfig_path, context=s.kubernetes_context)
        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()
        self.networking = client.NetworkingV1Api()

    def ping(self) -> None:
        self.core.get_api_resources()

    @staticmethod
    def _apply(create, patch, name: str, namespace: str | None, body: dict):
        try:
            if namespace:
                return create(namespace=namespace, body=body)
            return create(body=body)
        except ApiException as exc:
            if exc.status != 409:
                raise
            if namespace:
                return patch(name=name, namespace=namespace, body=body)
            return patch(name=name, body=body)

    def ensure_namespace(self, env: Environment):
        body = {"metadata": {"name": env.namespace, "labels": {"managed-by": "student-platform", "environment-id": env.id}}}
        self._apply(self.core.create_namespace, self.core.patch_namespace, env.namespace, None, body)

    def ensure_controls(self, env: Environment):
        a = env.allocation
        q = quota_body(env.namespace, a.cpu_limit, a.memory_limit, a.storage_limit, a.max_pods)
        self._apply(self.core.create_namespaced_resource_quota, self.core.patch_namespaced_resource_quota, "environment-quota", env.namespace, q)
        lr = limit_range_body(env.namespace)
        self._apply(self.core.create_namespaced_limit_range, self.core.patch_namespaced_limit_range, "defaults", env.namespace, lr)

    def ensure_secret(self, env: Environment) -> dict[str, str]:
        name = "environment-credentials"
        try:
            existing = self.core.read_namespaced_secret(name, env.namespace)
            return {k: base64.b64decode(v).decode() for k, v in (existing.data or {}).items()}
        except ApiException as exc:
            if exc.status != 404:
                raise
        if env.template_id == "backend":
            values = {
                "POSTGRES_USER": "student",
                "POSTGRES_PASSWORD": secrets.token_urlsafe(20),
                "POSTGRES_DB": "studentdb",
                "REDIS_URL": "redis://redis:6379/0",
            }
        else:
            values = {
                "MINIO_ROOT_USER": "student",
                "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(20),
                "JUPYTER_TOKEN": secrets.token_urlsafe(20),
                "MINIO_ENDPOINT": "http://minio:9000",
            }
        body = client.V1Secret(
            metadata=client.V1ObjectMeta(name=name),
            string_data=values,
            type="Opaque",
        )
        self.core.create_namespaced_secret(env.namespace, body)
        return values

    def _deployment(self, env: Environment, name: str, image: str, ports=None, env_vars=None, command=None, args=None, readiness_probe=None, volume_name=None, mount_path=None):
        ports = [client.V1ContainerPort(container_port=p) for p in (ports or [])]
        env_list = []
        for var in env_vars or []:
            if isinstance(var, tuple):
                env_list.append(client.V1EnvVar(name=var[0], value=var[1]))
            else:
                env_list.append(client.V1EnvVar(
                    name=var,
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(name="environment-credentials", key=var)
                    ),
                ))
        container = client.V1Container(
            name=name,
            image=image,
            ports=ports,
            env=env_list,
            command=command,
            args=args,
            resources=client.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "500m", "memory": "512Mi"},
            ),
            readiness_probe=readiness_probe,
            volume_mounts=[client.V1VolumeMount(name=volume_name, mount_path=mount_path)] if volume_name else None,
        )
        labels = {"app": name, "environment-id": env.id}
        body = client.V1Deployment(
            metadata=client.V1ObjectMeta(name=name, labels=labels),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(match_labels={"app": name}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=client.V1PodSpec(
                        containers=[container],
                        volumes=[client.V1Volume(name=volume_name, persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=volume_name))] if volume_name else None,
                    ),
                ),
            ),
        )
        self._apply(self.apps.create_namespaced_deployment, self.apps.patch_namespaced_deployment, name, env.namespace, body)


    def _pvc(self, env: Environment, name: str, size: str):
        body = client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1VolumeResourceRequirements(requests={"storage": size}),
            ),
        )
        self._apply(self.core.create_namespaced_persistent_volume_claim, self.core.patch_namespaced_persistent_volume_claim, name, env.namespace, body)

    @staticmethod
    def _tcp_probe(port: int):
        return client.V1Probe(tcp_socket=client.V1TCPSocketAction(port=port), initial_delay_seconds=3, period_seconds=3, failure_threshold=20)

    @staticmethod
    def _http_probe(port: int, path: str):
        return client.V1Probe(http_get=client.V1HTTPGetAction(port=port, path=path), initial_delay_seconds=3, period_seconds=3, failure_threshold=20)

    @staticmethod
    def _exec_probe(command: list[str]):
        return client.V1Probe(_exec=client.V1ExecAction(command=command), initial_delay_seconds=3, period_seconds=3, failure_threshold=20)

    def _service(self, env: Environment, name: str, port: int, target: int | None = None):
        body = client.V1Service(
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1ServiceSpec(
                selector={"app": name},
                ports=[client.V1ServicePort(port=port, target_port=target or port)],
            ),
        )
        self._apply(self.core.create_namespaced_service, self.core.patch_namespaced_service, name, env.namespace, body)

    def ensure_workloads(self, env: Environment):
        if env.template_id == "backend":
            self._pvc(env, "postgres-data", "2Gi")
            self._deployment(
                env, "postgres", "postgres:16-alpine", [5432],
                ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"],
                readiness_probe=self._exec_probe(["pg_isready", "-U", "student", "-d", "studentdb"]),
                volume_name="postgres-data", mount_path="/var/lib/postgresql/data",
            )
            self._service(env, "postgres", 5432)
            self._deployment(env, "redis", "redis:7-alpine", [6379], readiness_probe=self._exec_probe(["redis-cli", "ping"]))
            self._service(env, "redis", 6379)
            self._deployment(
                env,
                "fastapi",
                "student-platform-backend:local",
                [8000],
                [("DATABASE_HOST", "postgres"), ("REDIS_HOST", "redis")],
                readiness_probe=self._http_probe(8000, "/health"),
            )
            self._service(env, "fastapi", 80, 8000)
        else:
            self._pvc(env, "minio-data", "2Gi")
            self._deployment(
                env,
                "minio",
                "minio/minio:latest",
                [9000, 9001],
                ["MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"],
                args=["server", "/data", "--console-address", ":9001"],
                readiness_probe=self._http_probe(9000, "/minio/health/ready"),
                volume_name="minio-data", mount_path="/data",
            )
            self._service(env, "minio", 9000)
            self._deployment(
                env,
                "jupyter",
                "quay.io/jupyter/pyspark-notebook:latest",
                [8888],
                ["JUPYTER_TOKEN", "MINIO_ENDPOINT"],
                readiness_probe=self._tcp_probe(8888),
            )
            self._service(env, "jupyter", 80, 8888)

    def ensure_ingress(self, env: Environment) -> str:
        settings = get_settings()
        short = env.id.split("-")[0]
        host = f"{env.template_id}-{short}.localhost"
        service = "fastapi" if env.template_id == "backend" else "jupyter"
        body = client.V1Ingress(
            metadata=client.V1ObjectMeta(name="environment"),
            spec=client.V1IngressSpec(
                rules=[client.V1IngressRule(
                    host=host,
                    http=client.V1HTTPIngressRuleValue(paths=[client.V1HTTPIngressPath(
                        path="/",
                        path_type="Prefix",
                        backend=client.V1IngressBackend(
                            service=client.V1IngressServiceBackend(
                                name=service,
                                port=client.V1ServiceBackendPort(number=80),
                            )
                        ),
                    )]),
                )]
            ),
        )
        self._apply(self.networking.create_namespaced_ingress, self.networking.patch_namespaced_ingress, "environment", env.namespace, body)
        return f"http://{host}:{settings.ingress_port}"

    def wait_ready(self, env: Environment, timeout: int = 180) -> list[ComponentHealth]:
        required = ["postgres", "redis", "fastapi"] if env.template_id == "backend" else ["minio", "jupyter"]
        deadline = time.time() + timeout
        last = []
        while time.time() < deadline:
            last = self.health(env)
            if all(x.healthy for x in last if x.name in required) and len(last) >= len(required):
                if env.template_id == "data":
                    last.append(ComponentHealth("spark", True, "Spark is bundled with the Jupyter PySpark image"))
                return last
            time.sleep(3)
        details = "; ".join(f"{x.name}: {x.message}" for x in last)
        raise ProvisioningError(f"Workloads did not become ready before timeout. {details}")

    def health(self, env: Environment) -> list[ComponentHealth]:
        required = ["postgres", "redis", "fastapi"] if env.template_id == "backend" else ["minio", "jupyter"]
        out = []
        for name in required:
            try:
                dep = self.apps.read_namespaced_deployment(name, env.namespace)
                healthy = (dep.status.available_replicas or 0) >= 1
                msg = "Healthy" if healthy else "Waiting for workload readiness"
                out.append(ComponentHealth(name, healthy, msg))
            except ApiException as exc:
                out.append(ComponentHealth(name, False, f"Resource unavailable ({exc.status})"))
        if env.template_id == "data" and all(x.healthy for x in out):
            out.append(ComponentHealth("spark", True, "Available inside Jupyter"))
        return out

    def get_credentials(self, env: Environment) -> dict[str, str]:
        secret = self.core.read_namespaced_secret("environment-credentials", env.namespace)
        return {k: base64.b64decode(v).decode() for k, v in (secret.data or {}).items()}

    def get_logs(self, env: Environment) -> dict[str, str]:
        result = {}
        for h in self.health(env):
            if h.name == "spark":
                continue
            pods = self.core.list_namespaced_pod(env.namespace, label_selector=f"app={h.name}").items
            if not pods:
                result[h.name] = "No runtime logs available yet."
                continue
            try:
                result[h.name] = self.core.read_namespaced_pod_log(pods[0].metadata.name, env.namespace, tail_lines=200)
            except ApiException as exc:
                result[h.name] = f"Unable to read logs: {exc.reason}"
        return result

    def scale(self, env: Environment, replicas: int):
        names = ["postgres", "redis", "fastapi"] if env.template_id == "backend" else ["minio", "jupyter"]
        for name in names:
            self.apps.patch_namespaced_deployment_scale(name, env.namespace, {"spec": {"replicas": replicas}})

    def delete(self, env: Environment):
        try:
            self.core.delete_namespace(env.namespace)
        except ApiException as exc:
            if exc.status != 404:
                raise
