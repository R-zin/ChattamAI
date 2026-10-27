# Deploying ChattamAI on Microsoft Azure

This guide details how to deploy **ChattamAI** (Full-Stack React + FastAPI + FAISS + LangGraph + Nemotron-3.5-VL Vision) to **Azure Container Apps (ACA)**.

---

## 1. Architecture on Azure

Azure Container Apps is a serverless container platform backed by Kubernetes and KEDA, providing automatic scaling, HTTPS termination, health probes, and persistent volume integration:

```
User Web Browser
       │
       ▼ (HTTPS)
Azure Container App Ingress (https://chattamai-prod.<unique>.azurecontainerapps.io)
       │
       ├── (Frontend Routes: /, /assets/*, /results/*) ──> Static React 18 SPA (FastAPI)
       │
       └── (API Routes: /api/*, /auth/*) ──> FastAPI Multi-Agent LangGraph Pipeline
                                                  │
                                                  ├──> External NVIDIA NIM (Nemotron-3.5-VL)
                                                  │
                                                  └──> Azure File Share Mount (/app/data)
                                                         ├── FAISS Vector Store (/app/data/index)
                                                         └── SQLite Database (/app/data/chattamai.db)
```

---

## 2. Prerequisites

1. An active [Azure Subscription](https://azure.microsoft.com/).
2. API Keys for AI Providers:
   - `OPENAI_API_KEY` (embeddings)
   - `GEMINI_API_KEY` (Gemini 2.5 Flash LLM)
   - `NVIDIA_API_KEY` (Nemotron-3.5-VL vision parsing)
   - `SECRET_KEY` (32+ character random string for JWT sessions: `openssl rand -hex 32`)
3. Optional:
   - `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET` (for Google OAuth 2.0 federation)

---

## 3. Method 1: Infrastructure-as-Code via Azure Bicep (Recommended)

The repository provides a complete, one-step Bicep template in [`infra/main.bicep`](../infra/main.bicep).

### Step 1: Install or Open Azure Cloud Shell
You can run this locally with Azure CLI, or directly in your browser using the [Azure Cloud Shell (Bash)](https://shell.azure.com):
```bash
# Verify Azure CLI
az --version
az login
```

### Step 2: Create a Resource Group
```bash
az group create \
  --name rg-chattamai-prod \
  --location eastus
```

### Step 3: Deploy Infrastructure & Storage Mount
Execute the Bicep template:
```bash
az deployment group create \
  --resource-group rg-chattamai-prod \
  --template-file infra/main.bicep \
  --parameters \
    appName="chattamai" \
    environment="prod" \
    secretKey="$(openssl rand -hex 32)" \
    openAiApiKey="sk-..." \
    geminiApiKey="AIza..." \
    nvidiaApiKey="nvapi-..." \
    corsOrigins="https://chattamai-prod.azurecontainerapps.io,http://localhost:5173"
```

*This automatically provisions the Log Analytics Workspace, Azure Container Registry, Azure Storage Account with File Share, ACA Environment, and the Container App with persistent `/app/data` mount.*

### Step 4: Build & Push the Docker Image
Build the container directly inside Azure Container Registry without needing Docker installed locally:
```bash
# Retrieve ACR name from deployment output
ACR_NAME=$(az acr list --resource-group rg-chattamai-prod --query "[0].name" -o tsv)

# Submit server-side build to ACR
az acr build \
  --registry "$ACR_NAME" \
  --image chattamai:latest \
  --image chattamai:v1.0.0 \
  .
```

### Step 5: Update Container App to Use the New Image
```bash
az containerapp update \
  --name chattamai-prod \
  --resource-group rg-chattamai-prod \
  --image "${ACR_NAME}.azurecr.io/chattamai:latest"
```

---

## 4. Method 2: Automated CI/CD via GitHub Actions

The repository includes a production deployment workflow in [`.github/workflows/deploy-azure.yml`](../.github/workflows/deploy-azure.yml).

### Step 1: Create an Azure Service Principal
In Azure Cloud Shell or local terminal:
```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "sp-chattamai-github-deploy" \
  --role "Contributor" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-chattamai-prod" \
  --json-auth
```

### Step 2: Configure GitHub Repository Secrets
Navigate to your GitHub Repository **Settings > Secrets and variables > Actions** and add:
- `AZURE_CREDENTIALS`: Paste the complete JSON output from the command above.
- `AZURE_RESOURCE_GROUP`: `rg-chattamai-prod`
- `AZURE_CONTAINER_APP_NAME`: `chattamai-prod`
- `AZURE_CONTAINER_REGISTRY`: `your-acr-name`

Every push to `main` will automatically build the container image, push to Azure Container Registry, deploy the updated revision, and run a live `/api/health` verification probe.

---

## 5. Method 3: Deployment via Azure Portal UI

If you do not have Azure CLI installed locally, you can deploy completely via the Azure Portal:

### 1. Create Azure Container Registry (ACR)
1. Go to **Azure Portal > Create a resource > Container Registry**.
2. Select your subscription and resource group (`rg-chattamai-prod`).
3. Set **Registry name** (e.g. `chattamaiacr`) and SKU to **Basic**.
4. Enable **Admin user** under **Access keys**.

### 2. Build Container Image via Cloud Shell
Open the Azure Cloud Shell at the top right of the Azure portal:
```bash
git clone https://github.com/R-zin/ChattamAI.git
cd ChattamAI
az acr build --registry chattamaiacr --image chattamai:latest .
```

### 3. Create Azure Container App
1. Go to **Create a resource > Container App**.
2. **Basics**:
   - Resource Group: `rg-chattamai-prod`
   - Container App name: `chattamai-prod`
   - Region: East US (or closest to your users)
3. **App settings**:
   - Image source: **Azure Container Registry**
   - Registry: `chattamaiacr`
   - Image: `chattamai`
   - Tag: `latest`
   - CPU / Memory: `1.0 vCPU, 2.0 GiB`
4. **Ingress**:
   - Enable Ingress: **Enabled**
   - Ingress traffic: **Accepting traffic from anywhere**
   - Target port: `8000`
5. **Environment Variables**:
   Add the following variables in the **Containers** tab:
   - `PORT`: `8000`
   - `DATABASE_URL`: `sqlite:////app/data/chattamai.db`
   - `KBR_DATA_DIR`: `/app/data/kbr`
   - `INDEX_DIR`: `/app/data/index`
   - `SECRET_KEY`: *(Secure random string)*
   - `OPENAI_API_KEY`: *(Your OpenAI key)*
   - `GEMINI_API_KEY`: *(Your Google AI Studio key)*
   - `NVIDIA_API_KEY`: *(Your NVIDIA NIM key)*
   - `AUTH_REQUIRED`: `true`
   - `CORS_ORIGINS`: `https://chattamai-prod.<your-subdomain>.azurecontainerapps.io`
6. Click **Review + Create**.

---

## 6. Configuring Persistent Storage for FAISS and SQLite

To prevent losing uploaded rules, index embeddings, and user accounts during container scaling:

1. Create a Storage Account in Azure Portal (**Standard general-purpose v2**).
2. Go to **File shares** > Create a share named `chattam-data`.
3. In your **Container Apps Environment**:
   - Go to **Azure Files storage** > **Add**.
   - Select your storage account and the `chattam-data` share.
   - Set Mount name: `chattam-volume`.
4. In your **Container App (`chattamai-prod`)**:
   - Go to **Revision management** > **Edit and deploy**.
   - Under **Volume mounts**, attach `chattam-volume` to `/app/data`.
   - Click **Save** and deploy revision.

---

## 7. Post-Deployment Verification

1. **Verify Health Endpoint**:
   ```bash
   curl https://chattamai-prod.<your-region>.azurecontainerapps.io/api/health
   ```
   Expected response:
   ```json
   {
     "status": "ok",
     "index_size": 24,
     "embeddings_ready": true,
     "llm_ready": true,
     "llm_provider": "gemini",
     "llm_model": "gemini-2.5-flash"
   }
   ```
2. **Access Web Application**:
   Open `https://chattamai-prod.<your-region>.azurecontainerapps.io/` in any browser. The Swiss Modernist Visual Workbench and Login screens will be served directly by the container.
3. **Configure Google OAuth Redirect URI**:
   If utilizing Google sign-in, add the Azure FQDN callback to your Google Cloud Console Authorized Redirect URIs:
   `https://chattamai-prod.<your-region>.azurecontainerapps.io/login`
