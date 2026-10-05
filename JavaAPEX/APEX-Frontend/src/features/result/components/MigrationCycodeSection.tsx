import type { CycodeReport } from "../services/resultService";

export function MigrationCycodeSection({ report }: { report?: CycodeReport | null }) {
  const status = report?.gate_status ?? "PENDING";
  const color = status === "PASSED" ? "#166534" : status === "FAILED" ? "#b91c1c" : "#475569";
  return (
    <section aria-label="Cycode security results" style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 16, padding: 24, marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>Cycode Security</h3>
        <strong style={{ color }}>{status === "FAILED" ? "Findings detected" : status === "UNAVAILABLE" ? "Scan unavailable" : status === "PENDING" ? "Awaiting scan" : "Passed"}</strong>
      </div>
      <p style={{ color: "#64748b" }}>Secrets and application security checks. Advisory results do not block publication.</p>
      {report?.error_message && <p role="status" style={{ color: "#b45309" }}>{report.error_message}</p>}
      {report?.scanned_at && <p style={{ color: "#64748b", fontSize: 12 }}>Scanned: {new Date(report.scanned_at).toLocaleString()}</p>}
      {report?.scans.map((scan) => (
        <details key={scan.scan_type} style={{ borderTop: "1px solid #e2e8f0", padding: "12px 0" }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            {scan.scan_type === "secret" ? "Secrets" : "Application security (SAST)"}: {scan.gate_status === "UNAVAILABLE" ? "Unavailable" : `${scan.finding_count ?? 0} findings`}
          </summary>
          {scan.error_message && <p>{scan.error_message}</p>}
          {scan.findings.length > 0 && <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", textAlign: "left", marginTop: 12 }}>
              <thead><tr><th>Severity</th><th>File</th><th>Rule</th></tr></thead>
              <tbody>{scan.findings.map((finding, index) => <tr key={index}>
                <td>{finding.severity}</td><td style={{ overflowWrap: "anywhere" }}>{finding.file || "Not provided"}</td><td>{finding.rule || "Not provided"}</td>
              </tr>)}</tbody>
            </table>
            {(scan.finding_count ?? 0) > scan.findings.length && <p>Showing the first {scan.findings.length} findings. Review the full scan in Cycode.</p>}
          </div>}
          {scan.gate_status === "PASSED" && <p>No findings reported by this scan.</p>}
        </details>
      ))}
    </section>
  );
}
