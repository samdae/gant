---
id: runbook
name: Runbook
description: |
  Collect deployment information via Q&A to generate runbook document.
  Creates comprehensive deployment guide without actual secrets.

  Triggers: runbook, deploy, ops, 배포 문서, 운영 문서
user-invocable: true
version: 2.0.0
triggers:
  - "runbook"
  - "deploy"
  - "ops"
  - "deployment"
requires: []
platform: all
recommended_model: sonnet
allowed-tools:
  - Read
  - Write
  - Glob
  - LS
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Runbook Workflow

Collect all necessary deployment information through Q&A to generate a Launchpad document.

## 💡 Recommended Model

**Sonnet** (documentation task)

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **AskQuestion** | "Please select from the following options" format |
| **Read** | Request user to copy-paste file contents |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              └── runbook.md   # ← This skill's output
```

## ⚠️ Secrets Warning

**Never include actual secret values (passwords, API keys, etc.) in the document.**
→ Only record where/how to retrieve them

---

## Phase 0: Skill Entry

### 0-1. Service Information

```json
{
  "title": "Generate Deployment Launchpad",
  "questions": [
    {
      "id": "service_name",
      "prompt": "Please enter the service name (e.g., report, alert, issue)",
      "options": [
        {"id": "input", "label": "I will provide the name"}
      ]
    },
    {
      "id": "service_port",
      "prompt": "What is the service port?",
      "options": [
        {"id": "input", "label": "I will provide the port (e.g., 8080)"}
      ]
    }
  ]
}
```

### 0-2. Check for Existing Document

```json
{
  "title": "Existing Launchpad",
  "questions": [
    {
      "id": "existing_doc",
      "prompt": "Does runbook.md already exist?",
      "options": [
        {"id": "yes", "label": "Yes - Update it"},
        {"id": "no", "label": "No - Create new"}
      ]
    }
  ]
}
```

---

## Phase 1: Infrastructure Information Collection

### 1-1. Infrastructure Type

```json
{
  "title": "Infrastructure Type",
  "questions": [
    {
      "id": "infra_type",
      "prompt": "What is your deployment infrastructure?",
      "options": [
        {"id": "k8s", "label": "Kubernetes (AKS, EKS, GKE, self-hosted cluster)"},
        {"id": "docker", "label": "Docker / Docker Compose"},
        {"id": "vm", "label": "VM / Bare metal"},
        {"id": "serverless", "label": "Serverless (Lambda, Cloud Functions)"},
        {"id": "other", "label": "Other"}
      ]
    }
  ]
}
```

### 1-2. If Kubernetes Selected

```json
{
  "title": "Kubernetes Configuration",
  "questions": [
    {
      "id": "k8s_provider",
      "prompt": "What is your K8s provider?",
      "options": [
        {"id": "aks", "label": "Azure AKS"},
        {"id": "eks", "label": "AWS EKS"},
        {"id": "gke", "label": "Google GKE"},
        {"id": "self", "label": "Self-hosted cluster"},
        {"id": "other", "label": "Other"}
      ]
    },
    {
      "id": "k8s_namespace",
      "prompt": "What is the namespace? (If different per environment, will ask later)",
      "options": [
        {"id": "input", "label": "I will provide it"}
      ]
    },
    {
      "id": "k8s_manifest",
      "prompt": "Where are the manifest files located? (e.g., k8s/, deploy/)",
      "options": [
        {"id": "input", "label": "I will provide the path"}
      ]
    }
  ]
}
```

### 1-3. If Docker Selected

```json
{
  "title": "Docker Configuration",
  "questions": [
    {
      "id": "dockerfile_path",
      "prompt": "Where is the Dockerfile located?",
      "options": [
        {"id": "input", "label": "I will provide the path (e.g., ./Dockerfile)"}
      ]
    },
    {
      "id": "compose_path",
      "prompt": "Where is docker-compose.yml located? (If none, select 'None')",
      "options": [
        {"id": "input", "label": "I will provide the path"},
        {"id": "none", "label": "None"}
      ]
    },
    {
      "id": "registry",
      "prompt": "What container registry do you use?",
      "options": [
        {"id": "acr", "label": "Azure Container Registry"},
        {"id": "ecr", "label": "AWS ECR"},
        {"id": "gcr", "label": "Google GCR"},
        {"id": "dockerhub", "label": "Docker Hub"},
        {"id": "other", "label": "Other"}
      ]
    }
  ]
}
```

### 1-4. If VM Selected

```json
{
  "title": "VM Configuration",
  "questions": [
    {
      "id": "access_method",
      "prompt": "How do you access the server?",
      "options": [
        {"id": "ssh", "label": "SSH"},
        {"id": "bastion", "label": "Via Bastion Host"},
        {"id": "vpn", "label": "VPN required"},
        {"id": "other", "label": "Other"}
      ]
    },
    {
      "id": "deploy_method",
      "prompt": "What is your deployment method?",
      "options": [
        {"id": "rsync", "label": "rsync / scp"},
        {"id": "git_pull", "label": "git pull"},
        {"id": "ansible", "label": "Ansible"},
        {"id": "other", "label": "Other"}
      ]
    }
  ]
}
```

---

## Phase 2: CI/CD Information Collection

### 2-1. CI/CD Availability

```json
{
  "title": "CI/CD",
  "questions": [
    {
      "id": "has_cicd",
      "prompt": "Do you have a CI/CD pipeline?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide configuration details"},
        {"id": "no", "label": "No - Manual deployment"}
      ]
    }
  ]
}
```

### 2-2. If CI/CD Exists

```json
{
  "title": "CI/CD Configuration",
  "questions": [
    {
      "id": "cicd_tool",
      "prompt": "What CI/CD tool do you use?",
      "options": [
        {"id": "github_actions", "label": "GitHub Actions"},
        {"id": "gitlab_ci", "label": "GitLab CI"},
        {"id": "jenkins", "label": "Jenkins"},
        {"id": "argocd", "label": "ArgoCD"},
        {"id": "azure_devops", "label": "Azure DevOps"},
        {"id": "other", "label": "Other"}
      ]
    },
    {
      "id": "cicd_file",
      "prompt": "Where is the pipeline configuration file located?",
      "options": [
        {"id": "input", "label": "I will provide the path (e.g., .github/workflows/)"}
      ]
    },
    {
      "id": "trigger",
      "prompt": "What triggers deployment?",
      "options": [
        {"id": "push_main", "label": "Push to main/master branch"},
        {"id": "tag", "label": "Tag creation"},
        {"id": "manual", "label": "Manual trigger"},
        {"id": "other", "label": "Other"}
      ]
    }
  ]
}
```

---

## Phase 3: Environment-Specific Configuration Collection

### 3-1. Environment Identification

```json
{
  "title": "Environment Identification",
  "questions": [
    {
      "id": "environments",
      "prompt": "What environments do you have?",
      "options": [
        {"id": "dev_prod", "label": "dev, prod"},
        {"id": "dev_stg_prod", "label": "dev, staging, prod"},
        {"id": "single", "label": "Single environment"},
        {"id": "other", "label": "Other (please specify)"}
      ],
      "allow_multiple": true
    }
  ]
}
```

### 3-2. Per-Environment Details (Repeat for Each Environment)

```json
{
  "title": "{Environment Name} Configuration",
  "questions": [
    {
      "id": "env_url",
      "prompt": "What is the service URL for {environment name}?",
      "options": [
        {"id": "input", "label": "I will provide the URL"}
      ]
    },
    {
      "id": "env_config",
      "prompt": "Where is the configuration file for {environment name}? (.env, config, etc.)",
      "options": [
        {"id": "input", "label": "I will provide the path"}
      ]
    },
    {
      "id": "env_specific",
      "prompt": "Are there any special settings unique to {environment name}?",
      "options": [
        {"id": "yes", "label": "Yes - I will explain"},
        {"id": "no", "label": "No"}
      ]
    }
  ]
}
```

---

## Phase 4: Build/Deploy Command Collection

### 4-1. Build

```json
{
  "title": "Build",
  "questions": [
    {
      "id": "build_command",
      "prompt": "What is the build command? (If none, select 'None')",
      "options": [
        {"id": "input", "label": "I will provide the command (e.g., docker build -t ...)"},
        {"id": "none", "label": "No build step"}
      ]
    },
    {
      "id": "build_prereq",
      "prompt": "Are there any prerequisites before building?",
      "options": [
        {"id": "yes", "label": "Yes - I will explain"},
        {"id": "no", "label": "No"}
      ]
    }
  ]
}
```

### 4-2. Deployment

```json
{
  "title": "Deployment",
  "questions": [
    {
      "id": "deploy_command",
      "prompt": "What is the deployment command?",
      "options": [
        {"id": "input", "label": "I will provide the command (e.g., kubectl apply -f ...)"}
      ]
    },
    {
      "id": "deploy_prereq",
      "prompt": "Are there any prerequisites before deployment? (DB migration, etc.)",
      "options": [
        {"id": "yes", "label": "Yes - I will explain"},
        {"id": "no", "label": "No"}
      ]
    }
  ]
}
```

### 4-3. Rollback

```json
{
  "title": "Rollback",
  "questions": [
    {
      "id": "rollback_command",
      "prompt": "How do you rollback?",
      "options": [
        {"id": "input", "label": "I will provide the command (e.g., kubectl rollout undo ...)"},
        {"id": "unknown", "label": "Not sure"}
      ]
    }
  ]
}
```

---

## Phase 5: Validation/Monitoring Information Collection

### 5-1. Validation

```json
{
  "title": "Validation",
  "questions": [
    {
      "id": "health_check",
      "prompt": "What is the health check URL?",
      "options": [
        {"id": "input", "label": "I will provide the URL (e.g., /health, /api/health)"},
        {"id": "none", "label": "None"}
      ]
    },
    {
      "id": "smoke_test",
      "prompt": "Are there any post-deployment tests to run?",
      "options": [
        {"id": "yes", "label": "Yes - I will explain"},
        {"id": "no", "label": "No"}
      ]
    }
  ]
}
```

### 5-2. Monitoring

```json
{
  "title": "Monitoring",
  "questions": [
    {
      "id": "monitoring_url",
      "prompt": "Do you have a monitoring dashboard URL?",
      "options": [
        {"id": "input", "label": "I will provide the URL"},
        {"id": "none", "label": "None"}
      ]
    },
    {
      "id": "log_access",
      "prompt": "How do you access logs?",
      "options": [
        {"id": "input", "label": "I will explain (e.g., kubectl logs, CloudWatch)"},
        {"id": "unknown", "label": "Not sure"}
      ]
    }
  ]
}
```

---

## Phase 6: Secrets/Configuration Management

### 6-1. Secrets Management

```json
{
  "title": "Secrets Management",
  "questions": [
    {
      "id": "secret_method",
      "prompt": "How do you manage secrets?",
      "options": [
        {"id": "k8s_secret", "label": "K8s Secret"},
        {"id": "vault", "label": "HashiCorp Vault"},
        {"id": "aws_sm", "label": "AWS Secrets Manager"},
        {"id": "azure_kv", "label": "Azure Key Vault"},
        {"id": "env_file", "label": ".env file"},
        {"id": "other", "label": "Other"}
      ]
    },
    {
      "id": "secret_location",
      "prompt": "Where/how are secrets configured? (Do not include actual values)",
      "options": [
        {"id": "input", "label": "I will provide the location/method"}
      ]
    }
  ]
}
```

---

## Phase 7: Notes/Checklist

### 7-1. Pre-Deployment Checklist

```json
{
  "title": "Pre-Deployment Checklist",
  "questions": [
    {
      "id": "pre_deploy_checklist",
      "prompt": "Are there any items to verify before deployment?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide them"},
        {"id": "no", "label": "Nothing specific"}
      ]
    }
  ]
}
```

### 7-2. Cautions

```json
{
  "title": "Cautions",
  "questions": [
    {
      "id": "cautions",
      "prompt": "Are there any deployment cautions?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide them"},
        {"id": "no", "label": "Nothing specific"}
      ]
    }
  ]
}
```

---

## Phase 8: Document Generation

### 8-1. Template

```markdown
# {serviceName} Deployment Launchpad

