# Safety net FIRST: monthly cost budget with alerts at 10% / 25% / 50%
# of the limit ($20 / $50 / $100 for the default $200). Run before deploying.
#
# Usage: .\scripts\set_budgets.ps1 you@example.com [-LimitUsd 200]
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Email,
    [Parameter(Position = 1)][int]$LimitUsd = 200
)
$ErrorActionPreference = "Stop"

$accountId = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) {
    throw "aws sts get-caller-identity a esuat - ruleaza 'aws configure' intai."
}

$budget = @{
    BudgetName  = "customs-analyzer-credits"
    BudgetType  = "COST"
    TimeUnit    = "MONTHLY"
    BudgetLimit = @{ Amount = "$LimitUsd"; Unit = "USD" }
} | ConvertTo-Json -Compress

$notifications = @(
    foreach ($threshold in 10, 25, 50) {
        @{
            Notification = @{
                NotificationType   = "ACTUAL"
                ComparisonOperator = "GREATER_THAN"
                Threshold          = $threshold
                ThresholdType      = "PERCENTAGE"
            }
            Subscribers  = @(@{ SubscriptionType = "EMAIL"; Address = $Email })
        }
    }
) | ConvertTo-Json -Depth 5 -Compress

# file:// avoids PowerShell quote-mangling of inline JSON arguments.
$budgetFile = Join-Path $env:TEMP "budget.json"
$notifFile = Join-Path $env:TEMP "budget-notifications.json"
[System.IO.File]::WriteAllText($budgetFile, $budget)
[System.IO.File]::WriteAllText($notifFile, $notifications)

aws budgets create-budget `
    --account-id $accountId `
    --budget "file://$budgetFile" `
    --notifications-with-subscribers "file://$notifFile"
if ($LASTEXITCODE -ne 0) { throw "aws budgets create-budget a esuat." }

Remove-Item $budgetFile, $notifFile -ErrorAction SilentlyContinue
Write-Host ("Budget 'customs-analyzer-credits' set: alerts to {0} at `${1}, `${2}, `${3} of `${4}." -f `
        $Email, [int]($LimitUsd / 10), [int]($LimitUsd / 4), [int]($LimitUsd / 2), $LimitUsd)
