# Dot-source from a development launcher after changing to the repository root.
if (!(Test-Path .env.dev)) {
    throw 'Create .env.dev from .env.dev.example and set a local admin token.'
}
Get-Content .env.dev | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z_0-9]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim(), 'Process')
    }
}
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5433'
$env:POSTGRES_DB = 'tradingagents_dev'
# The database helpers give full DSNs priority over component variables.
$env:SUPABASE_DB_URL = ''
$env:TRADINGAGENTS_DB_URL = ''
$env:DATABASE_URL = ''
$env:TRADINGAGENTS_ENV_FILE = (Resolve-Path .env.dev).Path
$env:TRADINGAGENTS_CHROMA_PATH = Join-Path (Get-Location) '.cache/chroma-dev'
