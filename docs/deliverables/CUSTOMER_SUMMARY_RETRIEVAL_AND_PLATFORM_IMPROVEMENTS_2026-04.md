# Customer Summary: Retrieval and Platform Improvements (April 2026)

## What this means for your team

We improved answer quality, admin usability, and reliability across the platform so teams can get trustworthy results faster with less operational friction.

## Highlights

### Better answer quality and trust
- Improved retrieval behavior behind the scenes for more relevant responses.
- Kept strict grounding behavior: when there is not enough evidence, the assistant says so clearly instead of guessing.
- Improved source/citation presentation so users can verify answers more easily.

### Better Google Drive syncing control
- You can now choose multiple Drive folders to sync.
- Optional subfolder inclusion lets you control sync depth.
- Sync behavior is more reliable and better at handling larger scopes.

### Smoother team invitation experience
- Invite acceptance flow is more stable and no longer loops under failure conditions.
- You can now delete pending invites directly (helpful for mistyped emails).
- Invite resend behavior is clearer: newer invite links replace older ones.

### More admin self-service
- Organization admins can now manage Cloud LLM credentials in Settings (no platform-owner handoff required for this task).

### Clearer scope in the UI
- Navigation labels now use organization context:
  - `Organization / <Org>`
  - `Organization / <Org> / <Workspace>`
- This reduces confusion when moving between org-level and workspace-level tasks.

## Operational stability improvements

- Reduced unintended rate-limit interruptions in common admin flows.
- Improved error reporting in connector and invite scenarios for faster troubleshooting.

## Bottom line

This release improves day-to-day confidence:
- more accurate, grounded responses
- more predictable connector behavior
- faster admin operations
- clearer UI scope cues

If you want, we can provide a short tenant-specific validation checklist to confirm these behaviors in your own environment and data.

