import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";

type Org = {
  id: string;
  name: string;
};

type Workspace = { id: string; organization_id: string; name: string; description: string | null };
type Document = {
  id: string;
  filename: string;
  status: string;
  ingestion_job_id?: string | null;
  ingestion_job_status?: string | null;
  ingestion_job_error?: string | null;
  page_count: number | null;
  chunk_count?: number;
  created_at?: string;
};

const DOCUMENT_UPLOAD_ACCEPT =
  ".pdf,.docx,.txt,.md,.markdown,.html,.htm,.pptx,.xlsx,.xls,.csv,.rtf,.eml,.msg,.epub,.mobi,.png,.jpg,.jpeg,.webp,.tif,.tiff";

function Badge({ label, color, bg, border }: { label: string; color: string; bg: string; border: string }) {
  const C = useOrgShellTokens();
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "2px 8px", borderRadius: 100,
      fontSize: 10, fontWeight: 600, color, background: bg, border: `1px solid ${border}`,
      fontFamily: C.sans,
    }}>
      {label}
    </span>
  );
}

export function DocumentsPanel({ orgs, scopeOrganizationId }: { orgs: Org[]; scopeOrganizationId?: string | null }) {
  const C = useOrgShellTokens();
  const [allWorkspaces, setAllWorkspaces] = useState<(Workspace & { orgName: string })[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<string>("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [uploadOk, setUploadOk] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!orgs.length) return;
    const orgList = scopeOrganizationId
      ? orgs.filter((o) => o.id === scopeOrganizationId)
      : orgs;
    if (!orgList.length) {
      setAllWorkspaces([]);
      setSelectedWsId("");
      return;
    }
    let cancelled = false;
    void (async () => {
      const collected: (Workspace & { orgName: string })[] = [];
      for (const o of orgList) {
        try {
          const { data } = await api.get<Workspace[]>(`/workspaces/org/${o.id}`);
          data.forEach((ws) => collected.push({ ...ws, orgName: o.name }));
        } catch {
          // ignore
        }
      }
      if (cancelled) return;
      setAllWorkspaces(collected);
      setSelectedWsId((prev) => {
        if (collected.some((w) => w.id === prev)) return prev;
        return collected[0]?.id ?? "";
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [orgs, scopeOrganizationId]);

  useEffect(() => {
    if (!selectedWsId) return;
    let cancelled = false;
    setLoadingDocs(true);
    setDocuments([]);
    api
      .get<Document[]>(`/documents/workspaces/${selectedWsId}`)
      .then(({ data }) => {
        if (!cancelled) setDocuments(data);
      })
      .catch(() => {
        if (!cancelled) setDocuments([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingDocs(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedWsId]);

  const needsIngestionPoll = useMemo(
    () =>
      documents.some(
        (d) =>
          d.status === "processing" ||
          d.status === "uploaded" ||
          d.ingestion_job_status === "queued" ||
          d.ingestion_job_status === "processing",
      ),
    [documents],
  );

  useEffect(() => {
    if (!selectedWsId || !needsIngestionPoll) return;
    const t = window.setInterval(() => {
      void api
        .get<Document[]>(`/documents/workspaces/${selectedWsId}`)
        .then(({ data }) => setDocuments(data))
        .catch(() => {
          // keep last snapshot
        });
    }, 4000);
    return () => window.clearInterval(t);
  }, [selectedWsId, needsIngestionPoll]);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedWsId) return;
    setUploading(true);
    setUploadErr(null);
    setUploadOk(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await api.post<{ filename: string; chunk_count: number }>(
        `/documents/workspaces/${selectedWsId}/upload`, body,
      );
      setUploadOk(`"${data.filename}" indexed — ${data.chunk_count} chunks created.`);
      const { data: docs } = await api.get<Document[]>(`/documents/workspaces/${selectedWsId}`);
      setDocuments(docs);
    } catch (ex) {
      setUploadErr(apiErrorMessage(ex));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (scopeOrganizationId && !orgs.some((o) => o.id === scopeOrganizationId)) {
    return (
      <div style={{ padding: "18px 22px" }}>
        <div style={{ fontSize: 13, color: C.t2 }}>Select an organization from the context bar to manage documents for that org.</div>
      </div>
    );
  }

  return (
    <div style={{ padding: "18px 22px" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>
          Document Library
        </div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          Upload documents (PDF, Word, PowerPoint, Excel, CSV, RTF, text, Markdown, HTML) to index for grounded retrieval.
        </div>
      </div>

      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: C.t3, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Workspace
        </span>
        <select
          value={selectedWsId}
          onChange={(e) => setSelectedWsId(e.target.value)}
          style={{
            background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 7,
            padding: "6px 10px", fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
          }}
        >
          {allWorkspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>{ws.orgName} / {ws.name}</option>
          ))}
        </select>
      </div>

      <div style={{
        background: C.bgCard, border: `2px dashed ${C.bd2}`, borderRadius: 12,
        padding: "28px 24px", textAlign: "center", marginBottom: 20,
        cursor: "pointer", transition: "border-color .2s",
      }}
        onClick={() => fileRef.current?.click()}
      >
        <div style={{ fontSize: 30, marginBottom: 8 }}>📄</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 4 }}>
          {uploading ? "Uploading & indexing…" : "Click to upload a document"}
        </div>
        <div style={{ fontSize: 11, color: C.t3 }}>
          Files are parsed, chunked, embedded and indexed automatically
        </div>
        <input
          ref={fileRef}
          type="file"
          accept={DOCUMENT_UPLOAD_ACCEPT}
          style={{ display: "none" }}
          onChange={handleUpload}
          disabled={uploading || !selectedWsId}
        />
        {uploading && (
          <div style={{ marginTop: 12 }}>
            <div style={{
              height: 3, background: C.bgE, borderRadius: 100, overflow: "hidden", maxWidth: 280, margin: "0 auto",
            }}>
              <div style={{
                height: "100%", background: C.accent, borderRadius: 100,
                width: "60%", animation: "progress 1.5s ease-in-out infinite",
              }} />
            </div>
          </div>
        )}
      </div>

      {uploadErr && (
        <div style={{
          padding: "10px 14px", background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8,
          fontSize: 12, color: "#f87171", marginBottom: 14,
        }}>
          ✗ {uploadErr}
        </div>
      )}
      {uploadOk && (
        <div style={{
          padding: "10px 14px", background: "rgba(16,185,129,0.08)",
          border: "1px solid rgba(16,185,129,0.25)", borderRadius: 8,
          fontSize: 12, color: "#34d399", marginBottom: 14,
        }}>
          ✓ {uploadOk}
        </div>
      )}

      <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{
          padding: "11px 15px", borderBottom: `1px solid ${C.bd}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>
            Indexed documents {documents.length > 0 && `· ${documents.length}`}
          </span>
          {loadingDocs && <span style={{ fontSize: 10, color: C.t3 }}>Loading…</span>}
        </div>
        {documents.length === 0 && !loadingDocs ? (
          <div style={{ padding: "24px 16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
            No documents indexed yet. Upload a file above to get started.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Document", "Status", "Ingestion job", "Pages", "Chunks", "Indexed", ""].map((h) => (
                  <th key={h} style={{
                    textAlign: "left", fontSize: 9, fontWeight: 700,
                    letterSpacing: "0.1em", textTransform: "uppercase",
                    color: C.t3, padding: "7px 12px",
                    background: "rgba(255,255,255,0.02)", borderBottom: `1px solid ${C.bd}`,
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} style={{ borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
                  <td style={{ padding: "9px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{
                        width: 26, height: 26, borderRadius: 5, background: "rgba(37,99,235,0.12)",
                        border: `1px solid rgba(37,99,235,0.2)`, display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 12, flexShrink: 0,
                      }}>
                        📄
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 500, color: C.t1 }}>{doc.filename}</span>
                    </div>
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    {doc.status === "indexed"
                      ? <Badge label="● Indexed" color={C.green} bg="rgba(16,185,129,0.12)" border="rgba(16,185,129,0.25)" />
                      : doc.status === "processing" || doc.status === "uploaded"
                        ? <Badge label="⟳ Processing" color={C.gold} bg="rgba(245,158,11,0.12)" border="rgba(245,158,11,0.25)" />
                        : doc.status === "failed"
                          ? <Badge label="✕ Failed" color="#f87171" bg="rgba(239,68,68,0.12)" border="rgba(239,68,68,0.25)" />
                          : <Badge label={doc.status} color={C.t2} bg="rgba(148,163,184,0.08)" border={C.bd} />}
                  </td>
                  <td style={{ padding: "9px 12px", maxWidth: 140 }}>
                    {(() => {
                      const jst = doc.ingestion_job_status;
                      if (!doc.ingestion_job_id && !jst) {
                        return <span style={{ fontSize: 11, color: C.t3 }}>—</span>;
                      }
                      if (jst === "completed") {
                        return <Badge label="● Completed" color={C.green} bg="rgba(16,185,129,0.1)" border="rgba(16,185,129,0.22)" />;
                      }
                      if (jst === "processing") {
                        return <Badge label="⟳ Processing" color={C.gold} bg="rgba(245,158,11,0.12)" border="rgba(245,158,11,0.25)" />;
                      }
                      if (jst === "queued") {
                        return <Badge label="◌ Queued" color={C.accent} bg="rgba(37,99,235,0.1)" border="rgba(37,99,235,0.22)" />;
                      }
                      if (jst === "failed") {
                        return (
                          <span title={doc.ingestion_job_error || "Ingestion failed"}>
                            <Badge label="✕ Failed" color="#f87171" bg="rgba(239,68,68,0.12)" border="rgba(239,68,68,0.25)" />
                          </span>
                        );
                      }
                      return <Badge label={jst || "—"} color={C.t2} bg="rgba(148,163,184,0.08)" border={C.bd} />;
                    })()}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t2, fontFamily: C.mono }}>
                    {doc.page_count ?? "—"}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t2, fontFamily: C.mono }}>
                    {doc.chunk_count ?? "—"}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t3, fontFamily: C.mono }}>
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td style={{ padding: "9px 12px", textAlign: "right" }}>
                    <button
                      type="button"
                      disabled={removingId === doc.id}
                      onClick={async () => {
                        if (!window.confirm(`Remove “${doc.filename}” from the index?`)) return;
                        setRemovingId(doc.id);
                        try {
                          await api.delete(`/documents/${doc.id}`);
                          const { data: docs } = await api.get<Document[]>(`/documents/workspaces/${selectedWsId}`);
                          setDocuments(docs);
                        } catch (ex) {
                          setUploadErr(apiErrorMessage(ex));
                        } finally {
                          setRemovingId(null);
                        }
                      }}
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: C.red,
                        background: "none",
                        border: "none",
                        cursor: removingId === doc.id ? "wait" : "pointer",
                        fontFamily: C.sans,
                      }}
                    >
                      {removingId === doc.id ? "…" : "Remove"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
