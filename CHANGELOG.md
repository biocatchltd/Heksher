# Heksher Changelog
## Next  (REQ alembic upgrade)
### Removed
* old api endpoint POST /api/v1/rules/query has been removed and replaced with GET /api/v1/rules/query
### Changed
* the rename api endpoint has been changed to PUT /api/v1/<name>/name
* the method of the endpoint /api/v1/rules/search has been changed to GET.
### Deprecated
* The api endpoint PATCH /api/v1/rules/<rule> to change a rule's value is now deprecated, new users
  should use PUT /api/v1/rules/<rule>/value
### Added
* declarations are now tolerant of subtypes (to account for previous type upgrade)
* documentation
* The api endpoint PUT /api/v1/rules/<rule>/value to change a rule's value
* The api endpoint GET /api/v1/rules/query to query rules (replaces the old query endpoint)
### Fixed
* A bug where patching a context feature's index using "to_before" would use the incorrect target.
### Internal
* a new script to test and correctly report coverage
* tools/mk_revision.py to easily create alembic revisions
## 0.4.1
### Removed
* removed the alembic extra, it's now a requirement 
## 0.4.0 (REQ alembic upgrade)
### Added
* Setting names can now include the `.` character
* Added schema information for setting types
* Added POST, PATCH and DELETE API's to context_features, allowing run-time modifications
* Added POST, PUT, GET and DELETE API's to edit metadata (setting and rule)
* A route to explicitly change the type of a setting
* Added the ability to set an alias while declaring a setting, 
that can then be used interchangeably with the original setting name
* Added a PUT API to setting, to rename a setting and adding the previous name as an alias
### Changed
* Heksher now uses sqlalchemy instead of databases
* inline_sql method removed, uses sqlalchemy validation instead
* metadata is now stored in seperate tables
* metadata keys are restricted to alphanumeric characters, underscore and dash
* better health checks - ping and cache periodically 
### Fixed
* removed yellowbox as a non-dev dependency
* getting a specific rule would only return the first condition
### Internal
* Changed coverage checking to coverage
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
