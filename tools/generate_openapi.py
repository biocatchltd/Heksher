import json
import tomllib

from heksher.main import app

app = app()
with open("pyproject.toml", "rb") as proj_file:
    proj = tomllib.load(proj_file)
    app.version = proj['tool']['poetry']['version']
openapi = app.openapi()

with open("openapi.json", "x") as file:
    json.dump(openapi, file)