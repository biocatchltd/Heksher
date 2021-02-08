# Heksher Changelog
## unreleased major
## unreleased
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
