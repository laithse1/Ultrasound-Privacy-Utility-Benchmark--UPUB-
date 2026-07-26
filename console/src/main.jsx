import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./viewer.css";
import "./workflow.css";
import "./case-status.css";
import CasesIntake from "./CasesIntake.jsx";
import WorkflowJobs from "./WorkflowJobs.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const OHIF_URL = import.meta.env.VITE_OHIF_URL || "http://localhost:3000";

function readableError(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => item?.msg || item?.message || JSON.stringify(item)).join("; ");
  if (value && typeof value === "object") return value.msg || value.message || JSON.stringify(value);
  return String(value || "Unknown error");
}

async function request(path, options = {}) {
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    ...requestOptions,
    headers: { "Content-Type": "application/json", ...optionHeaders },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(readableError(data.detail || `Request failed (${response.status})`));
  return data;
}

function App() {
  const [health, setHealth] = useState("checking");
  const [cases, setCases] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [activeView, setActiveView] = useState("overview");
  const [toast, setToast] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const headers = useMemo(() => (apiKey ? { "X-API-Key": apiKey } : {}), [apiKey]);

  async function refresh() {
    try {
      const result = await fetch(`${API_BASE}/healthz`);
      setHealth(result.ok ? "online" : "degraded");
      const [caseData, jobData] = await Promise.all([
        request("/v1/cases", { headers }), request("/v1/jobs", { headers }),
      ]);
      setCases(caseData); setJobs(jobData);
    } catch (error) { setHealth("offline"); setToast(error.message); }
  }

  useEffect(() => { refresh(); }, [apiKey]);
  useEffect(() => { const timer = setInterval(refresh, 10000); return () => clearInterval(timer); }, [apiKey]);
  useEffect(() => { if (!toast) return undefined; const timer = setTimeout(() => setToast(""), 5000); return () => clearTimeout(timer); }, [toast]);

  async function registerCase(payload) {
    try {
      await request("/v1/cases", { method: "POST", headers, body: JSON.stringify(payload) });
      setToast("Case registered successfully"); setActiveView("cases"); refresh();
    } catch (error) { setToast(error.message); }
  }

  async function submitJob(payload) {
    try {
      await request("/v1/jobs", { method: "POST", headers, body: JSON.stringify(payload) });
      setToast("Job queued"); setActiveView("jobs"); refresh();
    } catch (error) { setToast(error.message); }
  }

  const running = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;
  const completed = jobs.filter((job) => ["completed", "succeeded"].includes(job.status)).length;
  const navigate = (view) => setActiveView(view);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">U</div><div><strong>UPUB</strong><span>Research Console</span></div></div>
      <div className="nav-label">WORKSPACE</div>
      {[['overview','Overview','O'], ['cases','Cases','C'], ['jobs','Jobs','J'], ['research','Research evidence','R']].map(([id, label, icon]) =>
        <button className={`nav-item ${activeView === id ? 'active' : ''}`} onClick={() => navigate(id)} key={id}><span>{icon}</span>{label}</button>)}
      <div className="sidebar-foot"><span className={`status-dot ${health}`}></span><span>API {health}</span><button onClick={refresh} className="refresh">Refresh</button></div>
    </aside>
    <main className="main-content">
      <div className="viewer-launchbar"><div><strong>Image review</strong><span>Open the OHIF DICOMweb viewer for study and annotation workflows.</span></div><a className="viewer-link" href={OHIF_URL} target="_blank" rel="noreferrer">Launch OHIF <span>-&gt;</span></a></div>
      <header className="topbar"><div><div className="eyebrow">LOCAL-FIRST MEDICAL AI</div><h1>{activeView === 'overview' ? 'Research overview' : activeView[0].toUpperCase() + activeView.slice(1)}</h1></div><div className="top-actions"><button className="icon-button" onClick={() => setShowApiKey(!showApiKey)}>Key</button><span className="avatar">LA</span></div></header>
      {showApiKey && <div className="key-panel"><label>API key <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Optional UPUB_API_KEY" /></label><span>Stored in memory only</span></div>}
      {toast && <div className="toast" onClick={() => setToast("")}>{toast}<span>X</span></div>}
      {activeView === "overview" && <Overview cases={cases} jobs={jobs} running={running} completed={completed} navigate={navigate} />}
      {activeView === "cases" && <CasesIntake cases={cases} onSubmit={registerCase} navigate={navigate} apiKey={apiKey} />}
      {activeView === "jobs" && <WorkflowJobs jobs={jobs} cases={cases} onSubmit={submitJob} />}
      {activeView === "research" && <Research />}
    </main>
  </div>;
}

function Overview({ cases, jobs, running, completed, navigate }) { return <>
  <section className="hero-card"><div><div className="eyebrow coral">PRIVACY + UTILITY</div><h2>Make ultrasound AI<br /><em>defensible by design.</em></h2><p>Trace every image, privacy decision, model run, and metric through one auditable research workflow.</p><div className="hero-actions"><button className="primary" onClick={() => navigate("cases")}>Register a case <span>-&gt;</span></button><button className="ghost" onClick={() => navigate("research")}>View evidence</button></div></div><div className="hero-orbit"><div className="orbit-ring"></div><div className="orbit-core">US<br /><small>AI</small></div><span className="orbit-tag tag-one">PHI</span><span className="orbit-tag tag-two">DICOM</span><span className="orbit-tag tag-three">MONAI</span></div></section>
  <section className="stat-grid"><Stat label="Registered cases" value={cases.length} detail="Manifest-backed" tone="teal" /><Stat label="Active jobs" value={running} detail="Queued or running" tone="coral" /><Stat label="Completed jobs" value={completed} detail="Auditable outputs" tone="blue" /><Stat label="Research status" value="LOCAL" detail="No clinical data" tone="violet" /></section>
  <div className="content-grid"><section className="panel"><PanelTitle title="Recent activity" action="View jobs" onClick={() => navigate("jobs")} /><Activity jobs={jobs.slice(0, 5)} /></section><section className="panel methodology"><PanelTitle title="Methodology" /><div className="method-row"><span className="method-icon">01</span><div><strong>Protect</strong><p>Header residuals + pixel PHI detection</p></div></div><div className="method-row"><span className="method-icon">02</span><div><strong>Measure</strong><p>Segmentation utility and uncertainty</p></div></div><div className="method-row"><span className="method-icon">03</span><div><strong>Prove</strong><p>Provenance, artifacts, reproducible runs</p></div></div></section></div>
</>; }

function Stat({ label, value, detail, tone }) { return <div className={`stat-card ${tone}`}><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>; }
function PanelTitle({ title, action, onClick }) { return <div className="panel-title"><h3>{title}</h3>{action && <button onClick={onClick} className="text-button">{action} -&gt;</button>}</div>; }
function Activity({ jobs }) { if (!jobs.length) return <div className="empty">No jobs yet. Queue a segmentation or privacy job to begin.</div>; return <div className="activity-list">{jobs.map((job) => <div className="activity" key={job.job_id}><span className={`job-icon ${job.status}`}>JOB</span><div><strong>{job.job_type.replaceAll('_', ' ')}</strong><p>{job.case_id}</p></div><span className={`pill ${job.status}`}>{job.status}</span></div>)}</div>; }

function Cases({ cases, onSubmit, navigate }) {
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

  function chooseFiles(event) {
    const files = Array.from(event.target.files || []); setSelectedFiles(files);
    const first = files[0]; const relative = first?.webkitRelativePath || first?.name || "";
    const root = relative.includes("/") ? relative.split("/")[0] : relative.replace(/\.[^.]+$/, "");
    const safe = root.toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^-|-$/g, "") || "ultrasound-case";
    setCaseId((value) => value || safe); setPatientGroup((value) => value || safe); setSourceUri(`browser://${root || "selection"}`);
  }

  const totalBytes = selectedFiles.reduce((sum, file) => sum + file.size, 0);
  const filtered = cases.filter((item) => `${item.case_id} ${item.dataset_name} ${item.patient_group}`.toLowerCase().includes(query.toLowerCase()));
  const extensions = [...new Set(selectedFiles.map((file) => file.name.split(".").pop()?.toLowerCase()).filter(Boolean))].slice(0, 6);
  function submit(event) { event.preventDefault(); onSubmit({ case_id: caseId, source_uri: sourceUri || "browser://manual", dataset_name: dataset, dataset_version: version, patient_group: patientGroup || caseId, split, has_segmentation_mask: hasMask, metadata: { selection_mode: mode, selected_file_count: String(selectedFiles.length), selected_bytes: String(totalBytes), file_extensions: extensions.join(",") } }); }

  return <div className="view-stack"><section className="page-intro"><div><div className="eyebrow">MANIFEST REGISTRY</div><h2>Cases & provenance</h2><p>Choose a local file or folder, review its summary, then register a safe manifest descriptor.</p></div><button className="ghost" onClick={() => document.getElementById("case-picker").click()}>Choose data</button></section>
    <div className="split-grid"><form className="panel form-panel" onSubmit={submit}><PanelTitle title="Register a case" /><input id="case-picker" className="visually-hidden" type="file" multiple={mode === "files"} webkitdirectory={mode === "folder" ? "" : undefined} onChange={chooseFiles} />
      <div className="picker-tabs"><button type="button" className={mode === "folder" ? "selected" : ""} onClick={() => setMode("folder")}>Folder</button><button type="button" className={mode === "files" ? "selected" : ""} onClick={() => setMode("files")}>Files</button></div>
      <div className="dropzone" onClick={() => document.getElementById("case-picker").click()}><strong>{selectedFiles.length ? `${selectedFiles.length} item${selectedFiles.length === 1 ? "" : "s"} selected` : `Browse ${mode === "folder" ? "a folder" : "files"}`}</strong><span>Files stay in your browser. Only a safe summary is sent to the API.</span></div>
      {selectedFiles.length > 0 && <div className="selection-summary"><span>{(totalBytes / 1024 / 1024).toFixed(2)} MB</span><span>{extensions.join(", ") || "mixed files"}</span><span>{selectedFiles[0].webkitRelativePath || selectedFiles[0].name}</span></div>}
      <div className="form-row"><Field name="case_id" label="Case ID" value={caseId} onChange={setCaseId} placeholder="breast-demo-001" required /><Field name="patient_group" label="Patient group" value={patientGroup} onChange={setPatientGroup} placeholder="patient-001" required /></div>
      <Field name="source_uri" label="Source descriptor" value={sourceUri} onChange={setSourceUri} placeholder="browser://selected-folder" required /><div className="form-row"><Field name="dataset_name" label="Dataset" value={dataset} onChange={setDataset} placeholder="BrEaST" required /><Field name="dataset_version" label="Version" value={version} onChange={setVersion} placeholder="v1" required /></div>
      <div className="form-row"><label className="field"><span>Split</span><select value={split} onChange={(e) => setSplit(e.target.value)}><option>train</option><option>validation</option><option>test</option></select></label><label className="check compact"><input type="checkbox" checked={hasMask} onChange={(e) => setHasMask(e.target.checked)} /> Mask available</label></div><button className="primary full" disabled={!caseId || !sourceUri}>Register case <span>-&gt;</span></button>
    </form><section className="panel"><div className="panel-title"><h3>Registered cases</h3><span className="count-label">{filtered.length} shown</span></div><input className="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search cases, datasets, patients..." /><div className="table-wrap"><table><thead><tr><th>Case</th><th>Dataset</th><th>Split</th><th>Mask</th><th></th></tr></thead><tbody>{filtered.map((item) => <tr key={item.case_id}><td><strong>{item.case_id}</strong><small>{item.patient_group}</small></td><td>{item.dataset_name}</td><td><span className="pill neutral">{item.split}</span></td><td>{item.has_segmentation_mask ? "yes" : "no"}</td><td><button className="row-action" onClick={() => navigate("jobs")}>Queue</button></td></tr>)}</tbody></table>{!filtered.length && <div className="empty">No matching cases. Choose data or register a manual manifest.</div>}</div></section></div></div>;
}

