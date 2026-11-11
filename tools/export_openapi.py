"""Export the reviewed Phase 1 API contract without connecting to a database."""
from dataclasses import replace
import json
from pathlib import Path
from app.config import Settings
from app.main import create_app

settings=replace(Settings(),environment="development",dev_auth=True,dev_secret="contract-export-only-not-an-identity-secret")
app=create_app(settings)
target=Path(__file__).resolve().parents[1]/"packages/api-contracts/openapi.json"
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps(app.openapi(),indent=2),encoding="utf-8")
print(target)

