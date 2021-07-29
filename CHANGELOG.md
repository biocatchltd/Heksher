# Heksher Changelog
## 0.3.1
### Removed
* removed alembic upgrade from the image's pre-start
### Changed
* Moved sentry initialization to the end of the app startup
### Internal  
* Changed linters to mypy and isort
## 0.3.0
### Added
* Added the ability of type upgrade via the 'declare' route.
### Fixed
* rule patch response no longer has content
## 0.2.3
### Added
* `patch` method for rules. Existing rules values can be patched using the new method.
### Internal
* Added `deployment` section.
## 0.2.2
### Fixed
* patched a bug in FastAPI where a 204 response would still have content
## 0.2.1
### Added
* added validation of cache time to ensure the time is not in the future.
### Fixed
* Fixed validation of flag and enum types.
* Fixed case of query without any settings.
* all datetime usages are now set to utc to avoid time travel.
## 0.2.0
### Changed
* `/rules/search` and `/rules/query` have been changed to `POST`
* `GET settings/`'s `include_additional_data` parameter has been moved from the request body to the query.
### Added
* When querying rules, users can now specify a context feature with "*", to allow any condition with that feature.
* `rule_id` to `/api/v1/rules/query` response.
### Fixed
* fixes issue where redoc would fail with 500 error
* error with logstash environment parsing on linux
* added validation to `POST Rule`
* additional validation for cache_time with timezone
### Internal
* added a test make sure redoc builds
* BB tests can now be run from WSL
* when testing the image build, output is always printed for easier debugging
* Added shebang to `test.sh` so it'll work on macOS.
## 0.1.0
* initial release
