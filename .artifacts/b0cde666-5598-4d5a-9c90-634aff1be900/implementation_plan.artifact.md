# Migration Results Page Enhancement Plan

Modify the "Changes Made" section on the migration Results page to make the three summary cards clickable and display their respective details below.

## User Review Required

> [!IMPORTANT]
> The "Code Transformations" card will be selected by default, as requested.
> Each card will display dynamic counts and details based on actual migration data.

## Proposed Changes

### APEX-Frontend

#### [MODIFY] [ResultReportView.tsx](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Frontend/src/features/result/components/ResultReportView.tsx)
- Implement `SelectedChangeSection` state to track which card is currently active.
- Make "Files Modified", "Code Transformations", and "Dependencies Updated" cards clickable using accessible buttons.
- Update the "Files Modified" section:
    - Display dynamic count: `{actual modified-file count} files updated`.
    - Show detailed list: relative path, filename, type, status, added/removed lines, and applied rule/transformation name.
    - Implement empty state: `No files were modified during this migration.`
- Update the "Code Transformations" section:
    - Display dynamic count: `{actual transformation count} migration issues fixed`.
    - Use actual transformed files to generate tabs.
    - Display Before/After diffs with real content and highlighting.
    - Implement empty state: `No code transformations were recorded for this migration.`
- Update the "Dependencies Updated" section:
    - Display dynamic count: `{actual upgraded-dependency count} dependencies upgraded`.
    - Show detailed list: Name, groupId, artifactId, versions, scope, status, and reason.
    - Support statuses: `UPGRADED`, `UNCHANGED`, `ADDED`, `REMOVED`, `FAILED`, `MANUAL_REVIEW`.
    - Implement empty state: `No dependencies were recorded for this migration.` (though card remains clickable if 0).
- Ensure only one detail section is visible at a time.
- Add subtle selected state styling to the cards.
- Maintain mobile responsiveness and existing typography/icons.

## Verification Plan

### Automated Tests
- Run `npm run lint` in `APEX-Frontend` to ensure code quality.
- Run `npm run build` in `APEX-Frontend` to verify compilation.
- (Optional) Run `npm run test` if applicable.

### Manual Verification
- Verify that clicking each card correctly toggles the detail section below.
- Confirm "Code Transformations" is selected by default.
- Check that counts match the number of items in the detail lists.
- Verify that empty states are correctly displayed when no data is available.
- Test keyboard navigation (Enter/Space) and ARIA attributes (`aria-expanded`, `aria-controls`).
- Verify the UI on mobile breakpoints.
