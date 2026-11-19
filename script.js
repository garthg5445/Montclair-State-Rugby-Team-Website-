/*
  MSU Rugby Club website

  Schedule and staff load from the API.
  The join form saves the submission for admins, then opens the visitor's email app.
*/

let schedule = [];
let currentScheduleFilter = "all";

function formatDate(dateString) {
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "DATE TBA";
  return date.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric"
  });
}

function formatTime(timeString) {
  if (!timeString) return "TIME TBA";
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

function mapApiEvent(event) {
  return {
    id: event.EventID,
    type: event.EventType,
    date: event.EventDate,
    time: formatTime(event.EventTime),
    opponent: event.Opponent,
    homeAway: event.HomeAway,
    location: event.Location,
    status: event.Status,
    result: ""
  };
}

function getUpcomingEvents() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return schedule
    .filter(event => event.status === "scheduled")
    .filter(event => {
      const eventDate = new Date(`${event.date}T12:00:00`);
      return !Number.isNaN(eventDate.getTime()) && eventDate >= today;
    })
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}

function renderNextMatch() {
  const container = document.getElementById("nextMatch");
  if (!container) return;
  const nextEvent = getUpcomingEvents()[0];

  if (!nextEvent) {
    container.className = "";
    container.innerHTML = `
      <div class="empty-state">
        <h3>UPCOMING SCHEDULE TO BE ANNOUNCED</h3>
        <p>Contact MSU Rugby Club for current practice and match information.</p>
        <a href="mailto:montclairmcrugby@gmail.com">EMAIL THE CLUB →</a>
      </div>`;
    return;
  }

  const isGame = nextEvent.type === "game";
  const homeAwayLabel = nextEvent.homeAway === "away" ? "AWAY" : "HOME";
  container.className = "match-card";
  container.innerHTML = `
    <div class="match-team">
      <span>${isGame ? homeAwayLabel + " CLUB" : "HOME CLUB"}</span>
      <h3>MSU RUGBY</h3>
      <span>MONTCLAIR STATE</span>
    </div>
    <div class="match-vs">
      <strong>${isGame ? "VS" : "TRAINING"}</strong>
      <span>${formatDate(nextEvent.date)}</span>
      <span>${nextEvent.time || "TIME TBA"}</span>
    </div>
    <div class="match-team">
      <span>${isGame ? "OPPONENT" : "SESSION"}</span>
      <h3>${nextEvent.opponent || (isGame ? "OPPONENT TBA" : "TEAM PRACTICE")}</h3>
      <span>${nextEvent.location || "LOCATION TBA"}</span>
    </div>`;
}

function statusLabel(status) {
  if (status === "cancelled") return "CANCELLED";
  if (status === "postponed") return "POSTPONED";
  return null;
}

function renderSchedule(filter = currentScheduleFilter) {
  currentScheduleFilter = filter;
  const container = document.getElementById("scheduleList");
  if (!container) return;

  const events = schedule
    .filter(event => filter === "all" || event.type === filter)
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  if (events.length === 0) {
    const label = filter === "all" ? "EVENTS" : `${filter.toUpperCase()}S`;
    container.innerHTML = `
      <div class="empty-state">
        <h3>NO ${label} POSTED YET</h3>
        <p>Confirmed matches and practices will be added here. Contact the club for the latest information.</p>
        <a href="mailto:montclairmcrugby@gmail.com">montclairmcrugby@gmail.com</a>
      </div>`;
    return;
  }

  container.innerHTML = events.map(event => {
    const specialStatus = statusLabel(event.status);
    const label = event.type === "game" ? "MATCH" : "PRACTICE";
    const homeAway =
      event.type === "game"
        ? (event.homeAway === "away" ? "Away" : "Home")
        : "";
    const title = event.type === "game"
      ? `${homeAway}: vs ${event.opponent || "Opponent TBA"}`
      : (event.opponent || "Team Practice");
    const detail = specialStatus || event.time || "TIME TBA";
    return `
      <div class="schedule-row">
        <div class="schedule-date">${formatDate(event.date)}<span>${label}</span></div>
        <div class="schedule-opponent">
          <h3>${title}</h3>
          <span>${event.location || "Location TBA"}</span>
        </div>
        <div class="schedule-location">${event.time || ""}</div>
        <div class="schedule-result ${specialStatus ? "schedule-cancelled" : ""}">${detail}</div>
      </div>`;
  }).join("");
}

function setupScheduleFilters() {
  const buttons = document.querySelectorAll(".schedule-filter");
  buttons.forEach(button => {
    button.addEventListener("click", () => {
      buttons.forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      renderSchedule(button.dataset.filter || "all");
    });
  });
}

async function loadSchedule() {
  try {
    const response = await fetch("/api/events");
    if (!response.ok) throw new Error("Failed to load schedule");
    const data = await response.json();
    schedule = (data.events || []).map(mapApiEvent);
  } catch (error) {
    schedule = [];
  }
  renderNextMatch();
  renderSchedule();
}

