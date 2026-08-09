# 5 - Announce

## Purpose

Post the release notes to the configured notification sink. Skip this step entirely if no notification sink was configured at setup.

## Input

- The version and changelog entry from steps 3 and 2.
- The notification-sink connection (if configured).
- The announcement channel/recipient recorded during setup.

## Output

Write `5-announce/results.md` in the run folder with: where the announcement was posted and the message content. If skipped, write a one-line note: "No notification sink configured. Step skipped."

## How to execute

1. **Check if a notification sink is configured.** If not, write the skip note and close the step.

2. **Format the announcement.** Adapt the changelog entry to the channel's format:
   - Slack/Discord: use markdown, keep it concise, link to the full release page.
   - Email: use a subject line like "Released v{version}: {summary}" and the full changelog as the body.
   - Other: use plain text.

3. **Post the announcement.** Send through the notification-sink connection. Confirm delivery.

4. **Update the run's done folder.** This is the last step, so create `done/info.md` with:
   - What was released (version, package, registry).
   - A one-line summary of the changes.
   - Anything learned that should change the steps or insights.

## Done when

The announcement is posted (or skipped), and the run's `done/info.md` is written.
