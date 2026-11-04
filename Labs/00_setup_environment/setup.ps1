param(
    [ValidatePattern('^[a-z0-9]{3,8}$')]
    [string]$StudentTag = '',
    [string]$ResourceGroupName = '',
    [string]$Location = ''
)

# Stop if an Azure CLI command fails instead of continuing with half-created resources.
function Invoke-Az {
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI command failed." }
}

# Use the subscription already selected by az login.
$SubscriptionId = (Invoke-Az account show --query id --output tsv).Trim()
$Suffix = $SubscriptionId.Split('-')[0]
$NameSuffix = if ($StudentTag) { "$StudentTag$Suffix" } else { $Suffix }
$ChatCapacity = 10
$EmbeddingCapacity = 10

$CourseDir = Split-Path -Parent $PSScriptRoot
# Reuse an instructor-assigned classroom group when the signed-in student has one.
if (-not $ResourceGroupName) {
    $AccountName = (Invoke-Az account show --query user.name --output tsv).Trim()
    $AllGroups = (Invoke-Az group list --output json) -join [Environment]::NewLine
    $AssignedGroups = @($AllGroups | ConvertFrom-Json | Where-Object {
        $_.tags.course -eq 'AdvancedRAG' -and $_.tags.student -eq $AccountName
    } | Select-Object -ExpandProperty name)
    if ($AssignedGroups.Count -eq 1 -and $AssignedGroups[0]) { $ResourceGroupName = $AssignedGroups[0].Trim() }
}
$ResourceGroup = if ($ResourceGroupName) { $ResourceGroupName } else { "rg-rag-$NameSuffix" }
if (-not $Location) {
    $Location = if ($ResourceGroupName) { (Invoke-Az group show --name $ResourceGroupName --query location --output tsv).Trim() } else { 'eastus' }
}
$StorageAccount = "ragstore$NameSuffix"
$Container = "knowledge-base"
$SearchService = "rag-search-$NameSuffix"
$IndexName = "rag-basic"
$FoundryAccount = "rag-foundry-$NameSuffix"
$FoundryProject = "rag-course"
$ChatDeployment = "gpt-4.1"
$EmbeddingDeployment = "text-embedding-3-large"

Write-Host "Subscription: $SubscriptionId"
Write-Host "Region: $Location | Resource group: $ResourceGroup"
Write-Host "Storage: $StorageAccount | Search: $SearchService | Foundry: $FoundryAccount"

# 1. Create a resource group in the selected subscription.
Invoke-Az group create --name $ResourceGroup --location $Location --output none

# 2. Create private Blob Storage and upload the course knowledge base.
Invoke-Az storage account create `
    --name $StorageAccount --resource-group $ResourceGroup `
    --location $Location --kind StorageV2 --sku Standard_LRS `
    --allow-blob-public-access false --output none
$env:AZURE_STORAGE_KEY = Invoke-Az storage account keys list `
    --account-name $StorageAccount --resource-group $ResourceGroup `
    --query '[0].value' --output tsv
Invoke-Az storage container create `
    --name $Container --account-name $StorageAccount --auth-mode key --output none
Invoke-Az storage blob upload-batch `
    --source (Join-Path $CourseDir 'Knowledge Base') --destination $Container `
    --account-name $StorageAccount --auth-mode key --overwrite true --output none
Remove-Item Env:AZURE_STORAGE_KEY

# 3. Create Azure AI Search and the empty vector index used by Lab 01.
Invoke-Az search service create `
    --name $SearchService --resource-group $ResourceGroup `
    --location $Location --sku basic --semantic-search free `
    --replica-count 1 --partition-count 1 --identity-type SystemAssigned `
    --auth-options aadOrApiKey --aad-auth-failure-mode http401WithBearerChallenge --output none
$SearchKey = Invoke-Az search admin-key show `
    --service-name $SearchService --resource-group $ResourceGroup `
    --query primaryKey --output tsv
$IndexFile = Join-Path $PSScriptRoot 'search_index.json'
$SearchUri = "https://${SearchService}.search.windows.net/indexes/${IndexName}?api-version=2024-07-01"
# Native PowerShell uses Windows certificate trust, including IT-installed proxy CAs.
# Certificate validation stays enabled; stop setup if the HTTPS request fails.
Invoke-RestMethod -Method Put -Uri $SearchUri `
    -Headers @{ 'api-key' = "$SearchKey".Trim() } `
    -InFile $IndexFile -ContentType 'application/json' -ErrorAction Stop | Out-Null

