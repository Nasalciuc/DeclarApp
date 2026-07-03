# End-to-end smoke test: upload a declaration, wait for the pipeline,
# print the validation report.
#
# Usage: .\scripts\smoke_test.ps1 path\to\declaration.pdf [-Stack customs-analyzer]
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Pdf,
    [Parameter(Position = 1)][string]$Stack = "customs-analyzer"
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path $Pdf)) { throw "Fisierul nu exista: $Pdf" }

function Get-StackOutput([string]$Key) {
    aws cloudformation describe-stacks --stack-name $Stack `
        --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text
}

$bucket = Get-StackOutput BucketName
$table = Get-StackOutput DeclarationsTableName
if (-not $bucket -or -not $table) { throw "Nu gasesc outputs pentru stack-ul '$Stack'." }

$id = "smoke-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$ext = [System.IO.Path]::GetExtension($Pdf).TrimStart(".")

Write-Host "-> uploading as input/$id.$ext to s3://$bucket"
aws s3 cp $Pdf "s3://$bucket/input/$id.$ext" --only-show-errors
if ($LASTEXITCODE -ne 0) { throw "Upload esuat." }

# file:// avoids PowerShell quote-mangling of the inline JSON key.
$keyFile = Join-Path $env:TEMP "smoke-key.json"
[System.IO.File]::WriteAllText($keyFile, "{`"declaration_id`":{`"S`":`"$id`"}}")

Write-Host -NoNewline "-> waiting for pipeline"
$status = "?"
foreach ($i in 1..60) {
    $status = aws dynamodb get-item --table-name $table `
        --key "file://$keyFile" --query "Item.status.S" --output text 2>$null
    if (-not $status -or $status -eq "None") { $status = "?" }
    if ($status -in "VALIDATED", "FLAGGED", "ERROR") { break }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 3
}
Remove-Item $keyFile -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "-> status: $status"

if ($status -in "VALIDATED", "FLAGGED") {
    Write-Host "-> report:"
    $raw = aws s3 cp "s3://$bucket/reports/$id.json" - --only-show-errors
    ($raw -join "`n") | ConvertFrom-Json | ConvertTo-Json -Depth 20
}
