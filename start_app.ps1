Write-Host "========================================="
Write-Host " Starting Autonomous Trading System      "
Write-Host "========================================="

# 1. Start database and redis
Write-Host "[1/5] Starting Docker infrastructure (PostgreSQL & Redis)..."
docker compose up -d

# Give it a moment to initialize
Start-Sleep -Seconds 5

# 2. Initialize database
Write-Host "[2/5] Initializing Database..."
uv run python -c "import asyncio; from src.core.database import init_db; asyncio.run(init_db())"

# 3. Start API server
Write-Host "[3/5] Starting Backend API Server (port 8000)..."
Start-Process "cmd.exe" -ArgumentList "/k uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000" -WindowStyle Normal

# 4. Start MCP server
Write-Host "[4/5] Starting MCP Server..."
Start-Process "cmd.exe" -ArgumentList "/k uv run mcp dev src/mcp/server.py" -WindowStyle Normal

# 5. Start Frontend
Write-Host "[5/5] Starting Frontend Dashboard (port 5173)..."
Set-Location -Path "frontend"
Start-Process "cmd.exe" -ArgumentList "/k npm run dev" -WindowStyle Normal
Set-Location -Path ".."

Write-Host "========================================="
Write-Host " All services have been launched!        "
Write-Host " Backend API:  http://localhost:8000     "
Write-Host " Frontend GUI: http://localhost:5173     "
Write-Host "========================================="
