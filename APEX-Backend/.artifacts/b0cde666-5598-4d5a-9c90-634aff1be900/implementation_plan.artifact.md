# Implementation Plan - API Endpoints Summary Card

Add an **API Endpoints** summary card to the Discovery page statistics row, consistent with existing cards.

## User Review Required

> [!IMPORTANT]
> The layout will now accommodate 5 summary cards. On smaller screens, the cards will wrap according to the existing responsive rules.

## Proposed Changes

### React Frontend

#### [MODIFY] [DiscoveryDashboard.css](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Frontend/src/features/discovery/components/DiscoveryDashboard.css)
- Update `.discovery-kpi-grid` to support 5 columns on desktop.
- Add an intermediate responsive step for 3 columns if needed, otherwise rely on the existing 2-column wrap at 1024px.

#### [MODIFY] [DiscoveryStepView.tsx](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Frontend/src/features/discovery/components/DiscoveryStepView.tsx)
- Calculate `apiEndpointCount` from `repoAnalysis?.api_endpoints`.
- Add a new "API Endpoints" card to the `discovery-kpi-grid` section.
- Implement the hover/pinned popover for the API Endpoints card, showing a summary of detected routes.
- Ensure unique React keys and consistent styling.

## Verification Plan

### Automated Tests
- Run `npm run lint` in `APEX-Frontend`.
- Run `npm run build` in `APEX-Frontend`.

### Manual Verification
- Verify all 5 cards appear in a single row on wide screens.
- Verify cards wrap correctly on tablets and mobile devices.
- Verify the API endpoint count is accurate (matches the number of rows in the endpoints table).
- Confirm the popover opens on hover and stays open when clicked (pinned).
- Confirm that refreshing the page maintains the count for the current job.
- Confirm that "Start New Migration" clears the count.
