# EDY Shield 2.3.0 — Release Notes

## Endpoint Integrity & Defense

EDY Shield 2.3.0 completes the local-first endpoint integrity workflow and its optional,
safe handoff to EDY SIEM. FIM, baseline creation, comparative scans, hash analysis and
local alert response continue to work when the SIEM receiver is unavailable.

## Highlights

- Durable SQLite outbox and Event Contract v1 delivery to EDY SIEM.
- Endpoint Integrity Center with factual change, evidence, hash comparison, baseline and
  delivery timeline.
- SIEM handoff is shown only after confirmed delivery and transports only the `event_id`.
- Teal/green endpoint identity, visible focus and reduced-motion support.
- Real-process offline recovery proves retained events, zero lost events and zero logical
  duplicates.

## Release validation

- 687 tests passed, 2 skipped, 86.68% coverage.
- Ruff, MyPy, dashboard JavaScript syntax, wheel/sdist and diff checks passed.
- External Chrome QA covered desktop, notebook, tablet and mobile states with no new
  application console errors or document overflow.

## Known limitations

- Inbox downstream processing, retention/purge policy, production deployment and additional
  event sources remain future work.
- WAR_ROOM is an evolving context and threat-intelligence surface in the SIEM; this release
  does not claim a separate WAR_ROOM integration.
