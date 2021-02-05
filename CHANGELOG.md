# Heksher Changelog
## unreleased major
## unreleased
### Added
* `rule_id` to `/api/v1/rules/query` response.
### Fixed
* fixes issue where redoc would fail with 500 error
* error with logstash environment parsing on linux
### Internal
* added a test make sure redoc builds
* BB tests can now be run from WSL
* when testing the image build, output is always printed for easier debugging
* Added shebang to `test.sh` so it'll work on macOS.
## 0.1.0
* initial release
