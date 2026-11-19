/*ADMIN PAGE*/

const PER_PAGE = 25;

let currentPage = 1;
let editingEventId = null;

const loginSection = document.getElementById("loginSection");
const adminDashboard = document.getElementById("adminDashboard");
const adminNavInfo = document.getElementById("adminNavInfo");
const backHomeButton = document.getElementById("backHomeButton");

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(path, {
    credentials: "same-origin",
    headers,
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


function showSuccess(element, message) {
  element.textContent = message;
  element.classList.remove("d-none");
}


function showLogin() {
  adminDashboard.classList.add("d-none");
  adminNavInfo.classList.add("d-none");
  backHomeButton.classList.remove("d-none");
  loginSection.classList.remove("d-none");
}


function showDashboard(email) {
  loginSection.classList.add("d-none");
  backHomeButton.classList.add("d-none");
  document.getElementById("adminEmail").textContent = email;
  adminNavInfo.classList.remove("d-none");
  adminDashboard.classList.remove("d-none");
  loadEvents();
  loadSeasonRecords();
  loadStaff();
  loadSubmissions(1);
}


function formatSubmittedAt(isoString) {
  if (!isoString) {
    return "";
  }

  const hasZone = /[zZ]|[+-]\d{2}:\d{2}$/.test(isoString);

  return new Date(hasZone ? isoString : isoString + "Z").toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}


function formatDisplayDate(dateString) {
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateString || "";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
}


function formatDisplayTime(timeString) {
  if (!timeString) return "";
  if (/^\d{2}:\d{2}/.test(timeString)) {
    const [hours, minutes] = timeString.split(":");
    const date = new Date();
    date.setHours(Number(hours), Number(minutes), 0, 0);
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit"
    });
  }
  return timeString;
}


function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "";
  return td;
}


/*EVENTS*/

function syncEventTypeFields() {
  const isGame = document.getElementById("eventType").value === "game";
  const homeAwayGroup = document.getElementById("homeAwayGroup");
  const opponentLabel = document.getElementById("eventOpponentLabel");
  const opponent = document.getElementById("eventOpponent");
  const homeAway = document.getElementById("eventHomeAway");

  homeAwayGroup.classList.toggle("d-none", !isGame);
  homeAway.required = isGame;
  opponent.required = isGame;
  opponentLabel.textContent = isGame ? "Opposing Team" : "Session Name (optional)";
  if (!isGame) {
    homeAway.value = "home";
  }
}


function resetEventForm() {
  editingEventId = null;
  document.getElementById("eventForm").reset();
  document.getElementById("eventId").value = "";
  document.getElementById("eventFormTitle").textContent = "Add Event";
  document.getElementById("eventSubmitButton").textContent = "Add Event";
  document.getElementById("eventCancelEdit").classList.add("d-none");
  syncEventTypeFields();
}


function fillEventForm(event) {
  editingEventId = event.EventID;
  document.getElementById("eventId").value = event.EventID;
  document.getElementById("eventType").value = event.EventType;
  document.getElementById("eventHomeAway").value = event.HomeAway || "home";
  document.getElementById("eventStatus").value = event.Status;
  document.getElementById("eventOpponent").value = event.Opponent || "";
  document.getElementById("eventLocation").value = event.Location || "";
  document.getElementById("eventDate").value = event.EventDate || "";
  document.getElementById("eventTime").value = (event.EventTime || "").slice(0, 5);
  document.getElementById("eventFormTitle").textContent = "Edit Event";
  document.getElementById("eventSubmitButton").textContent = "Save Changes";
  document.getElementById("eventCancelEdit").classList.remove("d-none");
  syncEventTypeFields();
  document.getElementById("admin-schedule").scrollIntoView({ behavior: "smooth" });
}


function renderEvents(events) {
  const body = document.getElementById("eventsBody");
  body.replaceChildren();

  if (!events.length) {
    const row = document.createElement("tr");
    const empty = cell("No events yet. Add a practice or game above.");
    empty.colSpan = 8;
    empty.className = "text-center text-muted py-4";
    row.appendChild(empty);
    body.appendChild(row);
    return;
  }

  events.forEach(event => {
    const row = document.createElement("tr");
    row.appendChild(cell(formatDisplayDate(event.EventDate)));
    row.appendChild(cell(formatDisplayTime(event.EventTime)));
    row.appendChild(cell(event.EventType === "game" ? "Game" : "Practice"));
    row.appendChild(cell(event.Opponent || ""));
    row.appendChild(cell(
      event.EventType === "game"
        ? (event.HomeAway === "away" ? "Away" : "Home")
        : "—"
    ));
    row.appendChild(cell(
      event.Status.charAt(0).toUpperCase() + event.Status.slice(1)
    ));
    row.appendChild(cell(event.Location || ""));

    const actions = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.className = "btn btn-outline-primary btn-sm me-2";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => fillEventForm(event));

    const deleteButton = document.createElement("button");
    deleteButton.className = "btn btn-outline-danger btn-sm";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteEvent(event));

    actions.appendChild(editButton);
    actions.appendChild(deleteButton);
    row.appendChild(actions);
    body.appendChild(row);
  });
}


