/*
  MSU Rugby Club website
  Add confirmed fixtures and practices to the schedule array below.

  Front-end only: the join form opens the visitor's email app.
  It does not send or store submissions on a server.
*/

const schedule = [
  // Add confirmed events using this format:
  // {
  //   type: "game", // "game" or "practice"
  //   date: "2026-09-12",
  //   time: "1:00 PM",
  //   opponent: "Opponent Name",
  //   location: "Confirmed field / venue",
  //   status: "upcoming", // "upcoming" or "cancelled"
  //   result: ""
  // }
];

function formatDate(dateString) {
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "DATE TBA";
  return date.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric"
  });
}

function getUpcomingEvents() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return schedule
    .filter(event => event.status !== "cancelled")
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
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <h3>UPCOMING SCHEDULE TO BE ANNOUNCED</h3>
        <p>Contact MSU Rugby Club for current practice and match information.</p>
        <a href="mailto:montclairmcrugby@gmail.com">EMAIL THE CLUB →</a>
      </div>`;
    return;
  }

  const isGame = nextEvent.type === "game";
  container.innerHTML = `
    <div class="match-team">
      <span>HOME CLUB</span><h3>MSU RUGBY</h3><span>MONTCLAIR STATE</span>
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

function renderSchedule(filter = "all") {
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
    const cancelled = event.status === "cancelled";
    const label = event.type === "game" ? "MATCH" : "PRACTICE";
    const detail = cancelled ? "CANCELLED" : (event.result || event.time || "TIME TBA");
    return `
      <div class="schedule-row">
        <div class="schedule-date">${formatDate(event.date)}<span>${label}</span></div>
        <div class="schedule-opponent">
          <h3>${event.opponent || (event.type === "game" ? "Opponent TBA" : "Team Practice")}</h3>
          <span>${event.location || "Location TBA"}</span>
        </div>
        <div class="schedule-location">${event.time || ""}</div>
        <div class="schedule-result ${cancelled ? "schedule-cancelled" : ""}">${detail}</div>
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

function setupJoinForm() {
  const form = document.getElementById("joinForm");
  const confirmation = document.getElementById("joinConfirmation");
  if (!form) return;

  form.addEventListener("submit", event => {
    event.preventDefault();
    const name = document.getElementById("playerName")?.value.trim() || "";
    const email = document.getElementById("playerEmail")?.value.trim() || "";
    const position = document.getElementById("position")?.value || "Not specified";
    const experience = document.getElementById("experience")?.value || "Not specified";
    const message = document.getElementById("message")?.value.trim() || "";

    const subject = encodeURIComponent("MSU Rugby Club - New Player Interest");
    const body = encodeURIComponent(
      `Name: ${name}\nEmail: ${email}\nPosition interest: ${position}\nExperience: ${experience}\n\nMessage:\n${message}`
    );

    if (confirmation) {
      confirmation.classList.remove("d-none");
      confirmation.textContent =
        "Your email app should open with your message. Press Send in your email app to complete your inquiry.";
    }
    window.location.href =
      `mailto:montclairmcrugby@gmail.com?subject=${subject}&body=${body}`;
  });
}

function setCurrentYear() {
  const year = document.getElementById("currentYear");
  if (year) year.textContent = new Date().getFullYear();
}

document.addEventListener("DOMContentLoaded", () => {
  renderNextMatch();
  renderSchedule();
  setupScheduleFilters();
  setupJoinForm();
  setCurrentYear();
});
