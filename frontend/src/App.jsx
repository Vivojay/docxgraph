import React, { useEffect, useMemo, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams
} from "react-router-dom";
import {
  createCase,
  endorseCase,
  exportCases,
  getAdminLogs,
  getCase,
  getCases,
  getMe,
  getRoiMetrics,
  getSimilarCases,
  getSystemMetrics,
  login,
  logout,
  matchExperts,
  refresh,
  searchCases,
  updateCase
} from "./api";

const CASE_TYPES = {
  general: "general",
  ed_neuro: "ed_neuro",
  immuno_toxicity: "immuno_toxicity"
};

const CASE_TYPE_LABELS = {
  general: "General micro-case",
  ed_neuro: "ED neuro triage",
  immuno_toxicity: "Immunotherapy toxicity"
};

const KNOWLEDGE_QUERIES = [
  "acute stroke with facial droop and arm weakness",
  "immunotherapy colitis after pembrolizumab",
  "rural clinic dizziness and neuro referral",
  "atypical angina after procedure"
];

function useAuth() {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function init() {
      try {
        await refresh();
        const me = await getMe();
        if (!active) return;
        setUser(me.user);
        setProfile(me.profile || null);
      } catch (err) {
        if (!active) return;
        setUser(null);
        setProfile(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    init();
    return () => {
      active = false;
    };
  }, []);

  return { user, setUser, profile, setProfile, loading };
}

function ProtectedRoute({ user, loading, children }) {
  if (loading) return <div className="eg-screen-center"><div className="eg-loading-card">Loading workspace...</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function initials(name) {
  if (!name) return "EG";
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function glyph(label) {
  const map = {
    dashboard: "DB",
    profile: "PR",
    knowledge: "AI",
    newcase: "NC",
    match: "EX",
    admin: "AD",
    cases: "CL"
  };
  return map[label] || "EG";
}

function AppShell({ user, profile, onLogout, children }) {
  const location = useLocation();
  const navItems = [
    { key: "dashboard", label: "Dashboard", to: "/" },
    { key: "profile", label: "My Profile", to: "/profile" },
    { key: "knowledge", label: "AI Knowledge Graph", to: "/knowledge" },
    { key: "newcase", label: "New Case", to: "/cases/new" },
    { key: "match", label: "Expert Routing", to: "/match" }
  ];
  if (["org_admin", "auditor", "super_admin"].includes(user.role)) {
    navItems.push({ key: "admin", label: "Admin", to: "/admin" });
  }

  return (
    <div className="eg-shell">
      <aside className="eg-sidebar">
        <div className="eg-sidebar-brand">
          <div className="eg-logo-mark">EG</div>
          <div>
            <div className="eg-brand-title">ExperienceGraph</div>
            <div className="eg-brand-subtitle">Clinical Intelligence Network</div>
          </div>
        </div>

        <div className="eg-sidebar-group-label">Platform</div>
        <nav className="eg-sidebar-nav">
          {navItems.map((item) => {
            const active = location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(item.to));
            return (
              <Link key={item.to} to={item.to} className={`eg-nav-item ${active ? "active" : ""}`}>
                <span className="eg-nav-glyph">{glyph(item.key)}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="eg-sidebar-footer">
          <div className="eg-sidebar-user">
            <div className="eg-avatar">{initials(user.full_name || user.email)}</div>
            <div>
              <div className="eg-sidebar-user-name">{user.full_name || user.email}</div>
              <div className="eg-sidebar-user-meta">
                {(profile?.specialty || "Clinician")} · {profile?.verified ? "Verified" : "Pending"}
              </div>
            </div>
          </div>
          <button type="button" onClick={onLogout} className="eg-ghost-button eg-sidebar-logout">
            Sign Out
          </button>
        </div>
      </aside>

      <div className="eg-main">
        <header className="eg-topbar">
          <div className="eg-topbar-search">
            <span className="eg-topbar-search-label">Search</span>
            <input placeholder="Search cases, specialties, outcomes..." aria-label="Search workspace" />
          </div>
          <div className="eg-topbar-actions">
            <Link to="/knowledge" className="eg-pill-button">AI Graph</Link>
            <div className="eg-user-chip">
              <div className="eg-avatar small">{initials(user.full_name || user.email)}</div>
              <div>
                <div className="eg-user-chip-name">{user.full_name || user.email}</div>
                <div className="eg-user-chip-meta">{profile?.specialty || user.role}</div>
              </div>
            </div>
          </div>
        </header>
        <main className="eg-content">{children}</main>
      </div>
    </div>
  );
}

function LoginPage({ onLogin, onProfile }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      await login(email, password);
      const me = await getMe();
      onLogin(me.user);
      onProfile(me.profile || null);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="eg-auth-screen">
      <section className="eg-auth-brand-panel">
        <div className="eg-auth-grid" />
        <div className="eg-auth-panel-inner">
          <div className="eg-auth-brand">
            <div className="eg-logo-mark large">EG</div>
            <div>
              <div className="eg-brand-title inverse">ExperienceGraph</div>
              <div className="eg-brand-subtitle inverse">Enterprise clinician network</div>
            </div>
          </div>
          <div className="eg-auth-copy">
            <h1>Where verified clinicians build collective intelligence</h1>
            <p>
              Structured micro-cases, explainable expert routing, and an AI knowledge graph shaped by
              real-world outcomes and peer validation.
            </p>
          </div>
          <div className="eg-auth-stats">
            <div className="eg-auth-stat"><strong>2</strong><span>Demo orgs</span></div>
            <div className="eg-auth-stat"><strong>52</strong><span>Seeded cases</span></div>
            <div className="eg-auth-stat"><strong>3</strong><span>Knowledge modes</span></div>
            <div className="eg-auth-stat"><strong>API</strong><span>Enterprise-first</span></div>
          </div>
          <div className="eg-auth-features">
            <div>Primary-source style verification signals and role-aware access.</div>
            <div>Hybrid case retrieval with tags, outcomes, constraints, and semantic matching.</div>
            <div>Audit-ready exports, revision history, and reusable structured-case schema.</div>
          </div>
        </div>
      </section>

      <section className="eg-auth-form-panel">
        <div className="eg-auth-card">
          <div className="eg-auth-tabs">
            <button className="active" type="button">Sign In</button>
            <button type="button" disabled>Join Network</button>
          </div>
          <h2>Welcome back</h2>
          <p className="muted">Use a seeded clinician or admin account to enter the workspace.</p>
          {error && <div className="eg-alert error">{error}</div>}
          <form onSubmit={handleSubmit} className="eg-form">
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            <button className="eg-primary-button" type="submit">Enter Workspace</button>
          </form>
          <div className="eg-callout">
            Demo: `admin@demo.health / AdminPass123!`
          </div>
        </div>
      </section>
    </div>
  );
}

function DashboardPage({ user, profile }) {
  const [cases, setCases] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [caseData, roi] = await Promise.all([getCases(), getRoiMetrics()]);
        if (!active) return;
        setCases(caseData);
        setMetrics(roi);
      } catch (err) {
        if (active) setError(err.message);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  const highlightedCases = cases.slice(0, 6);

  return (
    <div className="eg-page-stack">
      <section className="eg-hero-card">
        <div>
          <div className="eg-section-kicker">Clinical command center</div>
          <h1>Good to see you, {user.full_name?.split(" ")[0] || "Doctor"}.</h1>
          <p>
            Monitor cross-specialty case flow, surface similar experiences, and route urgent questions
            to the right expert faster.
          </p>
          <div className="eg-hero-tags">
            <span className="eg-badge verified">{profile?.verified ? "Verified clinician" : "Verification pending"}</span>
            <span className="eg-badge subtle">{profile?.specialty || "General"} focus</span>
            <span className="eg-badge subtle">{profile?.availability_status || "available"}</span>
          </div>
        </div>
        <div className="eg-hero-stats-grid">
          <div className="eg-stat-card"><strong>{cases.length}</strong><span>Org cases</span></div>
          <div className="eg-stat-card"><strong>{metrics?.case_type_counts?.ed_neuro ?? 0}</strong><span>ED neuro</span></div>
          <div className="eg-stat-card"><strong>{metrics?.case_type_counts?.immuno_toxicity ?? 0}</strong><span>Immunotherapy</span></div>
          <div className="eg-stat-card"><strong>{metrics?.ed_metrics?.transfer_avoided ?? 0}</strong><span>Transfers avoided</span></div>
        </div>
      </section>

      {error && <div className="eg-alert error">{error}</div>}

      <div className="eg-dashboard-grid">
        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h3>Case Library</h3>
              <p>Recent cases flowing through the organization.</p>
            </div>
            <Link to="/knowledge" className="eg-text-link">Open AI graph</Link>
          </div>
          <div className="eg-card-list">
            {highlightedCases.map((item) => (
              <Link key={item.id} to={`/cases/${item.id}`} className="eg-list-card">
                <div>
                  <strong>{item.specialty}</strong>
                  <div className="muted">{item.symptoms.slice(0, 118)}</div>
                </div>
                <div className="eg-list-card-side">
                  <span className="eg-badge subtle">{CASE_TYPE_LABELS[item.case_type] || item.case_type}</span>
                  {item.tags?.[0] && <span className="eg-inline-meta">{item.tags[0]}</span>}
                </div>
              </Link>
            ))}
            {highlightedCases.length === 0 && <p className="muted">No cases loaded yet.</p>}
          </div>
        </section>

        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h3>Program Signals</h3>
              <p>Outcome and throughput markers from the seeded network.</p>
            </div>
          </div>
          <div className="eg-metric-stack">
            <div className="eg-metric-row"><span>ED neuro cases</span><strong>{metrics?.case_type_counts?.ed_neuro ?? 0}</strong></div>
            <div className="eg-metric-row"><span>Average consult time</span><strong>{metrics?.ed_metrics?.avg_consult_time ?? "n/a"}</strong></div>
            <div className="eg-metric-row"><span>Transfers avoided</span><strong>{metrics?.ed_metrics?.transfer_avoided ?? 0}</strong></div>
            <div className="eg-metric-row"><span>Immunotherapy cases</span><strong>{metrics?.case_type_counts?.immuno_toxicity ?? 0}</strong></div>
            <div className="eg-metric-row"><span>ICU escalations</span><strong>{metrics?.immuno_metrics?.icu_escalations ?? 0}</strong></div>
            <div className="eg-metric-row"><span>Steroid response</span><strong>{metrics?.immuno_metrics?.steroid_response ?? 0}</strong></div>
          </div>
        </section>
      </div>
    </div>
  );
}

function CaseSelectPage() {
  return (
    <div className="eg-page-stack">
      <section className="eg-panel">
        <div className="eg-panel-header">
          <div>
            <h2>Choose a case program</h2>
            <p>Use the structured intake workflow that best matches the clinical scenario.</p>
          </div>
        </div>
        <div className="eg-program-grid">
          <Link className="eg-program-card" to="/cases/new/general">
            <span className="eg-nav-glyph">GN</span>
            <h3>{CASE_TYPE_LABELS.general}</h3>
            <p>Standard micro-case capture for reusable experience graph records.</p>
          </Link>
          <Link className="eg-program-card" to="/cases/new/ed-neuro">
            <span className="eg-nav-glyph">EN</span>
            <h3>{CASE_TYPE_LABELS.ed_neuro}</h3>
            <p>Time-sensitive neuro triage patterns, consult times, and transfer decisions.</p>
          </Link>
          <Link className="eg-program-card" to="/cases/new/immunotherapy">
            <span className="eg-nav-glyph">IM</span>
            <h3>{CASE_TYPE_LABELS.immuno_toxicity}</h3>
            <p>Capture irAE severity, infusion timing, and recovery outcomes cleanly.</p>
          </Link>
        </div>
      </section>
    </div>
  );
}

function parseTags(value) {
  if (!value) return [];
  return value.split(",").map((tag) => tag.trim()).filter(Boolean);
}

function coerceNumber(value) {
  if (value === "" || value === null || value === undefined) return null;
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

function coerceBoolean(value) {
  if (value === true || value === false) return value;
  if (value === "" || value === null || value === undefined) return null;
  const normalized = String(value).toLowerCase();
  if (["yes", "true", "1"].includes(normalized)) return true;
  if (["no", "false", "0"].includes(normalized)) return false;
  return null;
}

function normalizeTemplateFields(caseType, fields) {
  if (!fields) return {};
  if (caseType === CASE_TYPES.ed_neuro) {
    return {
      ...fields,
      nihss: coerceNumber(fields.nihss),
      consult_time_minutes: coerceNumber(fields.consult_time_minutes),
      transfer_needed: coerceBoolean(fields.transfer_needed),
      transfer_avoided: coerceBoolean(fields.transfer_avoided)
    };
  }
  if (caseType === CASE_TYPES.immuno_toxicity) {
    return {
      ...fields,
      cycle_number: coerceNumber(fields.cycle_number),
      days_since_infusion: coerceNumber(fields.days_since_infusion),
      severity_grade: coerceNumber(fields.severity_grade),
      icu_escalation: coerceBoolean(fields.icu_escalation)
    };
  }
  return fields;
}

function CaseFormPage({ mode }) {
  const params = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(mode === "edit");
  const [caseType, setCaseType] = useState(CASE_TYPES.general);
  const [form, setForm] = useState({
    specialty: "",
    specialty_domain: "",
    symptoms: "",
    demographics: "",
    age_bucket: "",
    constraints: "",
    resource_setting: "",
    suspected_dx: "",
    final_dx: "",
    interventions: "",
    outcomes: "",
    follow_up: "",
    what_changed: "",
    specialty_tags: "",
    free_tags: "",
    outcome_tags: "",
    intervention_tags: ""
  });
  const [templateFields, setTemplateFields] = useState({});

  useEffect(() => {
    if (mode === "edit") {
      let active = true;
      setLoading(true);
      getCase(params.caseId)
        .then((data) => {
          if (!active) return;
          setCaseType(data.case_type || CASE_TYPES.general);
          setForm({
            specialty: data.specialty || "",
            specialty_domain: data.specialty_domain || "",
            symptoms: data.symptoms || "",
            demographics: data.demographics || "",
            age_bucket: data.age_bucket || "",
            constraints: data.constraints || "",
            resource_setting: data.resource_setting || "",
            suspected_dx: data.suspected_dx || "",
            final_dx: data.final_dx || "",
            interventions: data.interventions || "",
            outcomes: data.outcomes || "",
            follow_up: data.follow_up || "",
            what_changed: data.what_changed || "",
            specialty_tags: (data.specialty_tags || []).join(", "),
            free_tags: (data.free_tags || []).join(", "),
            outcome_tags: (data.outcome_tags || []).join(", "),
            intervention_tags: (data.intervention_tags || []).join(", ")
          });
          setTemplateFields(data.template_fields || {});
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
      return () => {
        active = false;
      };
    }
    const program = params.program;
    if (program === "ed-neuro") setCaseType(CASE_TYPES.ed_neuro);
    if (program === "immunotherapy") setCaseType(CASE_TYPES.immuno_toxicity);
  }, [mode, params.caseId, params.program]);

  function updateField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateTemplate(key, value) {
    setTemplateFields((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    const payload = {
      case_type: caseType,
      specialty: form.specialty,
      specialty_domain: form.specialty_domain,
      symptoms: form.symptoms,
      demographics: form.demographics,
      age_bucket: form.age_bucket,
      constraints: form.constraints,
      resource_setting: form.resource_setting,
      suspected_dx: form.suspected_dx,
      final_dx: form.final_dx,
      interventions: form.interventions,
      outcomes: form.outcomes,
      follow_up: form.follow_up,
      what_changed: form.what_changed,
      template_fields: normalizeTemplateFields(caseType, templateFields),
      specialty_tags: parseTags(form.specialty_tags),
      free_tags: parseTags(form.free_tags),
      outcome_tags: parseTags(form.outcome_tags),
      intervention_tags: parseTags(form.intervention_tags)
    };
    try {
      const result = mode === "edit" ? await updateCase(params.caseId, payload) : await createCase(payload);
      navigate(`/cases/${result.id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <div className="eg-loading-card">Loading case...</div>;

  return (
    <div className="eg-page-stack">
      <section className="eg-panel">
        <div className="eg-panel-header">
          <div>
            <h2>{mode === "edit" ? "Update" : "Create"} {CASE_TYPE_LABELS[caseType]}</h2>
            <p>Capture reusable case intelligence without patient identifiers.</p>
          </div>
        </div>
        {error && <div className="eg-alert error">{error}</div>}
        <form className="eg-form" onSubmit={handleSubmit}>
          <div className="eg-grid two">
            <label>
              Specialty
              <input value={form.specialty} onChange={(e) => updateField("specialty", e.target.value)} required />
            </label>
            <label>
              Specialty domain
              <input value={form.specialty_domain} onChange={(e) => updateField("specialty_domain", e.target.value)} />
            </label>
          </div>
          <div className="eg-grid two">
            <label>
              Demographics
              <input value={form.demographics} onChange={(e) => updateField("demographics", e.target.value)} />
            </label>
            <label>
              Age bucket
              <input value={form.age_bucket} onChange={(e) => updateField("age_bucket", e.target.value)} />
            </label>
          </div>
          <label>
            Symptoms
            <textarea value={form.symptoms} onChange={(e) => updateField("symptoms", e.target.value)} required />
          </label>
          <div className="eg-grid two">
            <label>
              Constraints
              <textarea value={form.constraints} onChange={(e) => updateField("constraints", e.target.value)} />
            </label>
            <label>
              Resource setting
              <input value={form.resource_setting} onChange={(e) => updateField("resource_setting", e.target.value)} />
            </label>
          </div>
          <div className="eg-grid two">
            <label>
              Suspected diagnosis
              <textarea value={form.suspected_dx} onChange={(e) => updateField("suspected_dx", e.target.value)} />
            </label>
            <label>
              Final diagnosis
              <textarea value={form.final_dx} onChange={(e) => updateField("final_dx", e.target.value)} />
            </label>
          </div>
          <label>
            Interventions
            <textarea value={form.interventions} onChange={(e) => updateField("interventions", e.target.value)} />
          </label>
          <div className="eg-grid two">
            <label>
              Outcomes
              <textarea value={form.outcomes} onChange={(e) => updateField("outcomes", e.target.value)} />
            </label>
            <label>
              Follow-up
              <textarea value={form.follow_up} onChange={(e) => updateField("follow_up", e.target.value)} />
            </label>
          </div>
          <label>
            What I would do differently
            <textarea value={form.what_changed} onChange={(e) => updateField("what_changed", e.target.value)} />
          </label>

          {caseType === CASE_TYPES.ed_neuro && (
            <div className="eg-subpanel">
              <h3>ED neuro triage fields</h3>
              <div className="eg-grid three">
                <label>Onset time<input value={templateFields.onset_time || ""} onChange={(e) => updateTemplate("onset_time", e.target.value)} /></label>
                <label>Last known well<input value={templateFields.last_known_well || ""} onChange={(e) => updateTemplate("last_known_well", e.target.value)} /></label>
                <label>NIHSS<input type="number" value={templateFields.nihss ?? ""} onChange={(e) => updateTemplate("nihss", e.target.value)} /></label>
              </div>
              <div className="eg-grid three">
                <label>Anticoagulation<input value={templateFields.anticoagulation || ""} onChange={(e) => updateTemplate("anticoagulation", e.target.value)} /></label>
                <label>Imaging available<input value={templateFields.imaging_available || ""} onChange={(e) => updateTemplate("imaging_available", e.target.value)} /></label>
                <label>tPA given<input value={templateFields.tpa_given || ""} onChange={(e) => updateTemplate("tpa_given", e.target.value)} /></label>
              </div>
              <div className="eg-grid two">
                <label>
                  Transfer needed
                  <select value={templateFields.transfer_needed === true ? "yes" : templateFields.transfer_needed === false ? "no" : templateFields.transfer_needed || ""} onChange={(e) => updateTemplate("transfer_needed", e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
                <label>
                  Transfer avoided
                  <select value={templateFields.transfer_avoided === true ? "yes" : templateFields.transfer_avoided === false ? "no" : templateFields.transfer_avoided || ""} onChange={(e) => updateTemplate("transfer_avoided", e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
              </div>
              <label>Consult time (minutes)<input type="number" value={templateFields.consult_time_minutes ?? ""} onChange={(e) => updateTemplate("consult_time_minutes", e.target.value)} /></label>
              <label>Deficits<textarea value={templateFields.deficits || ""} onChange={(e) => updateTemplate("deficits", e.target.value)} /></label>
            </div>
          )}

          {caseType === CASE_TYPES.immuno_toxicity && (
            <div className="eg-subpanel">
              <h3>Immunotherapy toxicity fields</h3>
              <div className="eg-grid three">
                <label>Therapy regimen<input value={templateFields.therapy_regimen || ""} onChange={(e) => updateTemplate("therapy_regimen", e.target.value)} /></label>
                <label>Cycle number<input type="number" value={templateFields.cycle_number ?? ""} onChange={(e) => updateTemplate("cycle_number", e.target.value)} /></label>
                <label>Days since infusion<input type="number" value={templateFields.days_since_infusion ?? ""} onChange={(e) => updateTemplate("days_since_infusion", e.target.value)} /></label>
              </div>
              <div className="eg-grid three">
                <label>irAE system<input value={templateFields.irae_system || ""} onChange={(e) => updateTemplate("irae_system", e.target.value)} /></label>
                <label>Severity grade<input type="number" value={templateFields.severity_grade ?? ""} onChange={(e) => updateTemplate("severity_grade", e.target.value)} /></label>
                <label>Steroid response<input value={templateFields.steroid_response || ""} onChange={(e) => updateTemplate("steroid_response", e.target.value)} /></label>
              </div>
              <div className="eg-grid two">
                <label>
                  ICU escalation
                  <select value={templateFields.icu_escalation === true ? "yes" : templateFields.icu_escalation === false ? "no" : templateFields.icu_escalation || ""} onChange={(e) => updateTemplate("icu_escalation", e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
                <label>Consult services<input value={templateFields.consult_services || ""} onChange={(e) => updateTemplate("consult_services", e.target.value)} /></label>
              </div>
            </div>
          )}

          <div className="eg-grid two">
            <label>Specialty tags<input value={form.specialty_tags} onChange={(e) => updateField("specialty_tags", e.target.value)} /></label>
            <label>Free tags<input value={form.free_tags} onChange={(e) => updateField("free_tags", e.target.value)} /></label>
          </div>
          <div className="eg-grid two">
            <label>Outcome tags<input value={form.outcome_tags} onChange={(e) => updateField("outcome_tags", e.target.value)} /></label>
            <label>Intervention tags<input value={form.intervention_tags} onChange={(e) => updateField("intervention_tags", e.target.value)} /></label>
          </div>
          <button className="eg-primary-button" type="submit">{mode === "edit" ? "Update" : "Create"} case</button>
        </form>
      </section>
    </div>
  );
}

function CaseDetailPage() {
  const params = useParams();
  const [caseItem, setCaseItem] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [detail, similarCases] = await Promise.all([getCase(params.caseId), getSimilarCases(params.caseId)]);
        if (!active) return;
        setCaseItem(detail);
        setSimilar(similarCases);
      } catch (err) {
        if (active) setError(err.message);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [params.caseId]);

  async function handleEndorse() {
    try {
      await endorseCase(params.caseId);
      alert("Case endorsed");
    } catch (err) {
      alert(err.message);
    }
  }

  if (error) return <div className="eg-alert error">{error}</div>;
  if (!caseItem) return <div className="eg-loading-card">Loading case...</div>;

  return (
    <div className="eg-page-stack">
      <div className="eg-dashboard-grid">
        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h2>{caseItem.specialty}</h2>
              <p>Case #{caseItem.id} · {CASE_TYPE_LABELS[caseItem.case_type] || caseItem.case_type}</p>
            </div>
            <div className="eg-inline-actions">
              <button className="eg-ghost-button" onClick={handleEndorse}>Endorse</button>
              <Link className="eg-ghost-button" to={`/cases/${caseItem.id}/edit`}>Edit</Link>
            </div>
          </div>
          <div className="eg-case-meta-row">
            {caseItem.specialty_domain && <span className="eg-badge subtle">{caseItem.specialty_domain}</span>}
            {caseItem.resource_setting && <span className="eg-badge subtle">{caseItem.resource_setting}</span>}
            {caseItem.age_bucket && <span className="eg-badge subtle">{caseItem.age_bucket}</span>}
          </div>
          <div className="eg-case-section">
            <h4>Symptoms</h4>
            <p>{caseItem.symptoms}</p>
          </div>
          {caseItem.constraints && <div className="eg-case-section"><h4>Constraints</h4><p>{caseItem.constraints}</p></div>}
          {caseItem.interventions && <div className="eg-case-section"><h4>Interventions</h4><p>{caseItem.interventions}</p></div>}
          {caseItem.outcomes && <div className="eg-case-section"><h4>Outcomes</h4><p>{caseItem.outcomes}</p></div>}
          {caseItem.follow_up && <div className="eg-case-section"><h4>Follow-up</h4><p>{caseItem.follow_up}</p></div>}
          {caseItem.what_changed && <div className="eg-case-section"><h4>What I would do differently</h4><p>{caseItem.what_changed}</p></div>}
          <div className="eg-tag-list">
            {caseItem.tags.map((tag) => <span key={tag} className="eg-badge subtle">{tag}</span>)}
          </div>
          {caseItem.template_fields && Object.keys(caseItem.template_fields).length > 0 && (
            <div className="eg-subpanel">
              <h3>Program fields</h3>
              <div className="eg-definition-list">
                {Object.entries(caseItem.template_fields).map(([key, value]) => (
                  <div key={key} className="eg-definition-row">
                    <span>{key}</span>
                    <strong>{String(value)}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h3>Similar cases</h3>
              <p>Persisted graph edges and hybrid retrieval explanations.</p>
            </div>
          </div>
          <div className="eg-card-list">
            {similar.map((item) => (
              <div key={item.case_id} className="eg-list-card vertical">
                <div className="eg-list-card-top">
                  <strong>Case #{item.case_id}</strong>
                  <span className="eg-badge verified">Score {item.score.toFixed(2)}</span>
                </div>
                {item.explanation?.length > 0 && (
                  <ul className="eg-explanation-list">
                    {item.explanation.map((line, idx) => <li key={idx}>{line}</li>)}
                  </ul>
                )}
              </div>
            ))}
            {similar.length === 0 && <p className="muted">No similar cases yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}

function MatchPage() {
  const [summary, setSummary] = useState("");
  const [caseType, setCaseType] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [region, setRegion] = useState("");
  const [urgency, setUrgency] = useState("");
  const [tags, setTags] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      const data = await matchExperts({
        summary,
        case_type: caseType || null,
        specialty: specialty || null,
        region: region || null,
        urgency: urgency || null,
        tags: parseTags(tags)
      });
      setResults(data);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="eg-page-stack">
      <div className="eg-dashboard-grid">
        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h2>Expert routing</h2>
              <p>Rank clinicians using similarity, trust signals, rarity, and availability.</p>
            </div>
          </div>
          {error && <div className="eg-alert error">{error}</div>}
          <form className="eg-form" onSubmit={handleSubmit}>
            <label>
              Case program
              <select value={caseType} onChange={(e) => setCaseType(e.target.value)}>
                <option value="">Any</option>
                <option value={CASE_TYPES.general}>General</option>
                <option value={CASE_TYPES.ed_neuro}>ED neuro triage</option>
                <option value={CASE_TYPES.immuno_toxicity}>Immunotherapy toxicity</option>
              </select>
            </label>
            <label>
              Summary
              <textarea value={summary} onChange={(e) => setSummary(e.target.value)} required />
            </label>
            <div className="eg-grid three">
              <label>Specialty<input value={specialty} onChange={(e) => setSpecialty(e.target.value)} /></label>
              <label>Region<input value={region} onChange={(e) => setRegion(e.target.value)} /></label>
              <label>
                Urgency
                <select value={urgency} onChange={(e) => setUrgency(e.target.value)}>
                  <option value="">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </label>
            </div>
            <label>Tags<input value={tags} onChange={(e) => setTags(e.target.value)} /></label>
            <button className="eg-primary-button" type="submit">Find experts</button>
          </form>
        </section>

        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h3>Ranked clinicians</h3>
              <p>Explainable match output from the routing service.</p>
            </div>
          </div>
          <div className="eg-card-list">
            {results.map((result) => (
              <div key={result.doctor_id} className="eg-list-card vertical">
                <div className="eg-list-card-top">
                  <div>
                    <strong>{result.doctor_name}</strong>
                    <div className="muted">{result.specialty} · {result.region || "Region unknown"}</div>
                  </div>
                  <span className="eg-badge verified">Score {result.score.toFixed(2)}</span>
                </div>
                <div className="eg-score-breakdown">
                  {Object.entries(result.score_breakdown || {}).map(([key, value]) => (
                    <span key={key} className="eg-badge subtle">{key}: {Number(value).toFixed(2)}</span>
                  ))}
                </div>
                <ul className="eg-explanation-list">
                  {result.explanation.map((line, idx) => <li key={idx}>{line}</li>)}
                </ul>
              </div>
            ))}
            {results.length === 0 && <p className="muted">Run a routing query to see recommendations.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}

function ProfilePage({ user, profile }) {
  const [cases, setCases] = useState([]);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    let active = true;
    getCases().then((data) => {
      if (active) setCases(data);
    }).catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const specialtyCount = cases.filter((item) => item.specialty === profile?.specialty).length;
  const topTags = useMemo(() => {
    const counts = {};
    cases.forEach((item) => {
      (item.tags || []).forEach((tag) => {
        counts[tag] = (counts[tag] || 0) + 1;
      });
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [cases]);

  return (
    <div className="eg-page-stack">
      <section className="eg-profile-hero">
        <div className="eg-profile-cover" />
        <div className="eg-profile-body">
          <div className="eg-profile-header-row">
            <div className="eg-profile-avatar">{initials(user.full_name || user.email)}</div>
            <div className="eg-profile-header-copy">
              <div className="eg-profile-title-row">
                <h1>{user.full_name || user.email}</h1>
                <span className="eg-badge verified">{profile?.verified ? "Verified" : "Pending"}</span>
              </div>
              <p>{profile?.specialty || "Clinician"} · {profile?.region || "Region pending"} · {user.role}</p>
              <div className="eg-tag-list">
                <span className="eg-badge subtle">{profile?.availability_status || "available"}</span>
                <span className="eg-badge subtle">{profile?.years_experience || 0} years experience</span>
                <span className="eg-badge subtle">{profile?.proof_status || "manual_review"}</span>
              </div>
            </div>
          </div>
          <div className="eg-profile-stats">
            <div><strong>{cases.length}</strong><span>Org cases visible</span></div>
            <div><strong>{specialtyCount}</strong><span>Specialty-aligned cases</span></div>
            <div><strong>{topTags.length}</strong><span>Active tag clusters</span></div>
            <div><strong>{profile?.verified ? "High" : "Pending"}</strong><span>Trust status</span></div>
          </div>
        </div>
      </section>

      <section className="eg-tab-strip">
        {["overview", "contributions", "credentials", "reviews"].map((tab) => (
          <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </section>

      {activeTab === "overview" && (
        <div className="eg-dashboard-grid">
          <section className="eg-panel">
            <div className="eg-panel-header"><div><h3>Profile overview</h3><p>Reusable clinician metadata and specialty alignment.</p></div></div>
            <div className="eg-definition-list">
              <div className="eg-definition-row"><span>Email</span><strong>{user.email}</strong></div>
              <div className="eg-definition-row"><span>Specialty</span><strong>{profile?.specialty || "n/a"}</strong></div>
              <div className="eg-definition-row"><span>Region</span><strong>{profile?.region || "n/a"}</strong></div>
              <div className="eg-definition-row"><span>Availability</span><strong>{profile?.availability_status || "n/a"}</strong></div>
              <div className="eg-definition-row"><span>Verification</span><strong>{profile?.verified ? "Verified" : "Pending"}</strong></div>
            </div>
          </section>
          <section className="eg-panel">
            <div className="eg-panel-header"><div><h3>Top specialty tags</h3><p>Signals currently strongest across the visible org graph.</p></div></div>
            <div className="eg-card-list">
              {topTags.map(([tag, count]) => (
                <div key={tag} className="eg-list-card"><strong>{tag}</strong><span className="eg-badge subtle">{count} mentions</span></div>
              ))}
              {topTags.length === 0 && <p className="muted">No tag signals yet.</p>}
            </div>
          </section>
        </div>
      )}

      {activeTab === "contributions" && (
        <section className="eg-panel">
          <div className="eg-panel-header"><div><h3>Relevant contributions</h3><p>Recent cases most aligned to your specialty lane.</p></div></div>
          <div className="eg-card-list">
            {cases.filter((item) => !profile?.specialty || item.specialty === profile.specialty).slice(0, 8).map((item) => (
              <Link key={item.id} to={`/cases/${item.id}`} className="eg-list-card">
                <div>
                  <strong>{item.specialty}</strong>
                  <div className="muted">{item.symptoms.slice(0, 110)}</div>
                </div>
                <span className="eg-badge subtle">{CASE_TYPE_LABELS[item.case_type] || item.case_type}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {activeTab === "credentials" && (
        <section className="eg-panel">
          <div className="eg-panel-header"><div><h3>Credentials and trust</h3><p>Enterprise trust signals carried into routing and endorsements.</p></div></div>
          <div className="eg-metric-stack">
            <div className="eg-metric-row"><span>Role</span><strong>{user.role}</strong></div>
            <div className="eg-metric-row"><span>Verification status</span><strong>{profile?.verified ? "Verified" : "Pending review"}</strong></div>
            <div className="eg-metric-row"><span>Proof workflow</span><strong>{profile?.proof_status || "manual_review"}</strong></div>
            <div className="eg-metric-row"><span>Organization scope</span><strong>{user.org_id}</strong></div>
          </div>
        </section>
      )}

      {activeTab === "reviews" && (
        <section className="eg-panel">
          <div className="eg-panel-header"><div><h3>Peer review posture</h3><p>This branch keeps the trust model outcome-based rather than follower-based.</p></div></div>
          <div className="eg-callout secondary">
            Endorsements, completeness, rarity exposure, and availability are already wired into the
            enterprise routing score. Dedicated per-profile review feeds can build on that next.
          </div>
        </section>
      )}
    </div>
  );
}

function KnowledgePage({ profile }) {
  const [mode, setMode] = useState("chat");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([
    {
      role: "assistant",
      content:
        "Welcome to the AI Knowledge Graph. Ask a clinical question and I will synthesize likely relevant cases from this organization with confidence and retrieval explanations."
    }
  ]);
  const [searchState, setSearchState] = useState({
    summary: "",
    specialty: profile?.specialty || "",
    case_type: "",
    tags: "",
    results: [],
    loading: false
  });
  const [recommendations, setRecommendations] = useState([]);
  const [knowledgeError, setKnowledgeError] = useState(null);

  useEffect(() => {
    let active = true;
    async function loadRecommendations() {
      try {
        const data = await searchCases({
          summary: `${profile?.specialty || "clinical"} outcomes and similar cases`,
          specialty: profile?.specialty || null,
          limit: 4
        });
        if (active) setRecommendations(data);
      } catch (err) {
        if (active) setRecommendations([]);
      }
    }
    loadRecommendations();
    return () => {
      active = false;
    };
  }, [profile?.specialty]);

  async function runKnowledgeSearch(payload) {
    setSearchState((prev) => ({ ...prev, loading: true }));
    setKnowledgeError(null);
    try {
      const results = await searchCases(payload);
      setSearchState((prev) => ({ ...prev, results, loading: false }));
      return results;
    } catch (err) {
      setSearchState((prev) => ({ ...prev, loading: false }));
      setKnowledgeError(err.message);
      return [];
    }
  }

  async function sendKnowledgeChat(query) {
    if (!query.trim()) return;
    setChatMessages((prev) => [...prev, { role: "user", content: query }]);
    setChatInput("");
    const results = await runKnowledgeSearch({
      summary: query,
      specialty: profile?.specialty || null,
      tags: []
    });
    const summary =
      results.length > 0
        ? `I found ${results.length} relevant cases. The strongest match is case #${results[0].case_id} in ${results[0].specialty} with confidence ${Math.round(results[0].confidence * 100)}%. Key signals: ${results[0].explanation.join(", ")}.`
        : "I could not find strong case matches from the current graph for that phrasing. Try a more specific specialty, outcome, or symptom cluster.";
    setChatMessages((prev) => [...prev, { role: "assistant", content: summary, sources: results.slice(0, 3) }]);
  }

  async function handleSearchSubmit(event) {
    event.preventDefault();
    await runKnowledgeSearch({
      summary: searchState.summary,
      specialty: searchState.specialty || null,
      case_type: searchState.case_type || null,
      tags: parseTags(searchState.tags),
      limit: 8
    });
  }

  return (
    <div className="eg-page-stack">
      <section className="eg-knowledge-header">
        <div>
          <div className="eg-section-kicker">AI knowledge graph</div>
          <h1>Collective clinical intelligence</h1>
          <p>Search, synthesize, and recommend from the structured experience graph without losing traceability.</p>
        </div>
        <div className="eg-live-chip">Live · enterprise retrieval active</div>
      </section>

      <div className="eg-mode-grid">
        <button type="button" className={mode === "chat" ? "active" : ""} onClick={() => setMode("chat")}><strong>AI Chat</strong><span>Ask clinical questions and get sourced answers.</span></button>
        <button type="button" className={mode === "search" ? "active" : ""} onClick={() => setMode("search")}><strong>Search & Browse</strong><span>Filter and inspect hybrid retrieval results.</span></button>
        <button type="button" className={mode === "recommendations" ? "active" : ""} onClick={() => setMode("recommendations")}><strong>Recommendations</strong><span>AI-ranked insights for your current specialty context.</span></button>
      </div>

      {knowledgeError && <div className="eg-alert error">{knowledgeError}</div>}

      {mode === "chat" && (
        <div className="eg-knowledge-grid">
          <section className="eg-panel chat">
            <div className="eg-chat-feed">
              {chatMessages.map((message, index) => (
                <div key={index} className={`eg-chat-bubble ${message.role}`}>
                  <div className="eg-chat-bubble-body">{message.content}</div>
                  {message.sources?.length > 0 && (
                    <div className="eg-chat-sources">
                      {message.sources.map((source) => (
                        <div key={source.case_id} className="eg-source-card">
                          <strong>Case #{source.case_id}</strong>
                          <span>{source.specialty}</span>
                          <span>{source.explanation?.join(" · ")}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="eg-chat-input-row">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask a clinical question..."
              />
              <button className="eg-primary-button" type="button" onClick={() => sendKnowledgeChat(chatInput)}>Send</button>
            </div>
            <div className="eg-hipaa-note">Do not include patient identifiers in prompts.</div>
          </section>

          <aside className="eg-panel side">
            <div className="eg-panel-header"><div><h3>Suggested queries</h3><p>Try a seeded clinical pattern.</p></div></div>
            <div className="eg-card-list">
              {KNOWLEDGE_QUERIES.map((query) => (
                <button key={query} type="button" className="eg-query-card" onClick={() => sendKnowledgeChat(query)}>
                  {query}
                </button>
              ))}
            </div>
          </aside>
        </div>
      )}

      {mode === "search" && (
        <div className="eg-knowledge-grid search">
          <aside className="eg-panel side">
            <div className="eg-panel-header"><div><h3>Filters</h3><p>Use specialty and case program to narrow retrieval.</p></div></div>
            <form className="eg-form" onSubmit={handleSearchSubmit}>
              <label>Summary<input value={searchState.summary} onChange={(e) => setSearchState((prev) => ({ ...prev, summary: e.target.value }))} /></label>
              <label>Specialty<input value={searchState.specialty} onChange={(e) => setSearchState((prev) => ({ ...prev, specialty: e.target.value }))} /></label>
              <label>
                Case type
                <select value={searchState.case_type} onChange={(e) => setSearchState((prev) => ({ ...prev, case_type: e.target.value }))}>
                  <option value="">Any</option>
                  <option value={CASE_TYPES.general}>General</option>
                  <option value={CASE_TYPES.ed_neuro}>ED neuro triage</option>
                  <option value={CASE_TYPES.immuno_toxicity}>Immunotherapy toxicity</option>
                </select>
              </label>
              <label>Tags<input value={searchState.tags} onChange={(e) => setSearchState((prev) => ({ ...prev, tags: e.target.value }))} /></label>
              <button className="eg-primary-button" type="submit">{searchState.loading ? "Searching..." : "Run search"}</button>
            </form>
          </aside>
          <section className="eg-panel">
            <div className="eg-panel-header"><div><h3>Knowledge entries</h3><p>{searchState.results.length} result(s) from hybrid retrieval.</p></div></div>
            <div className="eg-card-list">
              {searchState.results.map((item) => (
                <div key={item.case_id} className="eg-list-card vertical">
                  <div className="eg-list-card-top">
                    <div>
                      <strong>Case #{item.case_id}</strong>
                      <div className="muted">{item.specialty} · {CASE_TYPE_LABELS[item.case_type] || item.case_type}</div>
                    </div>
                    <span className="eg-badge verified">{Math.round(item.confidence * 100)}%</span>
                  </div>
                  <div className="eg-score-breakdown">
                    {Object.entries(item.score_breakdown || {}).map(([key, value]) => (
                      <span key={key} className="eg-badge subtle">{key}: {Number(value).toFixed(2)}</span>
                    ))}
                  </div>
                  <ul className="eg-explanation-list">
                    {item.explanation?.map((line, idx) => <li key={idx}>{line}</li>)}
                  </ul>
                </div>
              ))}
              {!searchState.loading && searchState.results.length === 0 && (
                <div className="eg-empty-state">
                  <strong>No results yet.</strong>
                  <p>Run a search to browse knowledge entries from the graph.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {mode === "recommendations" && (
        <section className="eg-panel">
          <div className="eg-panel-header">
            <div>
              <h3>Recommendations for {profile?.specialty || "your specialty"}</h3>
              <p>These are surfaced from the current graph using your specialty context.</p>
            </div>
          </div>
          <div className="eg-card-list">
            {recommendations.map((item) => (
              <Link key={item.case_id} to={`/cases/${item.case_id}`} className="eg-list-card vertical">
                <div className="eg-list-card-top">
                  <strong>Case #{item.case_id}</strong>
                  <span className="eg-badge verified">{Math.round(item.confidence * 100)}%</span>
                </div>
                <div className="muted">{item.specialty}</div>
                <ul className="eg-explanation-list">
                  {item.explanation?.map((line, idx) => <li key={idx}>{line}</li>)}
                </ul>
              </Link>
            ))}
            {recommendations.length === 0 && <p className="muted">No recommendations available yet.</p>}
          </div>
        </section>
      )}
    </div>
  );
}

function AdminPage() {
  const [logs, setLogs] = useState([]);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [exportCount, setExportCount] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    Promise.all([getAdminLogs(), getSystemMetrics()])
      .then(([logData, metrics]) => {
        if (!active) return;
        setLogs(logData);
        setSystemMetrics(metrics);
      })
      .catch((err) => setError(err.message));
    return () => {
      active = false;
    };
  }, []);

  async function handleExport() {
    try {
      const data = await exportCases();
      setExportCount(data.length);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="eg-page-stack">
      <section className="eg-panel">
        <div className="eg-panel-header">
          <div>
            <h2>Admin control room</h2>
            <p>Audit, export, and system observability for the current organization.</p>
          </div>
          <button className="eg-primary-button" type="button" onClick={handleExport}>Export cases</button>
        </div>
        {error && <div className="eg-alert error">{error}</div>}
        {exportCount !== null && <div className="eg-callout secondary">Export returned {exportCount} cases.</div>}
        {systemMetrics && (
          <div className="eg-hero-stats-grid admin">
            <div className="eg-stat-card"><strong>{systemMetrics.totals.cases}</strong><span>Cases</span></div>
            <div className="eg-stat-card"><strong>{systemMetrics.totals.users}</strong><span>Users</span></div>
            <div className="eg-stat-card"><strong>{systemMetrics.totals.verified_profiles}</strong><span>Verified profiles</span></div>
            <div className="eg-stat-card"><strong>{systemMetrics.totals.audit_events}</strong><span>Audit events</span></div>
          </div>
        )}
      </section>

      <section className="eg-panel">
        <div className="eg-panel-header"><div><h3>Audit stream</h3><p>Recent enterprise actions across auth, data access, and exports.</p></div></div>
        <div className="eg-card-list">
          {logs.map((log, idx) => (
            <div key={idx} className="eg-list-card">
              <div>
                <strong>{log.action}</strong>
                <div className="muted">{log.entity_type}{log.entity_id ? ` #${log.entity_id}` : ""}</div>
                <div className="muted">{log.viewer_email || "system"}</div>
              </div>
              <span className="eg-badge subtle">{log.created_at.slice(0, 10)}</span>
            </div>
          ))}
          {logs.length === 0 && <p className="muted">No logs yet.</p>}
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const { user, setUser, profile, setProfile, loading } = useAuth();

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setProfile(null);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={setUser} onProfile={setProfile} />} />
        <Route
          path="*"
          element={
            <ProtectedRoute user={user} loading={loading}>
              <AppShell user={user} profile={profile} onLogout={handleLogout}>
                <Routes>
                  <Route path="/" element={<DashboardPage user={user} profile={profile} />} />
                  <Route path="/profile" element={<ProfilePage user={user} profile={profile} />} />
                  <Route path="/knowledge" element={<KnowledgePage profile={profile} />} />
                  <Route path="/cases/new" element={<CaseSelectPage />} />
                  <Route path="/cases/new/:program" element={<CaseFormPage mode="create" />} />
                  <Route path="/cases/:caseId/edit" element={<CaseFormPage mode="edit" />} />
                  <Route path="/cases/:caseId" element={<CaseDetailPage />} />
                  <Route path="/match" element={<MatchPage />} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppShell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