function renderStaff(staff) {
  const container = document.getElementById("staffList");
  if (!container) return;

  const roles = [
    { key: "PresidentName", label: "CLUB PRESIDENT" },
    { key: "CoachName", label: "HEAD COACH" },
    { key: "CaptainName", label: "TEAM CAPTAIN" }
  ];

  container.innerHTML = roles.map(role => {
    const name = (staff?.[role.key] || "").trim();
    return `
      <div class="col-md-4">
        <div class="coach-card">
          <div class="coach-photo">MSU</div>
          <div>
            <span>${role.label}</span>
            <h3>${name || "TO BE ANNOUNCED"}</h3>
            <p>${name ? "Managed from the club admin panel." : "Leadership details will appear here once added."}</p>
          </div>
        </div>
      </div>`;
  }).join("");
}

async function loadStaff() {
  try {
    const response = await fetch("/api/staff");
    if (!response.ok) throw new Error("Failed to load staff");
    renderStaff(await response.json());
  } catch (error) {
    renderStaff({});
  }
}

function renderSeasonRecordBand(container, kicker, title, wins, losses) {
  if (!container) return;
  container.innerHTML = `
    <div class="season-record-copy">
      <span class="section-kicker">${kicker}</span>
      <h3>${title}</h3>
    </div>
    <div class="season-record-score">
      <strong>${wins}-${losses}</strong>
      <span>WINS · LOSSES</span>
    </div>`;
}

async function loadSeasonRecords() {
  const currentBox = document.getElementById("currentSeasonRecord");
  const historyBox = document.getElementById("allTimeRecord");

  try {
    const response = await fetch("/api/season-records");
    if (!response.ok) throw new Error("Failed to load season records");
    const data = await response.json();
    const current = data.currentRecord || { SeasonLabel: data.currentSeason || "", Wins: 0, Losses: 0 };
    const allTime = data.allTime || { Wins: 0, Losses: 0 };

    renderSeasonRecordBand(
      currentBox,
      "CURRENT SEASON",
      `${current.SeasonLabel || "SEASON"} RECORD`,
      current.Wins || 0,
      current.Losses || 0
    );
    renderSeasonRecordBand(
      historyBox,
      "ALL-TIME",
      "CLUB RECORD",
      allTime.Wins || 0,
      allTime.Losses || 0
    );
  } catch (error) {
    renderSeasonRecordBand(currentBox, "CURRENT SEASON", "SEASON RECORD", 0, 0);
    renderSeasonRecordBand(historyBox, "ALL-TIME", "CLUB RECORD", 0, 0);
  }
}

function setupMessageCounter() {
  const message = document.getElementById("message");
  const counter = document.getElementById("messageCount");
  const warning = document.getElementById("messageLimitWarning");
  if (!message || !counter) return;

  const maxLength = 300;

  const updateCounter = () => {
    const length = message.value.length;
    counter.textContent = `${length} / ${maxLength}`;

    if (warning) {
      if (length >= maxLength) {
        warning.classList.remove("d-none");
      } else {
        warning.classList.add("d-none");
      }
    }
  };

  message.addEventListener("input", updateCounter);
  updateCounter();
}

function setupJoinForm() {
  const form = document.getElementById("joinForm");
  const confirmation = document.getElementById("joinConfirmation");
  const errorBox = document.getElementById("joinError");
  if (!form) return;

  form.addEventListener("submit", async event => {
    event.preventDefault();

    const name = document.getElementById("playerName")?.value.trim() || "";
    const email = document.getElementById("playerEmail")?.value.trim() || "";
    const position = document.getElementById("position")?.value || "";
    const experience = document.getElementById("experience")?.value || "";
    const message = document.getElementById("message")?.value.trim() || "";
    const submitButton = form.querySelector("button[type='submit']");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    if (confirmation) confirmation.classList.add("d-none");
    if (errorBox) errorBox.classList.add("d-none");
    if (submitButton) submitButton.disabled = true;

    try {
      const headers = { "Content-Type": "application/json" };
      if (csrfToken) {
        headers["X-CSRF-Token"] = csrfToken;
      }

      const response = await fetch("/api/recruitment", {
        method: "POST",
        credentials: "same-origin",
        headers,
        body: JSON.stringify({
          FullName: name,
          Email: email,
          Position: position,
          ExperienceLevel: experience,
          Comments: message
        })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Something went wrong. Please try again.");
      }

      if (confirmation) {
        confirmation.classList.remove("d-none");
        confirmation.textContent =
          "Submitted! Your email app should open with your message. Press send in your email app to complete your inquiry.";
      }

      const subject = encodeURIComponent("MSU Rugby Club - New Player Interest");
      const body = encodeURIComponent(
        `Name: ${name}\nEmail: ${email}\nPosition interest: ${position}\nExperience: ${experience}\n\nMessage:\n${message}`
      );

      window.location.href =
        `mailto:montclairmcrugby@gmail.com?subject=${subject}&body=${body}`;
    } catch (error) {
      if (errorBox) {
        errorBox.textContent =
          error instanceof TypeError
            ? "Could not reach the server. Please try again later."
            : error.message;
        errorBox.classList.remove("d-none");
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function setCurrentYear() {
  const year = document.getElementById("currentYear");
  if (year) year.textContent = new Date().getFullYear();
}

document.addEventListener("DOMContentLoaded", () => {
  setupScheduleFilters();
  setupMessageCounter();
  setupJoinForm();
  setCurrentYear();
  loadSchedule();
  loadStaff();
  loadSeasonRecords();
});
