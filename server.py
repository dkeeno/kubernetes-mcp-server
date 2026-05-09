#!/usr/bin/env python3
"""
Kubernetes MCP Server
Provides tools for generating Kubernetes YAML manifests and deploying using kubectl.
"""

import asyncio
import json
import subprocess
import yaml
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

server = Server("kubernetes-mcp-server")

K8S_MANIFESTS_DIR = Path.home() / "k8s-manifests"
K8S_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Kubernetes tools."""
    return [
        Tool(
            name="generate_deployment",
            description="Generate a Kubernetes Deployment YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Deployment name"},
                    "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                    "image": {"type": "string", "description": "Container image (e.g., nginx:latest)"},
                    "replicas": {"type": "integer", "description": "Number of replicas", "default": 1},
                    "port": {"type": "integer", "description": "Container port", "default": 80},
                    "env_vars": {"type": "object", "description": "Environment variables"},
                    "resource_limits": {
                        "type": "object",
                        "description": "Resource limits",
                        "properties": {
                            "cpu": {"type": "string", "description": "CPU limit (e.g., 500m)"},
                            "memory": {"type": "string", "description": "Memory limit (e.g., 512Mi)"}
                        }
                    },
                    "labels": {"type": "object", "description": "Labels to apply"}
                },
                "required": ["name", "image"]
            }
        ),
        Tool(
            name="generate_service",
            description="Generate a Kubernetes Service YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"},
                    "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                    "service_type": {
                        "type": "string",
                        "description": "Service type",
                        "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
                        "default": "ClusterIP"
                    },
                    "port": {"type": "integer", "description": "Service port", "default": 80},
                    "target_port": {"type": "integer", "description": "Target port on pods", "default": 80},
                    "selector": {"type": "object", "description": "Pod selector labels"}
                },
                "required": ["name", "selector"]
            }
        ),
        Tool(
            name="generate_configmap",
            description="Generate a Kubernetes ConfigMap YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "ConfigMap name"},
                    "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                    "data": {"type": "object", "description": "ConfigMap data (key-value pairs)"}
                },
                "required": ["name", "data"]
            }
        ),
        Tool(
            name="generate_secret",
            description="Generate a Kubernetes Secret YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Secret name"},
                    "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                    "secret_type": {"type": "string", "description": "Secret type", "default": "Opaque"},
                    "data": {"type": "object", "description": "Secret data (key-value pairs, will be base64 encoded)"}
                },
                "required": ["name", "data"]
            }
        ),
        Tool(
            name="generate_ingress",
            description="Generate a Kubernetes Ingress YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Ingress name"},
                    "namespace": {"type": "string", "description": "Namespace", "default": "default"},
                    "host": {"type": "string", "description": "Hostname"},
                    "service_name": {"type": "string", "description": "Backend service name"},
                    "service_port": {"type": "integer", "description": "Backend service port"},
                    "tls_enabled": {"type": "boolean", "description": "Enable TLS", "default": False},
                    "tls_secret": {"type": "string", "description": "TLS secret name (if TLS enabled)"}
                },
                "required": ["name", "host", "service_name", "service_port"]
            }
        ),
        Tool(
            name="generate_namespace",
            description="Generate a Kubernetes Namespace YAML manifest",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Namespace name"},
                    "labels": {"type": "object", "description": "Labels to apply"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="kubectl_apply",
            description="Apply Kubernetes manifest using kubectl",
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest_path": {"type": "string", "description": "Path to YAML manifest file"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["manifest_path"]
            }
        ),
        Tool(
            name="kubectl_delete",
            description="Delete Kubernetes resources using kubectl",
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest_path": {"type": "string", "description": "Path to YAML manifest file"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["manifest_path"]
            }
        ),
        Tool(
            name="kubectl_get",
            description="Get Kubernetes resources",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "description": "Resource type (pods, deployments, services, etc.)"},
                    "namespace": {"type": "string", "description": "Namespace (optional, default: all)"},
                    "name": {"type": "string", "description": "Resource name (optional, get all if not specified)"},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["resource_type"]
            }
        ),
        Tool(
            name="kubectl_describe",
            description="Describe a Kubernetes resource",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "description": "Resource type"},
                    "name": {"type": "string", "description": "Resource name"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["resource_type", "name"]
            }
        ),
        Tool(
            name="kubectl_logs",
            description="Get logs from a pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "container": {"type": "string", "description": "Container name (optional, for multi-container pods)"},
                    "tail": {"type": "integer", "description": "Number of lines to show from the end", "default": 100},
                    "follow": {"type": "boolean", "description": "Follow log output", "default": False},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["pod_name"]
            }
        ),
        Tool(
            name="kubectl_exec",
            description="Execute a command in a pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name"},
                    "command": {"type": "string", "description": "Command to execute"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "container": {"type": "string", "description": "Container name (optional)"},
                    "context": {"type": "string", "description": "Kubectl context (optional)"}
                },
                "required": ["pod_name", "command"]
            }
        )
    ]


def save_manifest(manifest: Dict, name: str) -> Path:
    """Save a manifest to a file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.yaml"
    filepath = K8S_MANIFESTS_DIR / filename

    with open(filepath, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    return filepath


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls for Kubernetes operations."""

    try:
        if name == "generate_deployment":
            manifest = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": arguments["name"],
                    "namespace": arguments.get("namespace", "default"),
                    "labels": arguments.get("labels", {"app": arguments["name"]})
                },
                "spec": {
                    "replicas": arguments.get("replicas", 1),
                    "selector": {
                        "matchLabels": {"app": arguments["name"]}
                    },
                    "template": {
                        "metadata": {
                            "labels": {"app": arguments["name"]}
                        },
                        "spec": {
                            "containers": [{
                                "name": arguments["name"],
                                "image": arguments["image"],
                                "ports": [{"containerPort": arguments.get("port", 80)}]
                            }]
                        }
                    }
                }
            }

            container = manifest["spec"]["template"]["spec"]["containers"][0]

            if "env_vars" in arguments:
                container["env"] = [{"name": k, "value": v} for k, v in arguments["env_vars"].items()]

            if "resource_limits" in arguments:
                container["resources"] = {
                    "limits": arguments["resource_limits"],
                    "requests": arguments["resource_limits"]
                }

            filepath = save_manifest(manifest, f"deployment-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ Deployment manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "generate_service":
            manifest = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": arguments["name"],
                    "namespace": arguments.get("namespace", "default")
                },
                "spec": {
                    "type": arguments.get("service_type", "ClusterIP"),
                    "selector": arguments["selector"],
                    "ports": [{
                        "port": arguments.get("port", 80),
                        "targetPort": arguments.get("target_port", 80)
                    }]
                }
            }

            filepath = save_manifest(manifest, f"service-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ Service manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "generate_configmap":
            manifest = {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": arguments["name"],
                    "namespace": arguments.get("namespace", "default")
                },
                "data": arguments["data"]
            }

            filepath = save_manifest(manifest, f"configmap-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ ConfigMap manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "generate_secret":
            import base64
            manifest = {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": arguments["name"],
                    "namespace": arguments.get("namespace", "default")
                },
                "type": arguments.get("secret_type", "Opaque"),
                "data": {k: base64.b64encode(v.encode()).decode() for k, v in arguments["data"].items()}
            }

            filepath = save_manifest(manifest, f"secret-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ Secret manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "generate_ingress":
            manifest = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": arguments["name"],
                    "namespace": arguments.get("namespace", "default")
                },
                "spec": {
                    "rules": [{
                        "host": arguments["host"],
                        "http": {
                            "paths": [{
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": arguments["service_name"],
                                        "port": {"number": arguments["service_port"]}
                                    }
                                }
                            }]
                        }
                    }]
                }
            }

            if arguments.get("tls_enabled", False):
                manifest["spec"]["tls"] = [{
                    "hosts": [arguments["host"]],
                    "secretName": arguments.get("tls_secret", f"{arguments['name']}-tls")
                }]

            filepath = save_manifest(manifest, f"ingress-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ Ingress manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "generate_namespace":
            manifest = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": arguments["name"],
                    "labels": arguments.get("labels", {})
                }
            }

            filepath = save_manifest(manifest, f"namespace-{arguments['name']}")
            return [TextContent(
                type="text",
                text=f"✓ Namespace manifest generated\nSaved to: {filepath}\n\n{yaml.dump(manifest, default_flow_style=False, sort_keys=False)}"
            )]

        elif name == "kubectl_apply":
            cmd = ["kubectl", "apply", "-f", arguments["manifest_path"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        elif name == "kubectl_delete":
            cmd = ["kubectl", "delete", "-f", arguments["manifest_path"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        elif name == "kubectl_get":
            cmd = ["kubectl", "get", arguments["resource_type"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            else:
                cmd.append("-A")
            if "name" in arguments:
                cmd.append(arguments["name"])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])
            cmd.extend(["-o", "wide"])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        elif name == "kubectl_describe":
            cmd = ["kubectl", "describe", arguments["resource_type"], arguments["name"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        elif name == "kubectl_logs":
            cmd = ["kubectl", "logs", arguments["pod_name"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            if "container" in arguments:
                cmd.extend(["-c", arguments["container"]])
            if arguments.get("follow", False):
                cmd.append("-f")
            cmd.extend(["--tail", str(arguments.get("tail", 100))])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        elif name == "kubectl_exec":
            cmd = ["kubectl", "exec", arguments["pod_name"]]
            if "namespace" in arguments:
                cmd.extend(["-n", arguments["namespace"]])
            if "container" in arguments:
                cmd.extend(["-c", arguments["container"]])
            if "context" in arguments:
                cmd.extend(["--context", arguments["context"]])
            cmd.extend(["--", "sh", "-c", arguments["command"]])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return [TextContent(
                type="text",
                text=f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
