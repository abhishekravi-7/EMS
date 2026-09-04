# Fix 404 error for BRD metadata discovery

The frontend is receiving a 404 Not Found error when requesting `api/v1/discovery/{job_id}/brd`. This occurs when no BRD has been uploaded for the job. While technically correct in REST terms, this causes noisy error logs in the browser console. Additionally, a download endpoint for the BRD is missing.

## Proposed Changes

### [Backend] [discovery_controller.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/api/v1/endpoints/discovery_controller.py)

#### [MODIFY] [discovery_controller.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/api/v1/endpoints/discovery_controller.py)
- Change `get_brd_metadata` to return a `200 OK` with `null` or an empty object instead of `404 Not Found` when no BRD exists. This "clears" the error from the browser console.
- Add a new `download_brd` endpoint to allow the frontend to actually retrieve the uploaded PDF.
- Add a compatibility route for `/discovery/{job_id}/brd:1` (or any suffix) to handle cases where the frontend or a library appends a version/cache-buster.

## Verification Plan

### Automated Tests
- I will verify the route changes by checking the API definitions.
- (Optional) If possible, I will run a manual test using `curl` if a dev server is running.

### Manual Verification
- The user can verify that the 404 error no longer appears in the browser console when navigating to the Discovery page before uploading a BRD.
