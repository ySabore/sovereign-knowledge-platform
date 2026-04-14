import enterpriseUiHtml from "../../../../docs/sources/RefinedDocuments/enterprise-ui-screens.html?raw";

/**
 * Exact enterprise UI replica.
 * Uses the original HTML/CSS/JS verbatim via iframe srcDoc.
 */
export function EnterpriseUiReplicaPage() {
  return (
    <div style={{ height: "100vh", width: "100vw", background: "#030508" }}>
      <iframe
        title="Enterprise UI Screens Replica"
        srcDoc={enterpriseUiHtml}
        style={{ border: "none", width: "100%", height: "100%" }}
      />
    </div>
  );
}
