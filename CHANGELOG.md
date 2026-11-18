# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

- `TrendStore` no longer crashes when given a bare filename (`monitor.py` passes `"history.jsonl"`, whose `dirname` is empty)

## [1.3.0] - 2026-11-16

### Added

- Device groups (config `group:` field) with worst-case pill per group
- Detail drawer per card: latency sparkline + uptime since start
- Mute/unmute alerts per device (maintenance toggle, persisted)

## [1.2.0] - 2026-11-16

### Added

- Heartbeat history strip on every device card (last 50 checks, green/red bars)
- Global status banner: All systems operational / N of M devices down
- Search, filter (all/down/up/maintenance), and sort (name/status/latency) controls
- Light/dark theme toggle (persisted per browser)
- Maintenance and paused device states: checked but silent, blue/grey pills
- Durable JSONL trend recording wired into the monitor loop (history.jsonl)

## [1.1.0] - 2026-10-15

### Added

- Friendly device names: discovery resolves hostnames via reverse DNS and NetBIOS (Windows) when devices answer
- Rename devices from the dashboard (pencil button per card), persisted to config.yaml
- In-dashboard Help & FAQ panel
- README FAQ section
- 9 new tests (resolution + rename endpoints)

## [1.0.0] - 2026-08-29

### Added

- Initial release
