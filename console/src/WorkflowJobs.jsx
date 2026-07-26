import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const WORKFLOWS = {
  synthetic_phi: {
    label: "Synthetic PHI",
    help: "Generates a deterministic DICOM source, PHI-injected DICOM, and answer key.",
    fields: [],
  },
  deidentify: {
    label: "De-identify",
    help: "Removes synthetic PHI from a DICOM using its answer key.",
    fields: [
      ["input_path", "Input DICOM path", "Example: /app/artifacts/runtime/job-artifacts/<job-id>/1-001.injected.dcm"],
      ["answer_key_path", "Answer key path", "Example: /app/artifacts/runtime/job-artifacts/<job-id>/answer-key.json"],
      ["output_path", "Output path (optional, container path)", "Leave blank; Windows host paths are not visible inside Docker"],
    ],
  },
  segment: {
    label: "Segmentation",
    help: "Runs the MONAI checkpoint on one image/mask pair.",
    fields: [
      ["input_path", "Input image path", "Worker-visible path, for example /app/research-artifacts/..."],
      ["mask_path", "Mask path", "Worker-visible ground-truth mask path"],
      ["checkpoint", "Checkpoint path", "Worker-visible .pt/.pth checkpoint path"],
      ["image_size", "Image size", "128"],
    ],
  },
  evaluate: {
    label: "Evaluation",
    help: "Evaluates a checkpoint on the test split of a manifest.",
    fields: [
      ["manifest", "Manifest path", "Worker-visible manifest JSON path"],
      ["checkpoint", "Checkpoint path", "Worker-visible .pt/.pth checkpoint path"],
      ["image_size", "Image size", "128"],
      ["batch_size", "Batch size", "32"],
      ["limit_test", "Test limit (optional)", "Leave blank for the full test split"],
    ],
  },
};

const REQUIRED_FIELDS = new Set(["input_path", "answer_key_path", "mask_path", "checkpoint", "manifest", "image_size", "batch_size"]);

export default function WorkflowJobs({ jobs, cases, onSubmit }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("synthetic_phi");
  const [caseId, setCaseId] = useState("");
  const [config, setConfig] = useState({});

  useEffect(() => { if (!caseId && cases[0]) setCaseId(cases[0].case_id); }, [cases, caseId]);
  const workflow = WORKFLOWS[type];
  const completedSynthetic = useMemo(() => jobs.filter((job) => job.job_type === "synthetic_phi" && job.status === "completed" && job.artifacts?.injected && job.artifacts?.answer_key), [jobs]);
  const filtered = jobs.filter((job) => `${job.job_type} ${job.case_id} ${job.status} ${job.error || ""}`.toLowerCase().includes(query.toLowerCase()));
  const missing = workflow.fields.filter(([name]) => REQUIRED_FIELDS.has(name) && !config[name]?.trim());

  function selectWorkflow(value) {
    setType(value);
    setConfig({});
  }

  function useSyntheticJob(jobId) {
    const job = completedSynthetic.find((item) => item.job_id === jobId);
    if (!job) return;
    setConfig((current) => ({ ...current, input_path: job.artifacts.injected, answer_key_path: job.artifacts.answer_key }));
  }

  function submit(event) {
    event.preventDefault();
    onSubmit({ job_type: type, case_id: caseId, config: { execute: "true", ...Object.fromEntries(Object.entries(config).filter(([, value]) => value?.trim())) } });
  }

  return <div className="view-stack">
    <section className="page-intro"><div><div className="eyebrow">EXECUTION QUEUE</div><h2>Jobs</h2><p>Choose a registered case, configure a typed workflow, and monitor its artifacts.</p></div></section>
    <div className="split-grid">
      <form className="panel form-panel" onSubmit={submit}>
        <div className="panel-title"><h3>Queue a job</h3></div>
        <label className="field"><span>Job type</span><select value={type} onChange={(event) => selectWorkflow(event.target.value)}>{Object.entries(WORKFLOWS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select></label>
        <div className="form-hint workflow-help">{workflow.help}</div>
        <label className="field"><span>Registered case</span><select value={caseId} onChange={(event) => setCaseId(event.target.value)} required><option value="">Select a case...</option>{cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id}</option>)}</select></label>
        {type === "deidentify" && completedSynthetic.length > 0 && <label className="field"><span>Load inputs from completed Synthetic PHI job</span><select defaultValue="" onChange={(event) => useSyntheticJob(event.target.value)}><option value="">Select a generated job...</option>{completedSynthetic.map((job) => <option key={job.job_id} value={job.job_id}>{job.case_id} — {job.job_id.slice(0, 8)}</option>)}</select></label>}
        {workflow.fields.map(([name, label, placeholder]) => <label className="field" key={name}><span>{label}</span><input value={config[name] || ""} onChange={(event) => setConfig((current) => ({ ...current, [name]: event.target.value }))} placeholder={placeholder} required={REQUIRED_FIELDS.has(name)} /></label>)}
        <button className="primary full" disabled={!cases.length || !caseId || missing.length > 0}>Queue {workflow.label} <span>-&gt;</span></button>
        {!cases.length && <div className="form-hint">Register a case before queuing a job.</div>}
        {missing.length > 0 && <div className="form-hint">Complete the required workflow fields before queuing.</div>}
      </form>
      <section className="panel"><div className="panel-title"><h3>Job history</h3><span className="count-label">{filtered.length} shown</span></div><input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search type, case, status, or error..." /><div className="table-wrap"><table><thead><tr><th>Type</th><th>Case</th><th>Status</th><th>Created</th></tr></thead><tbody>{filtered.map((job) => <tr key={job.job_id}><td><strong>{job.job_type.replaceAll("_", " ")}</strong><small>{job.error || job.message || `${job.job_id.slice(0, 8)}...`}</small>{job.artifacts && <div className="artifact-links">{Object.keys(job.artifacts).map((name) => <a key={name} href={`${API_BASE}/v1/jobs/${job.job_id}/artifacts/${encodeURIComponent(name)}`} target="_blank" rel="noreferrer">{name}</a>)}</div>}</td><td>{job.case_id}</td><td><span className={`pill ${job.status}`}>{job.status}</span></td><td>{new Date(job.created_at).toLocaleString()}</td></tr>)}</tbody></table>{!filtered.length && <div className="empty">No matching jobs.</div>}</div></section>
    </div>
  </div>;
}
