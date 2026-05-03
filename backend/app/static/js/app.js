async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function login(event) {
  event.preventDefault();
  const payload = {
    email: event.target.email.value,
    password: event.target.password.value,
  };
  await postJson("/api/auth/login", payload);
  window.location.href = "/dashboard";
}

async function register(event) {
  event.preventDefault();
  const payload = {
    org_name: event.target.org_name.value,
    email: event.target.email.value,
    password: event.target.password.value,
    specialty: event.target.specialty.value,
    years_experience: parseInt(event.target.years_experience.value || "0", 10) || null,
    region: event.target.region.value,
  };
  await postJson("/api/auth/register", payload);
  await postJson("/api/auth/login", { email: payload.email, password: payload.password });
  window.location.href = "/dashboard";
}

async function createCase(event) {
  event.preventDefault();
  const payload = {
    title: event.target.title.value,
    demographics: event.target.demographics.value,
    symptoms: event.target.symptoms.value,
    constraints: event.target.constraints.value,
    suspected_dx: event.target.suspected_dx.value,
    final_dx: event.target.final_dx.value,
    interventions: event.target.interventions.value,
    outcomes: event.target.outcomes.value,
    what_differently: event.target.what_differently.value,
    domain_tags: event.target.domain_tags.value.split(",").map(t => t.trim()).filter(Boolean),
    icd_tags: event.target.icd_tags.value.split(",").map(t => t.trim()).filter(Boolean),
  };
  const data = await postJson("/api/cases", payload);
  window.location.href = `/cases/${data.id}/view`;
}

async function searchCases(event) {
  event.preventDefault();
  const payload = {
    query: event.target.query.value,
    specialty: event.target.specialty.value || null,
    region: event.target.region.value || null,
    tags: event.target.tags.value.split(",").map(t => t.trim()).filter(Boolean),
    top_k: parseInt(event.target.top_k.value || "5", 10),
  };
  const results = await postJson("/api/cases/search", payload);
  const list = document.getElementById("results");
  list.innerHTML = "";
  results.forEach(item => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${item.title}</strong> — score ${item.score} <a href="/cases/${item.case_id}/view">View</a>`;
    list.appendChild(li);
  });
}

async function matchExperts(event) {
  event.preventDefault();
  const payload = {
    case_summary: event.target.case_summary.value,
    specialty: event.target.specialty.value || null,
    region: event.target.region.value || null,
    urgency: event.target.urgency.value || null,
    top_k: parseInt(event.target.top_k.value || "5", 10),
  };
  const results = await postJson("/api/match", payload);
  const list = document.getElementById("matches");
  list.innerHTML = "";
  results.forEach(item => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${item.email}</strong> — ${item.explanation}`;
    list.appendChild(li);
  });
}
