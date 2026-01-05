param(
    [Parameter(Mandatory=$true)]
    [string]$Query
)

Write-Host "🔍 Поиск: $Query" -ForegroundColor Cyan
Write-Host ""

docker exec docling-docling python /app/search.py $Query
