# Deploy to Azure for Free

This guide will help you deploy your Expense Tracking API to Azure using the **Free Tier** (F1).

## Azure Free Tier Benefits

- **App Service (F1)**: Free web hosting
- **Azure Database for PostgreSQL**: Free tier available
- **Azure Cache for Redis**: Basic tier (paid, but optional)
- **60 minutes/day compute time** on F1 tier
- **1 GB storage**
- **Custom domain support**

## Prerequisites

1. Azure account (sign up at https://azure.microsoft.com/free/)
2. Azure CLI installed
3. Git installed

## Method 1: Deploy Using Azure CLI (Recommended)

### Step 1: Install Azure CLI

**Windows:**
Download from: https://aka.ms/installazurecliwindows

**Linux:**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**macOS:**
```bash
brew install azure-cli
```

### Step 2: Login to Azure

```bash
az login
```

This will open a browser for authentication.

### Step 3: Create Required Files

#### A. Create `startup.sh`

```bash
# FastAPI/startup.sh
#!/bin/bash

# Run database migrations
python -m alembic upgrade head

# Start the application
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Make it executable:
```bash
chmod +x startup.sh
```

#### B. Create `.deployment`

```ini
# FastAPI/.deployment
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

#### C. Update `requirements.txt`

Ensure it includes `gunicorn`:
```txt
gunicorn==21.2.0
```

### Step 4: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="expense-api-rg"
LOCATION="eastus"
APP_NAME="expense-tracker-api-$(openssl rand -hex 4)"
PLAN_NAME="expense-api-plan"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan (Free tier)
az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku F1 \
  --is-linux

# Create Web App
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --name $APP_NAME \
  --runtime "PYTHON:3.12" \
  --startup-file "startup.sh"
```

### Step 5: Configure Environment Variables

```bash
# Set environment variables
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    DATABASE_URL="sqlite+aiosqlite:///./expense_tracker.db" \
    REDIS_URL="redis://localhost:6379/0" \
    GROQ_API_KEY="your_groq_api_key_here" \
    GROQ_MODEL="llama-3.3-70b-versatile" \
    API_TITLE="Expense Tracking API" \
    API_VERSION="1.0.0" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"
```

### Step 6: Deploy Your Code

#### Option A: Deploy from Local Git

```bash
# Initialize git (if not already done)
cd FastAPI
git init
git add .
git commit -m "Initial commit"

# Configure deployment
az webapp deployment source config-local-git \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Get deployment URL
DEPLOY_URL=$(az webapp deployment source show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query url -o tsv)

# Add Azure remote
git remote add azure $DEPLOY_URL

# Deploy
git push azure main
```

#### Option B: Deploy from GitHub

```bash
# If your code is on GitHub
az webapp deployment source config \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --repo-url https://github.com/yourusername/your-repo \
  --branch main \
  --manual-integration
```

### Step 7: View Your API

```bash
# Get the URL
az webapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query defaultHostName -o tsv
```

Your API will be available at: `https://{APP_NAME}.azurewebsites.net`

API Documentation: `https://{APP_NAME}.azurewebsites.net/docs`

## Method 2: Deploy Using Azure Portal (GUI)

### Step 1: Create Web App

1. Go to https://portal.azure.com
2. Click "Create a resource"
3. Search for "Web App"
4. Click "Create"

### Step 2: Configure Basic Settings

- **Subscription**: Select your subscription
- **Resource Group**: Create new "expense-api-rg"
- **Name**: Choose unique name (e.g., "expense-tracker-api-xyz")
- **Publish**: Code
- **Runtime stack**: Python 3.12
- **Operating System**: Linux
- **Region**: Choose nearest region

### Step 3: Configure App Service Plan

- Click "Create new"
- **Name**: "expense-api-plan"
- **Pricing tier**: Click "Change size" → Dev/Test → F1 (Free)
- Click "Apply"

### Step 4: Review and Create

- Click "Review + create"
- Click "Create"
- Wait for deployment to complete

### Step 5: Configure Deployment

1. Go to your Web App resource
2. Click "Deployment Center" in left menu
3. Choose deployment source:
   - **Local Git**: For manual deployment
   - **GitHub**: For automatic deployment
4. Follow the wizard to complete setup

### Step 6: Set Environment Variables

1. In your Web App, click "Configuration"
2. Click "New application setting" for each:
   - `DATABASE_URL`: `sqlite+aiosqlite:///./expense_tracker.db`
   - `GROQ_API_KEY`: Your Groq API key
   - `GROQ_MODEL`: `llama-3.3-70b-versatile`
   - `REDIS_URL`: `redis://localhost:6379/0`
   - `SCM_DO_BUILD_DURING_DEPLOYMENT`: `true`
3. Click "Save"

### Step 7: Deploy Code

**Using Local Git:**

```bash
# Get Git URL from Deployment Center
git remote add azure <your-git-url>
git push azure main
```

**Using GitHub:**
- Connect your GitHub repository
- Select branch
- Azure will automatically deploy on push

## Adding PostgreSQL Database (Optional)

Azure offers a free PostgreSQL tier:

```bash
# Create PostgreSQL server
az postgres flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name expense-db-$(openssl rand -hex 4) \
  --location $LOCATION \
  --admin-user dbadmin \
  --admin-password "YourSecurePassword123!" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 15 \
  --storage-size 32

# Create database
az postgres flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name expense-db-xxxx \
  --database-name expense_tracker

# Get connection string
az postgres flexible-server show-connection-string \
  --server-name expense-db-xxxx \
  --database-name expense_tracker \
  --admin-user dbadmin \
  --admin-password "YourSecurePassword123!"
```

Update your app settings with the PostgreSQL connection string.

## Project Structure for Azure

Ensure your project has these files:

```
FastAPI/
├── app/                    # Your application code
├── alembic/               # Database migrations
├── main.py                # Entry point
├── requirements.txt       # Dependencies
├── startup.sh            # Startup script
├── .deployment           # Deployment config
└── .gitignore            # Git ignore file
```

## Important Files

### startup.sh
```bash
#!/bin/bash
python -m alembic upgrade head
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### .deployment
```ini
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

### .gitignore
```
__pycache__/
*.py[cod]
.env
.venv/
venv/
Lib/
Scripts/
Include/
*.db
*.sqlite
.pytest_cache/
.hypothesis/
.coverage
```

## Monitoring and Logs

### View Logs

```bash
# Stream logs
az webapp log tail \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Download logs
az webapp log download \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --log-file logs.zip
```

### In Azure Portal

1. Go to your Web App
2. Click "Log stream" in left menu
3. View real-time logs

## Custom Domain (Optional)

### Add Custom Domain

```bash
# Add custom domain
az webapp config hostname add \
  --webapp-name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --hostname yourdomain.com
```

### Enable HTTPS

Azure provides free SSL certificates:

1. Go to "Custom domains" in Azure Portal
2. Click "Add binding"
3. Select "App Service Managed Certificate"
4. Click "Add"

## Troubleshooting

### Application Not Starting

Check logs:
```bash
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP
```

Common issues:
- Missing `startup.sh`
- Wrong Python version
- Missing dependencies in `requirements.txt`

### Database Connection Error

- Verify `DATABASE_URL` in app settings
- Check if migrations ran successfully
- Review startup logs

### Out of Memory

F1 tier has limited memory (1GB). Optimize:
- Reduce worker processes
- Use connection pooling
- Enable caching

### Deployment Failed

```bash
# Check deployment logs
az webapp log deployment show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP
```

## Scaling (When You Outgrow Free Tier)

### Upgrade to Basic Tier

```bash
az appservice plan update \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku B1
```

### Enable Auto-scaling

Available on Standard tier and above.

## Cost Management

### Free Tier Limits

- **Compute**: 60 minutes/day
- **Storage**: 1 GB
- **Bandwidth**: 165 MB/day outbound

### Monitor Usage

```bash
# Check resource usage
az monitor metrics list \
  --resource $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --resource-type "Microsoft.Web/sites" \
  --metric "CpuTime"
```

### Set Budget Alerts

1. Go to "Cost Management + Billing"
2. Create budget
3. Set alert threshold

## Cleanup (Delete Resources)

When you're done testing:

```bash
# Delete entire resource group
az group delete --name $RESOURCE_GROUP --yes
```

## Alternative: Azure Container Instances (Free Credits)

If you prefer Docker:

```bash
# Build and push to Azure Container Registry
az acr create --resource-group $RESOURCE_GROUP --name expenseacr --sku Basic
az acr build --registry expenseacr --image expense-api:latest .

# Deploy to Container Instances
az container create \
  --resource-group $RESOURCE_GROUP \
  --name expense-api \
  --image expenseacr.azurecr.io/expense-api:latest \
  --dns-name-label expense-api-unique \
  --ports 8000
```

## Best Practices for Azure Deployment

1. **Use environment variables** for all configuration
2. **Enable Application Insights** for monitoring
3. **Set up CI/CD** with GitHub Actions
4. **Use managed identities** instead of passwords
5. **Enable HTTPS** always
6. **Regular backups** of database
7. **Monitor costs** regularly

## GitHub Actions CI/CD (Bonus)

Create `.github/workflows/azure-deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Deploy to Azure Web App
      uses: azure/webapps-deploy@v2
      with:
        app-name: ${{ secrets.AZURE_WEBAPP_NAME }}
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

## Support

- Azure Documentation: https://docs.microsoft.com/azure/app-service/
- Azure Free Account: https://azure.microsoft.com/free/
- Azure Support: https://azure.microsoft.com/support/

## Summary

Your API is now deployed to Azure for free! 🎉

- **URL**: `https://{your-app-name}.azurewebsites.net`
- **API Docs**: `https://{your-app-name}.azurewebsites.net/docs`
- **Cost**: $0/month (Free tier)
- **Uptime**: 60 minutes/day on F1 tier

For production use, consider upgrading to Basic (B1) tier for $13/month with 24/7 uptime.