> This document is used by LLMs to guide deployment.
> Actual secret values are not included.

## 1. Service Information

| Item | Value |
|------|-------|
| Service Name | {serviceName} |
| Port | {port} |
| Repository | {repo_url} |

---

## 2. Infrastructure

### 2.1 Type
{infra_type} ({provider})

### 2.2 Configuration
| Item | Value |
|------|-------|
| {Infrastructure-specific settings...} | |

---

## 3. CI/CD

### 3.1 Tool
{cicd_tool or "Manual deployment"}

### 3.2 Pipeline
- Configuration file: {cicd_file}
- Trigger: {trigger}

---

## 4. Environment-Specific Configuration

### 4.1 {Environment Name}
| Item | Value |
|------|-------|
| URL | {url} |
| Configuration file | {config_path} |
| Special notes | {specific} |

(Repeat for each environment)

---

## 5. Build

### 5.1 Prerequisites
{prereq or "None"}

### 5.2 Build Command
```bash
{build_command}
```

---

## 6. Deployment

### 6.1 Prerequisites
{prereq or "None"}

### 6.2 Deployment Command
```bash
{deploy_command}
```

### 6.3 Rollback Command
```bash
{rollback_command}
```

---

## 7. Validation

### 7.1 Health Check
- URL: {health_check_url}
- Expected response: 200 OK

