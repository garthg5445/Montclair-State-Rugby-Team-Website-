/*ADMIN PAGE*/

const PER_PAGE = 25;

let currentPage = 1;

const loginSection = document.getElementById("loginSection");
const submissionsSection = document.getElementById("submissionsSection");
const adminNavInfo = document.getElementById("adminNavInfo");


async function api(path, options = {}) {

  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    throw error;
  }

  return data;
}


function showError(element, message) {
  element.textContent = message;
  element.classList.remove("d-none");
}


function showLogin() {
  submissionsSection.classList.add("d-none");
  adminNavInfo.classList.add("d-none");
  loginSection.classList.remove("d-none");
}


function showSubmissions(email) {
  loginSection.classList.add("d-none");
  document.getElementById("adminEmail").textContent = email;
  adminNavInfo.classList.remove("d-none");
  submissionsSection.classList.remove("d-none");
  loadSubmissions(1);
}


function formatSubmittedAt(isoString) {
  if (!isoString) {
    return "";
  }

  // SQLite drops the timezone, so a timestamp without one is UTC.
  const hasZone = /[zZ]|[+-]\d{2}:\d{2}$/.test(isoString);

  return new Date(hasZone ? isoString : isoString + "Z").toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}


function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "";
  return td;
}


function renderSubmissions(data) {

  const body = document.getElementById("submissionsBody");

  body.replaceChildren();

  document.getElementById("submissionCount").textContent =
    `${data.total} total submission${data.total === 1 ? "" : "s"}`;

  if (data.submissions.length === 0) {
    const row = document.createElement("tr");
    const empty = cell("No submissions yet.");
    empty.colSpan = 7;
    empty.className = "text-center text-muted py-4";
    row.appendChild(empty);
    body.appendChild(row);
  }

  data.submissions.forEach(submission => {

    const row = document.createElement("tr");

    row.appendChild(cell(formatSubmittedAt(submission.SubmittedAt)));
    row.appendChild(cell(submission.FullName));

    const emailCell = document.createElement("td");
    const emailLink = document.createElement("a");
    emailLink.href = `mailto:${submission.Email}`;
    emailLink.textContent = submission.Email;
    emailCell.appendChild(emailLink);
    row.appendChild(emailCell);

    row.appendChild(cell(submission.Position));
    row.appendChild(cell(submission.ExperienceLevel));

    const commentsCell = cell(submission.Comments);
    commentsCell.style.whiteSpace = "pre-wrap";
    commentsCell.style.maxWidth = "320px";
    row.appendChild(commentsCell);

    const actionsCell = document.createElement("td");
    const deleteButton = document.createElement("button");
    deleteButton.className = "btn btn-outline-danger btn-sm";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteSubmission(submission));
    actionsCell.appendChild(deleteButton);
    row.appendChild(actionsCell);

    body.appendChild(row);
  });

  const pages = Math.max(data.pages, 1);
  document.getElementById("pageInfo").textContent = `Page ${data.page} of ${pages}`;
  document.getElementById("prevPage").disabled = data.page <= 1;
  document.getElementById("nextPage").disabled = data.page >= pages;
}


async function loadSubmissions(page) {

  const errorBox = document.getElementById("submissionsError");
  errorBox.classList.add("d-none");

  try {
    const data = await api(`/api/admin/recruitment?page=${page}&per_page=${PER_PAGE}`);
    currentPage = data.page;
    renderSubmissions(data);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
}


async function deleteSubmission(submission) {

  if (!confirm(`Delete the submission from ${submission.FullName}? This cannot be undone.`)) {
    return;
  }

  try {
    await api(`/api/admin/recruitment/${encodeURIComponent(submission.SubmissionID)}`, {
      method: "DELETE"
    });
    loadSubmissions(currentPage);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(document.getElementById("submissionsError"), error.message);
  }
}


/*LOGIN / LOGOUT*/

document.getElementById("loginForm").addEventListener("submit", async event => {

  event.preventDefault();

  const errorBox = document.getElementById("loginError");
  errorBox.classList.add("d-none");

  try {
    const data = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({
        Email: document.getElementById("loginEmail").value,
        Password: document.getElementById("loginPassword").value
      })
    });
    event.target.reset();
    showSubmissions(data.Email);
  } catch (error) {
    showError(errorBox, error.message);
  }
});


document.getElementById("logoutButton").addEventListener("click", async () => {
  await api("/api/admin/logout", { method: "POST" }).catch(() => {});
  showLogin();
});


document.getElementById("prevPage").addEventListener("click", () => loadSubmissions(currentPage - 1));
document.getElementById("nextPage").addEventListener("click", () => loadSubmissions(currentPage + 1));


/*INITIALIZE*/

api("/api/admin/me")
  .then(data => showSubmissions(data.Email))
  .catch(() => showLogin());