async function loadEvents() {
  const errorBox = document.getElementById("eventsError");
  errorBox.classList.add("d-none");

  try {
    const data = await api("/api/admin/events");
    renderEvents(data.events || []);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
}


async function deleteEvent(event) {
  if (!confirm(`Delete this ${event.EventType}? This cannot be undone.`)) {
    return;
  }

  try {
    await api(`/api/admin/events/${encodeURIComponent(event.EventID)}`, {
      method: "DELETE"
    });
    if (editingEventId === event.EventID) {
      resetEventForm();
    }
    loadEvents();
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(document.getElementById("eventsError"), error.message);
  }
}


document.getElementById("eventType").addEventListener("change", syncEventTypeFields);
document.getElementById("eventCancelEdit").addEventListener("click", resetEventForm);

document.getElementById("eventForm").addEventListener("submit", async event => {
  event.preventDefault();

  const errorBox = document.getElementById("eventsError");
  const successBox = document.getElementById("eventsSuccess");
  errorBox.classList.add("d-none");
  successBox.classList.add("d-none");

  const payload = {
    EventType: document.getElementById("eventType").value,
    HomeAway: document.getElementById("eventHomeAway").value,
    Status: document.getElementById("eventStatus").value,
    Opponent: document.getElementById("eventOpponent").value,
    Location: document.getElementById("eventLocation").value,
    EventDate: document.getElementById("eventDate").value,
    EventTime: document.getElementById("eventTime").value
  };

  try {
    if (editingEventId) {
      await api(`/api/admin/events/${encodeURIComponent(editingEventId)}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      showSuccess(successBox, "Event updated.");
    } else {
      await api("/api/admin/events", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      showSuccess(successBox, "Event added.");
    }
    resetEventForm();
    loadEvents();
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
});


/*SEASON RECORDS*/

let editingSeasonRecordId = null;

function currentAcademicStartYear(today = new Date()) {
  return today.getMonth() >= 7 ? today.getFullYear() : today.getFullYear() - 1;
}

function populateSeasonLabelOptions() {
  const select = document.getElementById("seasonLabel");
  if (!select) return;

  const earliestStart = 1997;
  const latestStart = currentAcademicStartYear();
  const previousValue = select.value;

  select.replaceChildren();

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a season...";
  select.appendChild(placeholder);

  for (let startYear = latestStart; startYear >= earliestStart; startYear -= 1) {
    const label = `${startYear}-${startYear + 1}`;
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    select.appendChild(option);
  }

  if (previousValue && [...select.options].some(option => option.value === previousValue)) {
    select.value = previousValue;
  }
}

function resetSeasonRecordForm() {
  editingSeasonRecordId = null;
  document.getElementById("seasonRecordForm").reset();
  document.getElementById("seasonRecordId").value = "";
  document.getElementById("seasonRecordFormTitle").textContent = "Add Season Record";
  document.getElementById("seasonRecordSubmitButton").textContent = "Add Season Record";
  document.getElementById("seasonRecordCancelEdit").classList.add("d-none");
  populateSeasonLabelOptions();
}

function fillSeasonRecordForm(record) {
  editingSeasonRecordId = record.RecordID;
  document.getElementById("seasonRecordId").value = record.RecordID;
  populateSeasonLabelOptions();
  const seasonSelect = document.getElementById("seasonLabel");
  if (
    record.SeasonLabel &&
    ![...seasonSelect.options].some(option => option.value === record.SeasonLabel)
  ) {
    const option = document.createElement("option");
    option.value = record.SeasonLabel;
    option.textContent = record.SeasonLabel;
    seasonSelect.appendChild(option);
  }
  seasonSelect.value = record.SeasonLabel || "";
  document.getElementById("seasonWins").value = record.Wins;
  document.getElementById("seasonLosses").value = record.Losses;
  document.getElementById("seasonRecordFormTitle").textContent = "Edit Season Record";
  document.getElementById("seasonRecordSubmitButton").textContent = "Save Changes";
  document.getElementById("seasonRecordCancelEdit").classList.remove("d-none");
  document.getElementById("admin-season-records").scrollIntoView({ behavior: "smooth" });
}

function renderSeasonRecords(records) {
  const body = document.getElementById("seasonRecordsBody");
  body.replaceChildren();

  if (!records.length) {
    const row = document.createElement("tr");
    const empty = cell("No season records yet.");
    empty.colSpan = 4;
    empty.className = "text-center text-muted py-4";
    row.appendChild(empty);
    body.appendChild(row);
    return;
  }

  records.forEach(record => {
    const row = document.createElement("tr");
    row.appendChild(cell(record.SeasonLabel));
    row.appendChild(cell(String(record.Wins)));
    row.appendChild(cell(String(record.Losses)));

    const actions = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.className = "btn btn-outline-primary btn-sm me-2";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => fillSeasonRecordForm(record));

    const deleteButton = document.createElement("button");
    deleteButton.className = "btn btn-outline-danger btn-sm";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteSeasonRecord(record));

    actions.appendChild(editButton);
    actions.appendChild(deleteButton);
    row.appendChild(actions);
    body.appendChild(row);
  });
}

async function loadSeasonRecords() {
  const errorBox = document.getElementById("seasonRecordsError");
  errorBox.classList.add("d-none");

  try {
    const data = await api("/api/admin/season-records");
    renderSeasonRecords(data.records || []);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
}

async function deleteSeasonRecord(record) {
  if (!confirm(`Delete the ${record.SeasonLabel} record? This cannot be undone.`)) {
    return;
  }

  try {
    await api(`/api/admin/season-records/${encodeURIComponent(record.RecordID)}`, {
      method: "DELETE"
    });
    if (editingSeasonRecordId === record.RecordID) {
      resetSeasonRecordForm();
    }
    loadSeasonRecords();
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(document.getElementById("seasonRecordsError"), error.message);
  }
}

document.getElementById("seasonRecordCancelEdit").addEventListener("click", resetSeasonRecordForm);

document.getElementById("seasonRecordForm").addEventListener("submit", async event => {
  event.preventDefault();

  const errorBox = document.getElementById("seasonRecordsError");
  const successBox = document.getElementById("seasonRecordsSuccess");
  errorBox.classList.add("d-none");
  successBox.classList.add("d-none");

  const payload = {
    SeasonLabel: document.getElementById("seasonLabel").value.trim(),
    Wins: document.getElementById("seasonWins").value,
    Losses: document.getElementById("seasonLosses").value
  };

  try {
    if (editingSeasonRecordId) {
      await api(`/api/admin/season-records/${encodeURIComponent(editingSeasonRecordId)}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      showSuccess(successBox, "Season record updated.");
    } else {
      await api("/api/admin/season-records", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      showSuccess(successBox, "Season record added.");
    }
    resetSeasonRecordForm();
    loadSeasonRecords();
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
});


/*STAFF*/

async function loadStaff() {
  try {
    const data = await api("/api/admin/staff");
    document.getElementById("presidentName").value = data.PresidentName || "";
    document.getElementById("coachName").value = data.CoachName || "";
    document.getElementById("captainName").value = data.CaptainName || "";
  } catch (error) {
    if (error.status === 401) {
      showLogin();
    }
  }
}


function currentStaffPayload() {
  return {
    PresidentName: document.getElementById("presidentName").value,
    CoachName: document.getElementById("coachName").value,
    CaptainName: document.getElementById("captainName").value
  };
}


async function saveStaffRole(roleLabel, errorId, successId) {
  const errorBox = document.getElementById(errorId);
  const successBox = document.getElementById(successId);
  errorBox.classList.add("d-none");
  successBox.classList.add("d-none");

  try {
    await api("/api/admin/staff", {
      method: "PUT",
      body: JSON.stringify(currentStaffPayload())
    });
    showSuccess(successBox, `${roleLabel} saved.`);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      return;
    }
    showError(errorBox, error.message);
  }
}


document.getElementById("presidentForm").addEventListener("submit", async event => {
  event.preventDefault();
  await saveStaffRole("President", "presidentError", "presidentSuccess");
});

document.getElementById("coachForm").addEventListener("submit", async event => {
  event.preventDefault();
  await saveStaffRole("Coach", "coachError", "coachSuccess");
});

document.getElementById("captainForm").addEventListener("submit", async event => {
  event.preventDefault();
  await saveStaffRole("Captain", "captainError", "captainSuccess");
});


/*SUBMISSIONS*/

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
    await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({
        Email: document.getElementById("loginEmail").value,
        Password: document.getElementById("loginPassword").value
      })
    });
    event.target.reset();
    window.location.reload();
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

syncEventTypeFields();
populateSeasonLabelOptions();

api("/api/admin/me")
  .then(data => showDashboard(data.Email))
  .catch(() => showLogin());
