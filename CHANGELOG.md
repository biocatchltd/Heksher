# Heksher Changelog
## unreleased major
## unreleased
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