function Jobs({ jobs, cases, onSubmit }) { const [query, setQuery] = useState(""); const [type, setType] = useState("synthetic_phi"); const [caseId, setCaseId] = useState(""); const filtered = jobs.filter((job) => `${job.job_type} ${job.case_id} ${job.status} ${job.error || ""}`.toLowerCase().includes(query.toLowerCase())); useEffect(() => { if (!caseId && cases[0]) setCaseId(cases[0].case_id); }, [cases, caseId]); function submit(e) { e.preventDefault(); onSubmit({ job_type: type, case_id: caseId, config: { execute: "true" } }); } const needsInputs = type !== "synthetic_phi"; return <div className="view-stack"><section className="page-intro"><div><div className="eyebrow">EXECUTION QUEUE</div><h2>Jobs</h2><p>Choose a registered case, run a typed workflow, and monitor the result.</p></div></section><div className="split-grid"><form className="panel form-panel" onSubmit={submit}><PanelTitle title="Queue a job" /><label className="field"><span>Job type</span><select value={type} onChange={(e) => setType(e.target.value)}><option value="synthetic_phi">Synthetic PHI (ready to run)</option><option value="deidentify">De-identify (prepared inputs required)</option><option value="segment">Segmentation (checkpoint required)</option><option value="evaluate">Evaluation (manifest + checkpoint required)</option></select></label><label className="field"><span>Registered case</span><select value={caseId} onChange={(e) => setCaseId(e.target.value)} required><option value="">Select a case...</option>{cases.map((item) => <option key={item.case_id}>{item.case_id}</option>)}</select></label><button className="primary full" disabled={!cases.length || !caseId || needsInputs}>Queue job <span>-&gt;</span></button>{needsInputs && <div className="form-hint">This workflow needs prepared file/checkpoint paths. Use the research scripts or provide a workflow configuration before enabling it.</div>}{!cases.length && <div className="form-hint">Register a case before queuing a job.</div>}</form><section className="panel"><div className="panel-title"><h3>Job history</h3><span className="count-label">{filtered.length} shown</span></div><input className="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search type, case, status, or error..." /><div className="table-wrap"><table><thead><tr><th>Type</th><th>Case</th><th>Status</th><th>Created</th></tr></thead><tbody>{filtered.map((job) => <tr key={job.job_id}><td><strong>{job.job_type.replaceAll("_", " ")}</strong><small>{job.error || job.message || job.job_id.slice(0, 8) + "..."}</small></td><td>{job.case_id}</td><td><span className={`pill ${job.status}`}>{job.status}</span></td><td>{new Date(job.created_at).toLocaleString()}</td></tr>)}</tbody></table>{!filtered.length && <div className="empty">No matching jobs.</div>}</div></section></div></div>; }

