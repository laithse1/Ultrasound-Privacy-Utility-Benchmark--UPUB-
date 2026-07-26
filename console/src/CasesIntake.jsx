import React, { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const OHIF_URL = import.meta.env.VITE_OHIF_URL || "http://localhost:3000";

export default function CasesIntake({ cases, onSubmit, navigate, apiKey }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [mode, setMode] = useState("folder");
  const [query, setQuery] = useState("");
  const [split, setSplit] = useState("test");
  const [hasMask, setHasMask] = useState(true);
  const [dataset, setDataset] = useState("BrEaST");
  const [version, setVersion] = useState("local");
  const [patientGroup, setPatientGroup] = useState("");
  const [caseId, setCaseId] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [importStatus, setImportStatus] = useState("");
  const pickerId = "case-picker";

  function chooseFiles(event) {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
    const first = files[0];
    const relative = first?.webkitRelativePath || first?.name || "";
    const root = relative.includes("/") ? relative.split("/")[0] : relative.replace(/\.[^.]+$/, "");
    const safe = root.toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^-|-$/g, "") || "ultrasound-case";
    setCaseId((value) => value || safe);
    setPatientGroup((value) => value || safe);
    setSourceUri(`browser://${root || "selection"}`);
  }

  const totalBytes = selectedFiles.reduce((sum, file) => sum + file.size, 0);
  const extensions = [...new Set(selectedFiles.map((file) => file.name.split(".").pop()?.toLowerCase()).filter(Boolean))].slice(0, 6);
  const dicomFiles = selectedFiles.filter((file) => file.type === "application/dicom" || /\.(dcm|dicom)$/i.test(file.name));
  const viewerReady = dicomFiles.length > 0;
  const filtered = cases.filter((item) => `${item.case_id} ${item.dataset_name} ${item.patient_group}`.toLowerCase().includes(query.toLowerCase()));

  async function importToViewer() {
    if (!dicomFiles.length) return;
    setImportStatus("Importing DICOM files...");
    try {
      for (const file of dicomFiles) {
        const uploadHeaders = { "Content-Type": "application/dicom" };
        if (apiKey) uploadHeaders["X-API-Key"] = apiKey;
        const response = await fetch(`${API_BASE}/v1/dicom/import`, { method: "POST", headers: uploadHeaders, body: file });
        const errorBody = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorBody.detail || `HTTP ${response.status}`);
      }
      setImportStatus(`${dicomFiles.length} DICOM file${dicomFiles.length === 1 ? "" : "s"} imported. Refresh OHIF to view the study.`);
    } catch (error) { setImportStatus(`Import failed: ${error.message}`); }
  }

  function submit(event) {
    event.preventDefault();
    onSubmit({ case_id: caseId, source_uri: sourceUri || "browser://manual", dataset_name: dataset, dataset_version: version, patient_group: patientGroup || caseId, split, has_segmentation_mask: hasMask, metadata: { selection_mode: mode, selected_file_count: String(selectedFiles.length), selected_bytes: String(totalBytes), file_extensions: extensions.join(","), dicom_file_count: String(dicomFiles.length), viewer_ready: String(viewerReady) } });
  }

  return <div className="view-stack"><section className="page-intro"><div><div className="eyebrow">MANIFEST REGISTRY</div><h2>Cases & provenance</h2><p>Choose data, review what the viewer can open, then register a clear manifest.</p></div><button className="ghost" onClick={() => document.getElementById(pickerId).click()}>Choose data</button></section>
    <div className="split-grid"><form className="panel form-panel" onSubmit={submit}><div className="panel-title"><h3>Register a case</h3><span className="step-label">1. Select data</span></div><input id={pickerId} className="visually-hidden" type="file" multiple={mode === "files"} webkitdirectory={mode === "folder" ? "" : undefined} onChange={chooseFiles} />
      <div className="picker-tabs"><button type="button" className={mode === "folder" ? "selected" : ""} onClick={() => setMode("folder")}>Folder</button><button type="button" className={mode === "files" ? "selected" : ""} onClick={() => setMode("files")}>Files</button></div><div className="dropzone" onClick={() => document.getElementById(pickerId).click()}><strong>{selectedFiles.length ? `${selectedFiles.length} item${selectedFiles.length === 1 ? "" : "s"} selected` : `Browse ${mode === "folder" ? "a folder" : "files"}`}</strong><span>Nothing is uploaded during selection.</span></div>
      {selectedFiles.length > 0 && <><div className="selection-summary"><span>{(totalBytes / 1024 / 1024).toFixed(2)} MB</span><span>{extensions.join(", ") || "mixed files"}</span><span>{selectedFiles[0].webkitRelativePath || selectedFiles[0].name}</span><span className={viewerReady ? "ready-tag" : "warning-tag"}>{viewerReady ? `${dicomFiles.length} DICOM` : "Not an OHIF study"}</span></div><div className={viewerReady ? "viewer-note ready" : "viewer-note warning"}>{viewerReady ? "DICOM detected. Register the manifest, then import the selected files into Orthanc for OHIF viewing." : "PNG/JPEG files can be registered for research, but OHIF only displays DICOM studies and will not list these files."}</div>{viewerReady && <div className="viewer-actions"><button type="button" className="ghost" onClick={importToViewer}>Import DICOM to OHIF</button><a className="viewer-link" href={OHIF_URL} target="_blank" rel="noreferrer">Open OHIF</a></div>}{importStatus && <div className="form-hint">{importStatus}</div>}</>}
      <div className="panel-title form-section-title"><h3>2. Describe the case</h3></div><div className="form-row"><Field label="Case ID" value={caseId} onChange={setCaseId} placeholder="breast-demo-001" required /><Field label="Patient group" value={patientGroup} onChange={setPatientGroup} placeholder="patient-001" required /></div><Field label="Source descriptor" value={sourceUri} onChange={setSourceUri} placeholder="browser://selected-folder" required /><div className="form-row"><Field label="Dataset" value={dataset} onChange={setDataset} placeholder="BrEaST" required /><Field label="Version" value={version} onChange={setVersion} placeholder="v1" required /></div><div className="form-row"><label className="field"><span>Split</span><select value={split} onChange={(e) => setSplit(e.target.value)}><option>train</option><option>validation</option><option>test</option></select></label><label className="check compact"><input type="checkbox" checked={hasMask} onChange={(e) => setHasMask(e.target.checked)} /> Mask available</label></div><button className="primary full" disabled={!caseId || !sourceUri}>Register case <span>-&gt;</span></button>
    </form><section className="panel"><div className="panel-title"><h3>Registered cases</h3><span className="count-label">{filtered.length} shown</span></div><input className="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search cases, datasets, patients..." /><div className="table-wrap"><table><thead><tr><th>Case</th><th>Dataset</th><th>Split</th><th>Mask</th><th>Viewer</th><th></th></tr></thead><tbody>{filtered.map((item) => <tr key={item.case_id}><td><strong>{item.case_id}</strong><small>{item.patient_group}</small></td><td>{item.dataset_name}</td><td><span className="pill neutral">{item.split}</span></td><td>{item.has_segmentation_mask ? "yes" : "no"}</td><td><span className={`viewer-status ${item.metadata?.viewer_ready === "true" ? "ready" : "manifest"}`}>{item.metadata?.viewer_ready === "true" ? "DICOM" : "Manifest"}</span></td><td><button className="row-action" onClick={() => navigate("jobs")}>Queue</button></td></tr>)}</tbody></table>{!filtered.length && <div className="empty">No matching cases. Choose data or register a manual manifest.</div>}</div></section></div></div>;
}

function Field({ label, value, onChange, placeholder, required }) { return <label className="field"><span>{label}</span><input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} required={required} /></label>; }
