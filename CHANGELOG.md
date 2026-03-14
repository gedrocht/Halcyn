# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and the project is intended to use semantic versioning tags over time.

## [Unreleased]

### Added

- GitHub Actions CI and packaging workflows
- packaging script with build manifest output
- contribution and security guidance
- issue templates, pull request template, CODEOWNERS, and Dependabot configuration
- friendlier prerequisite guidance and Windows setup notes

### Changed

- Visual Studio detection now works with custom install locations through `vswhere`
- native command failures in PowerShell scripts now stop clearly instead of continuing silently
- renderer dependency visibility is configured correctly for downstream targets
- API server build compatibility was updated for the fetched `cpp-httplib` version
