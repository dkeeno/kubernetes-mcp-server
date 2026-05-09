# Kubernetes MCP Server

An MCP server that provides tools for generating Kubernetes YAML manifests and deploying using kubectl.

## Features

### Manifest Generation
- **generate_deployment**: Create Deployment manifests with resource limits, env vars
- **generate_service**: Create Service manifests (ClusterIP, NodePort, LoadBalancer)
- **generate_configmap**: Create ConfigMap manifests
- **generate_secret**: Create Secret manifests (auto base64 encoding)
- **generate_ingress**: Create Ingress manifests with optional TLS
- **generate_namespace**: Create Namespace manifests

### Kubectl Operations
- **kubectl_apply**: Apply manifests to cluster
- **kubectl_delete**: Delete resources from cluster
- **kubectl_get**: List resources
- **kubectl_describe**: Describe resources in detail
- **kubectl_logs**: Get pod logs
- **kubectl_exec**: Execute commands in pods

## Prerequisites

- Python 3.10+
- kubectl installed and configured
- Access to a Kubernetes cluster (kubeconfig set up)

## Installation

```bash
cd kubernetes-mcp-server
pip install -r requirements.txt
```

## Kubernetes Access

Ensure kubectl is configured:

```bash
# Verify connection
kubectl cluster-info

# Check current context
kubectl config current-context

# List available contexts
kubectl config get-contexts
```

## Configuration

Add to your Claude Code settings (~/.claude/settings.json):

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "python",
      "args": ["/Users/youruser/Documents/Base/DevOps-ClaudeAi/test-cases/SM1/my-first-vpc/kubernetes-mcp-server/server.py"]
    }
  }
}
```

## Usage Examples

### Generate Manifests

```
User: "Generate a deployment for nginx with 3 replicas"
Claude: [calls generate_deployment with name=nginx, image=nginx:latest, replicas=3]

User: "Create a LoadBalancer service for the nginx deployment"
Claude: [calls generate_service with service_type=LoadBalancer, selector={app: nginx}]

User: "Generate a configmap with database connection settings"
Claude: [calls generate_configmap with data]
```

### Deploy to Cluster

```
User: "Apply the nginx deployment to the cluster"
Claude: [calls kubectl_apply with manifest path]

User: "Get all pods in the default namespace"
Claude: [calls kubectl_get with resource_type=pods, namespace=default]

User: "Show me the logs from the nginx pod"
Claude: [calls kubectl_logs with pod_name]
```

## Manifest Storage

Generated manifests are automatically saved to `~/k8s-manifests/` with timestamps:
- `deployment-nginx_20260417_143022.yaml`
- `service-nginx_20260417_143045.yaml`

This allows you to:
- Track generated configurations
- Version control your manifests
- Re-apply manifests later
- Review what was created

## Security Notes

⚠️ **IMPORTANT**:
- This server can deploy resources to your Kubernetes cluster
- Always review generated manifests before applying
- Use RBAC to limit kubectl permissions
- Be cautious with kubectl_exec (can run arbitrary commands in pods)
- Secrets are base64 encoded (not encrypted) - use proper secret management solutions

## Recommended RBAC Policy

Create a ServiceAccount with limited permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: mcp-deployer
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: mcp-deployer-role
  namespace: default
rules:
- apiGroups: ["", "apps", "networking.k8s.io"]
  resources: ["deployments", "services", "configmaps", "secrets", "ingresses"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: mcp-deployer-binding
  namespace: default
subjects:
- kind: ServiceAccount
  name: mcp-deployer
roleRef:
  kind: Role
  name: mcp-deployer-role
  apiGroup: rbac.authorization.k8s.io
```

## Working with Multiple Clusters

Use the `context` parameter to target different clusters:

```
User: "Deploy to production cluster"
Claude: [calls kubectl_apply with context=prod-cluster]

User: "List pods in staging"
Claude: [calls kubectl_get with context=staging-cluster]
```

## Error Handling

The server provides detailed kubectl error messages:
- Resource already exists
- Permission denied (RBAC)
- Invalid manifest syntax
- Connection errors
- Resource not found
