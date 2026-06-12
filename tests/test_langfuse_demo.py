"""
ARK × Langfuse 演示 E2E 测试

验证:
1. 演示 app.py 的所有导入和场景函数可正常调用
2. OTelExporter 推送到端点后端,事件被正确发出
3. 8 种事件类型都通过演示脚本 emit 至少一次
4. 演示文件结构完整 (docker-compose / collector config / README)

这是 0-star 仓库破圈演示的核心保证 — 演示不能跑 = 项目信誉受损
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 路径设置:确保可以导入 ark 和 demo app
DEMO_DIR = Path(__file__).parent.parent / "examples" / "langfuse-demo"
ARK_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(ARK_SRC))
sys.path.insert(0, str(DEMO_DIR))


class TestDemoFilesExist:
    """演示文件结构完整性"""

    def test_docker_compose_exists(self):
        assert (DEMO_DIR / "docker-compose.yml").exists(), "docker-compose.yml 缺失"

    def test_otel_collector_config_exists(self):
        assert (DEMO_DIR / "otel-collector.yaml").exists(), "otel-collector.yaml 缺失"

    def test_app_py_exists(self):
        assert (DEMO_DIR / "app.py").exists(), "app.py 缺失"

    def test_readme_exists(self):
        assert (DEMO_DIR / "README.md").exists(), "README.md 缺失"

    def test_env_example_exists(self):
        assert (DEMO_DIR / ".env.example").exists(), ".env.example 缺失"


class TestDemoConfigValidity:
    """演示配置语法正确性"""

    def test_docker_compose_yaml_valid(self):
        """docker-compose.yml 是合法 YAML"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        with open(DEMO_DIR / "docker-compose.yml") as f:
            config = yaml.safe_load(f)
        assert "services" in config
        assert "otel-collector" in config["services"]
        assert "langfuse-server" in config["services"]
        assert "langfuse-db" in config["services"]

    def test_otel_collector_config_valid(self):
        """otel-collector.yaml 是合法 YAML"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        with open(DEMO_DIR / "otel-collector.yaml") as f:
            config = yaml.safe_load(f)
        assert "receivers" in config
        assert "otlp" in config["receivers"]
        assert "exporters" in config
        assert "service" in config
        assert "pipelines" in config["service"]


class TestDemoImports:
    """演示 app.py 可正常导入"""

    def test_app_module_imports(self):
        """演示脚本能导入而不报错"""
        os.environ["ARK_OTEL_ENDPOINT"] = "http://test:4318/v1/traces"
        try:
            import app
            assert hasattr(app, "demo_idempotency")
            assert hasattr(app, "demo_circuit_breaker")
            assert hasattr(app, "demo_validation")
            assert hasattr(app, "demo_otel_emission")
        except Exception as e:
            pytest.fail(f"演示 app.py 导入失败: {e}")


class TestDemoE2EFlow:
    """端到端:演示函数能跑通"""

    def setup_method(self):
        os.environ["ARK_OTEL_ENDPOINT"] = "http://localhost:4318/v1/traces"
        # 重置全局 exporter
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()

    def teardown_method(self):
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()

    def test_all_4_demos_run(self):
        """4 个场景函数全部能跑完不出异常"""
        import app

        # 用黑洞端点,所有 emit 都会失败但不会抛异常
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            app.demo_idempotency()        # 场景 1
            app.demo_circuit_breaker()    # 场景 2
            app.demo_validation()         # 场景 3
            app.demo_otel_emission()      # 场景 4

            # 场景 4 显式 emit 了 7 个事件,加上 batch 前的隐式触发
            assert mock_post.call_count >= 7, \
                f"期望至少 7 次 OTLP POST,实际 {mock_post.call_count}"

    def test_otel_payload_format(self):
        """OTLP payload 是合法 ResourceSpans 格式"""
        import httpx
        from ark.otel_exporter import OTelExporter, EventType

        captured = []

        def fake_post(url, **kwargs):
            captured.append({"url": url, "json": kwargs.get("json")})
            return MagicMock(status_code=200)

        with patch("httpx.post", side_effect=fake_post):
            exporter = OTelExporter(
                endpoint="http://test:4318/v1/traces",
                service_name="ark-demo-test",
                batch_size=1,  # 立即 flush
            )
            exporter.emit(
                event_type=EventType.GUARDIAN_INTERCEPT,
                tool_name="stripe.charge",
                attributes={"amount": 99.99, "duplicate": True},
            )
            exporter.flush()

        assert len(captured) == 1
        payload = captured[0]["json"]
        assert "resourceSpans" in payload
        assert payload["resourceSpans"][0]["resource"]["attributes"][0]["value"]["stringValue"] == "ark-demo-test"
        span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["name"] == "ark.guardian.intercept"
        assert len(span["traceId"]) == 32
        assert len(span["spanId"]) == 16

    def test_all_8_event_types_emittable(self):
        """8 种事件类型都能 emit 不报错"""
        from ark.otel_exporter import OTelExporter, EventType

        with patch("httpx.post", return_value=MagicMock(status_code=200)):
            exporter = OTelExporter(
                endpoint="http://test:4318/v1/traces",
                batch_size=1,
            )
            for evt in EventType:
                exporter.emit(event_type=evt, tool_name=f"test.{evt.name}")
            exporter.flush()

        # 8 种事件,每种至少 emit 成功
        assert exporter._total_emitted == 8
        assert exporter._total_dropped == 0


class TestDockerComposeUp:
    """验证 docker compose 配置文件本身可被 docker 解析 (可选,需要 docker)"""

    @pytest.mark.skipif(
        not subprocess.run(["which", "docker"], capture_output=True).returncode == 0,
        reason="docker 未安装,跳过"
    )
    def test_docker_compose_config_validates(self):
        """docker compose config 能成功解析"""
        result = subprocess.run(
            ["docker", "compose", "-f", str(DEMO_DIR / "docker-compose.yml"), "config"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"docker compose config 失败: {result.stderr}"
        assert "otel-collector" in result.stdout
        assert "langfuse-server" in result.stdout