### 7.2 Smoke Test
{smoke_test or "None"}

---

## 8. Monitoring

| Item | Link/Method |
|------|-------------|
| Dashboard | {dashboard_url} |
| Log Access | {log_access} |

---

## 9. Secrets/Configuration Management

| Item | Method |
|------|--------|
| Management method | {secret_method} |
| Location/Access | {secret_location} |

⚠️ **Actual secret values are not included in this document.**

---

## 10. Pre-Deployment Checklist

- [ ] {checklist_item_1}
- [ ] {checklist_item_2}
- [ ] ...

---

## 11. Cautions

{cautions or "No special cautions"}

---

## Meta Information

| Item | Content |
|------|---------|
| Created | {date} |
| Last Modified | {date} |
| Skill Version | runbook 2.0.0 |
```

### 8-2. Save

```
docs/{serviceName}/runbook.md
```

---

## Phase 9: Completion Report

```markdown
## Deploy Launchpad Creation Complete

### Summary
| Item | Content |
|------|---------|
| Service | {serviceName} |
| Infrastructure | {infra_type} |
| CI/CD | {cicd_tool or "Manual"} |
| Environments | {environments} |

### File
- Created: `docs/{serviceName}/runbook.md`

### Usage
When deploying:
> "{serviceName} please deploy" + @runbook.md
> → LLM reads the document and guides deployment commands

### Next Steps
- Review document content
- If missing information, manually add or re-run this skill
```

---

# Integration Flow

```
[runbook] → runbook.md created
                            │
                            ▼
                    (When deployment needed)
                            │
                    User: "Deploy please" + @runbook.md
                            │
                            ▼
                    LLM reads document and guides deployment commands
```

---

# Cautions

1. **No Secret Values**
   - Never include actual passwords, API keys, etc.
   - Only record where/how to retrieve them

2. **Reinforcement Possible**
   - You may not have all information initially
   - Re-run this skill later or manually edit to enhance

3. **Watch for Environment Differences**
   - dev/staging/prod settings may differ
   - Clearly distinguish in environment-specific sections

4. **Keep Updated**
   - Update document when infrastructure/settings change
