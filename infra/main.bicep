@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Base application and environment name.')
@minLength(3)
@maxLength(24)
param appName string = 'chattamai'

@description('Environment stage (prod, staging, dev).')
param environment string = 'prod'

@description('Container image tag to deploy (e.g. myacr.azurecr.io/chattamai:v1.0.0).')
param containerImage string = 'mcr.microsoft.com/azuredocs/aci-helloworld:latest'

@description('CPU cores allocated to the container instance.')
param cpu string = '1.0'

@description('Memory allocated to the container instance.')
param memory string = '2.0Gi'

@description('Minimum container replicas (0 for scale-to-zero, 1+ for high availability).')
param minReplicas int = 1

@description('Maximum container replicas.')
param maxReplicas int = 5

// --- Secrets and API Keys ---
@secure()
@description('Secret key used for JWT signing and session validation.')
param secretKey string

@secure()
@description('OpenAI API Key for text-embedding-3-small embeddings.')
param openAiApiKey string = ''

@secure()
@description('Google Gemini API Key for Gemini 2.5 Flash LLM analysis.')
param geminiApiKey string = ''

@secure()
@description('NVIDIA NIM API Key for Nemotron-3.5-VL architectural blueprint vision.')
param nvidiaApiKey string = ''

@secure()
@description('Anthropic API Key for Claude LLM integration (optional).')
param anthropicApiKey string = ''

@secure()
@description('Admin Key for privileged registration and management endpoints.')
param adminKey string = ''

@secure()
@description('Google OAuth 2.0 Client ID.')
param googleClientId string = ''

@secure()
@description('Google OAuth 2.0 Client Secret.')
param googleClientSecret string = ''

@description('Redirect URI for Google OAuth callback.')
param googleRedirectUri string = ''

@description('Comma-delimited CORS allowed origins.')
param corsOrigins string = 'http://localhost:5173,http://localhost:8000'

@description('Enforce mandatory authentication on RAG endpoints.')
param authRequired bool = true

@description('Enforce mandatory TOTP 2FA step-up authentication.')
param totpRequired bool = false

// --- Resource Unique Names ---
var uniqueSuffix = uniqueString(resourceGroup().id)
var logAnalyticsName = '${appName}-logs-${uniqueSuffix}'
var acrName = '${replace(appName, '-', '')}acr${uniqueSuffix}'
var storageAccountName = 'st${replace(appName, '-', '')}${take(uniqueSuffix, 8)}'
var fileShareName = 'chattam-data'
var appEnvName = '${appName}-env-${uniqueSuffix}'
var containerAppName = '${appName}-${environment}'

// 1. Log Analytics Workspace for Container Monitoring & Logs
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// 2. Azure Container Registry (ACR)
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// 3. Azure Storage Account & File Share for Persistent FAISS & SQLite Storage
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: fileShareName
  properties: {
    shareQuota: 50
  }
}

// 4. Azure Container Apps Managed Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: appEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// 5. Mount Azure File Share into ACA Managed Environment
resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: containerAppEnv
  name: 'chattam-storage-mount'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: fileShare.name
      accessMode: 'ReadWrite'
    }
  }
}

// 6. Azure Container App (FastAPI Backend + React Frontend Bundle)
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  dependsOn: [
    envStorage
  ]
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'secret-key'
          value: secretKey
        }
        {
          name: 'openai-api-key'
          value: openAiApiKey
        }
        {
          name: 'gemini-api-key'
          value: geminiApiKey
        }
        {
          name: 'nvidia-api-key'
          value: nvidiaApiKey
        }
        {
          name: 'anthropic-api-key'
          value: anthropicApiKey
        }
        {
          name: 'admin-key'
          value: adminKey
        }
        {
          name: 'google-client-id'
          value: googleClientId
        }
        {
          name: 'google-client-secret'
          value: googleClientSecret
        }
      ]
    }
    template: {
      volumes: [
        {
          name: 'data-volume'
          storageType: 'AzureFile'
          storageName: 'chattam-storage-mount'
        }
      ]
      containers: [
        {
          name: 'chattamai-service'
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          volumeMounts: [
            {
              volumeName: 'data-volume'
              mountPath: '/app/data'
            }
          ]
          env: [
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'DATABASE_URL'
              value: 'sqlite:////app/data/chattamai.db'
            }
            {
              name: 'KBR_DATA_DIR'
              value: '/app/data/kbr'
            }
            {
              name: 'INDEX_DIR'
              value: '/app/data/index'
            }
            {
              name: 'SECRET_KEY'
              secretRef: 'secret-key'
            }
            {
              name: 'OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'GEMINI_API_KEY'
              secretRef: 'gemini-api-key'
            }
            {
              name: 'NVIDIA_API_KEY'
              secretRef: 'nvidia-api-key'
            }
            {
              name: 'ANTHROPIC_API_KEY'
              secretRef: 'anthropic-api-key'
            }
            {
              name: 'ADMIN_KEY'
              secretRef: 'admin-key'
            }
            {
              name: 'GOOGLE_CLIENT_ID'
              secretRef: 'google-client-id'
            }
            {
              name: 'GOOGLE_CLIENT_SECRET'
              secretRef: 'google-client-secret'
            }
            {
              name: 'GOOGLE_REDIRECT_URI'
              value: empty(googleRedirectUri) ? 'https://${containerAppName}.${containerAppEnv.properties.defaultDomain}/login' : googleRedirectUri
            }
            {
              name: 'CORS_ORIGINS'
              value: corsOrigins
            }
            {
              name: 'AUTH_REQUIRED'
              value: authRequired ? 'true' : 'false'
            }
            {
              name: 'TOTP_REQUIRED'
              value: totpRequired ? 'true' : 'false'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 20
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling-rule'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// --- Outputs ---
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output storageAccountName string = storageAccount.name