# 4. Create a Microsoft Foundry resource and project.
Invoke-Az cognitiveservices account create `
    --name $FoundryAccount --resource-group $ResourceGroup `
    --kind AIServices --sku S0 --location $Location `
    --custom-domain $FoundryAccount --assign-identity `
    --allow-project-management true --yes --output none
Invoke-Az cognitiveservices account project create `
    --name $FoundryAccount --resource-group $ResourceGroup `
    --project-name $FoundryProject --location $Location --assign-identity --output none

# Agentic RAG service-to-service authorization. Classroom delegation permits only these roles.
$SearchPrincipal = (Invoke-Az search service show --name $SearchService --resource-group $ResourceGroup --query identity.principalId --output tsv).Trim()
$ProjectPrincipal = (Invoke-Az cognitiveservices account project show --name $FoundryAccount --resource-group $ResourceGroup --project-name $FoundryProject --query identity.principalId --output tsv).Trim()
$FoundryScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$FoundryAccount"
$SearchScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Search/searchServices/$SearchService"
Invoke-Az role assignment create --assignee-object-id $SearchPrincipal --assignee-principal-type ServicePrincipal `
    --role "Cognitive Services User" --scope $FoundryScope --output none
Invoke-Az role assignment create --assignee-object-id $ProjectPrincipal --assignee-principal-type ServicePrincipal `
    --role "Search Index Data Reader" --scope $SearchScope --output none

# 5. Deploy a chat model and the embedding model used by the labs.
Invoke-Az cognitiveservices account deployment create `
    --name $FoundryAccount --resource-group $ResourceGroup `
    --deployment-name $ChatDeployment --model-name gpt-4.1 `
    --model-version 2025-04-14 --model-format OpenAI `
    --sku-name GlobalStandard --sku-capacity $ChatCapacity --output none
Invoke-Az cognitiveservices account deployment create `
    --name $FoundryAccount --resource-group $ResourceGroup `
    --deployment-name $EmbeddingDeployment --model-name text-embedding-3-large `
    --model-version 1 --model-format OpenAI `
    --sku-name Standard --sku-capacity $EmbeddingCapacity --output none

# Save the new connection values without showing keys on screen.
$FoundryKey = Invoke-Az cognitiveservices account keys list `
    --name $FoundryAccount --resource-group $ResourceGroup `
    --query key1 --output tsv
$OutputFile = Join-Path $PSScriptRoot '.env.generated'
$Lines = @(
    "AZURE_SUBSCRIPTION_ID=$SubscriptionId"
    "AZURE_RESOURCE_GROUP=$ResourceGroup"
    "AZURE_STORAGE_ACCOUNT=$StorageAccount"
    "AZURE_STORAGE_CONTAINER=$Container"
    "AZURE_FOUNDRY_ACCOUNT=$FoundryAccount"
    "AZURE_SEARCH_SERVICE=$SearchService"
    "AZURE_SEARCH_ENDPOINT=https://${SearchService}.search.windows.net"
    "AZURE_SEARCH_API_KEY=$SearchKey"
    "AZURE_OPENAI_ENDPOINT=https://${FoundryAccount}.openai.azure.com"
    "AZURE_OPENAI_API_KEY=$FoundryKey"
    "AZURE_OPENAI_DEPLOYMENT=$ChatDeployment"
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$EmbeddingDeployment"
    "AIPROJECT_ENDPOINT=https://${FoundryAccount}.services.ai.azure.com/api/projects/$FoundryProject"
    "FOUNDRY_PROJECT_RESOURCE_ID=/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$FoundryAccount/projects/$FoundryProject"
    "AZURE_OPENAI_API_VERSION=2025-04-01-preview"
)
[System.IO.File]::WriteAllText(
    $OutputFile,
    ($Lines -join [Environment]::NewLine) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Setup complete. Lab 01 index: $IndexName (empty until build_index.py runs)."
Write-Host "Connection values were saved in $OutputFile."
Write-Host "Before Lab 05, allow the new managed-identity role assignments to propagate."
