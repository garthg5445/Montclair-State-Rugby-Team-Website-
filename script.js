/*CURRENT YEAR*/

const currentYear = document.getElementById("currentYear");

if (currentYear) {
  currentYear.textContent = new Date().getFullYear();
}


/*SCHEDULE DATA ---
This lines of code is what allows an user to change the schedule
*/

const schedule = [

  {
    type: "practice",
    title: "Team Practice",
    date: "2026-10-14",
    time: "6:00 PM - 8:00 PM",
    location: "Main Athletic Field",
    status: "scheduled",
    result: ""
  },

  {
    type: "game",
    title: "Home Game vs. Rivals",
    date: "2026-10-17",
    time: "1:00 PM",
    location: "Main Athletic Field",
    status: "scheduled",
    result: ""
  },

  {
    type: "practice",
    title: "Team Practice",
    date: "2026-10-20",
    time: "6:00 PM - 8:00 PM",
    location: "Main Athletic Field",
    status: "scheduled",
    result: ""
  },

  {
    type: "game",
    title: "Away Game",
    date: "2026-10-24",
    time: "3:00 PM",
    location: "Riverside Sports Complex",
    status: "scheduled",
    result: ""
  },

  {
    type: "practice",
    title: "Team Practice",
    date: "2026-10-27",
    time: "6:00 PM - 8:00 PM",
    location: "Main Athletic Field",
    status: "scheduled",
    result: ""
  }

];


/*DATE FORMATTER */

function formatDate(dateString) {

  const date = new Date(dateString + "T12:00:00");

  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric"
  });
}


/*FIND NEXT EVENT*/

function getNextEvent() {

  const today = new Date();

  today.setHours(0, 0, 0, 0);

  const upcomingEvents = schedule
    .filter(event => {

      const eventDate = new Date(
        event.date + "T12:00:00"
      );

      return (
        eventDate >= today &&
        event.status !== "cancelled"
      );

    })
    .sort((a, b) => {

      return new Date(a.date) - new Date(b.date);

    });

  return upcomingEvents.length
    ? upcomingEvents[0]
    : null;
}


/*DISPLAY NEXT EVENT*/

function renderNextEvent() {

  const container =
    document.getElementById("nextEvent");

  if (!container) {
    return;
  }

  const event = getNextEvent();

  if (!event) {

    container.innerHTML = `
      <h3>No Upcoming Events</h3>
      <p class="mb-0">
        Check back soon for the next team event.
      </p>
    `;

    return;
  }


  const eventLabel =
    event.type === "game"
      ? "🏆 GAME"
      : "🏃 PRACTICE";


  container.innerHTML = `

    <div class="mb-2">
      ${eventLabel}
    </div>

    <h3>
      ${event.title}
    </h3>

    <div class="next-event-date">
      ${formatDate(event.date)}
    </div>

    <p class="mb-1">
      <strong>${event.time}</strong>
    </p>

    <p class="next-event-location mb-0">
      ${event.location}
    </p>

  `;
}


/*DISPLAY SCHEDULE */

function renderSchedule(filter = "all") {

  const container =
    document.getElementById("scheduleList");

  if (!container) {
    return;
  }


  let events = [...schedule];


  if (filter !== "all") {

    events = events.filter(
      event => event.type === filter
    );

  }


  events.sort((a, b) => {

    return new Date(a.date) - new Date(b.date);

  });


  if (events.length === 0) {

    container.innerHTML = `

      <div class="col-12 text-center">

        <div class="alert alert-info">
          No events found.
        </div>

      </div>

    `;

    return;
  }


  container.innerHTML = events.map(event => {

    const isCancelled =
      event.status === "cancelled";


    const typeLabel =
      event.type === "game"
        ? "Game"
        : "Practice";


    const typeBadge =
      event.type === "game"
        ? "bg-primary"
        : "bg-success";


    return `

      <div class="col-md-6 col-lg-4">

        <div class="schedule-card ${
          isCancelled ? "cancelled" : ""
        }">

          <div class="schedule-type">

            <span class="badge ${typeBadge}">
              ${typeLabel}
            </span>

          </div>


          <h4>
            ${event.title}
          </h4>


          <div class="schedule-date mb-2">
            ${formatDate(event.date)}
          </div>


          <p class="mb-1">
            <strong>Time:</strong>
            ${event.time}
          </p>


          <p class="schedule-location mb-3">
            <strong>Location:</strong>
            ${event.location}
          </p>


          ${
            isCancelled

              ? `

                <div class="alert alert-danger mb-0">

                  <strong>
                    CANCELLED
                  </strong>

                  <br>

                  This event has been cancelled.

                </div>

              `

              : event.result

                ? `

                  <p class="result mb-0">
                    Result: ${event.result}
                  </p>

                `

                : ""

          }

        </div>

      </div>

    `;

  }).join("");

}


/*SCHEDULE FILTERS*/

const filterButtons =
  document.querySelectorAll(".schedule-filter");


filterButtons.forEach(button => {

  button.addEventListener("click", () => {

    filterButtons.forEach(btn => {

      btn.classList.remove("active");

    });


    button.classList.add("active");


    const filter =
      button.dataset.filter;


    renderSchedule(filter);

  });

});


/*JOIN FORM*/

const joinForm =
  document.getElementById("joinForm");


if (joinForm) {

  joinForm.addEventListener("submit", function(event) {

    event.preventDefault();


    const name =
      document.getElementById("playerName").value;


    const email =
      document.getElementById("playerEmail").value;


    const position =
      document.getElementById("position").value;


    const experience =
      document.getElementById("experience").value;


    const message =
      document.getElementById("message").value;


    /*The form only displays a confirmation due to the backend not being integrated yet*/

    console.log("New player inquiry:", {
      name,
      email,
      position,
      experience,
      message
    });


    const confirmation =
      document.getElementById("joinConfirmation");


    confirmation.classList.remove("d-none");


    joinForm.reset();


    confirmation.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });

  });

}


/*INITIALIZE WEBSITE*/

document.addEventListener("DOMContentLoaded", () => {

  renderNextEvent();

  renderSchedule("all");

});