function Field({ name, label, placeholder, required, value, onChange }) { return <label className="field"><span>{label}</span><input name={name} value={value ?? ""} onChange={onChange ? (e) => onChange(e.target.value) : undefined} placeholder={placeholder} required={required} /></label>; }
function Research() { return <div className="view-stack"><section className="page-intro"><div><div className="eyebrow">EVIDENCE ROOM</div><h2>Research evidence</h2><p>The console is the operational surface for a benchmark designed to make privacy and utility measurable together.</p></div></section><div className="evidence-grid"><Evidence title="Privacy robustness" value="48 cases" detail="OCR + negative controls" color="coral" /><Evidence title="External datasets" value="4" detail="BUS-BRA | TN3K | BUSI | BrEaST" color="teal" /><Evidence title="Reproducibility" value="22 tests" detail="API, storage, worker, manifests" color="violet" /></div><section className="panel research-panel"><div className="research-line"><span className="big-number">01</span><div><h3>Protect the data boundary</h3><p>Metadata residual checks, synthetic burned-in PHI, local processing, and optional OCR provide a defensible privacy contract.</p></div></div><div className="research-line"><span className="big-number">02</span><div><h3>Measure clinical utility</h3><p>MONAI segmentation, cross-dataset transfer, per-case exports, and group-level bootstrap intervals quantify what masking costs.</p></div></div><div className="research-line"><span className="big-number">03</span><div><h3>Preserve the evidence</h3><p>Every experiment has a manifest, seed, checkpoint, metrics artifact, and provenance trail suitable for paper review.</p></div></div></section></div>; }
function Evidence({ title, value, detail, color }) { return <div className={`evidence-card ${color}`}><div className="eyebrow">{title}</div><strong>{value}</strong><p>{detail}</p></div>; }

createRoot(document.getElementById("root")).render(<App />);
