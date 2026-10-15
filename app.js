// =====================================================
// CampusAlert — plain JavaScript, no frameworks.
// Data is saved in the browser with localStorage.
// =====================================================

// ---- Settings: change these in one place ----
const HELP_NUMBER = "605-691-3414";           // used for SOS calls AND live location texts
const HELP_TEL = HELP_NUMBER.replace(/-/g, "");
const MENTAL_HEALTH_URL = "https://www.sdstate.edu/wellness-center/counseling-services";
const HOLD_MS = 2000;                          // how long to hold the SOS button

const DEMO_USER = {
  name: "Krish Sapkota",
  studentId: "101234567",
  email: "krish.sapkota@jacks.sdstate.edu",
  phone: "605-555-0142",
  emergencyName: "Anita Sapkota",
  emergencyPhone: "605-555-0199",
};

// ---- Saved state ----
let state = JSON.parse(localStorage.getItem("campusalert") || "null") || {
  user: null,
  reports: [],
};
function save() { localStorage.setItem("campusalert", JSON.stringify(state)); }

// ---- Small helpers ----
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

function makeId(prefix) {
  return prefix + "-" + Math.random().toString(36).slice(2, 7).toUpperCase();
}

// Show one screen, hide the others
function go(name) {
  $$(".screen").forEach((s) => s.classList.remove("active"));
  $("#screen-" + name).classList.add("active");
  window.scrollTo(0, 0);
  if (name === "home") renderHome();
  if (name === "profile") fillProfile();
  if (name !== "calling") stopTimer();
}

// Any element with data-go="screen" navigates there
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-go]");
  if (el) go(el.dataset.go);
});

// Put the help number everywhere it's shown
$$(".help-number").forEach((el) => (el.textContent = HELP_NUMBER));
$("#call-link").href = "tel:" + HELP_TEL;

// ---- Login / signup ----
$("#btn-demo").onclick = () => { state.user = { ...DEMO_USER }; save(); go("home"); };

$("#login-form").onsubmit = (e) => {
  e.preventDefault();
  const email = $("#login-email").value;
  state.user = state.user && state.user.email === email
    ? state.user
    : { ...DEMO_USER, email };
  save();
  go("home");
};

$("#signup-form").onsubmit = (e) => {
  e.preventDefault();
  state.user = Object.fromEntries(new FormData(e.target));
  save();
  go("home");
};

// ---- Home ----
function renderHome() {
  $("#home-name").textContent = state.user.name.split(" ")[0];
  $("#avatar").textContent = state.user.name[0];
  const list = $("#report-list");
  list.innerHTML = state.reports.length
    ? ""
    : '<li class="muted">No reports yet.</li>';
  state.reports.slice(0, 5).forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `<span><b>${r.type}</b><br><span class="small">${r.location}</span></span><span class="small">${r.id}</span>`;
    list.appendChild(li);
  });
}

// ---- SOS: press and hold for 2 seconds ----
const sosBtn = $("#sos-btn");
let holdTimer = null;

function startHold(e) {
  e.preventDefault();
  sosBtn.classList.add("holding");
  holdTimer = setTimeout(() => {
    sosBtn.classList.remove("holding");
    startCall();
  }, HOLD_MS);
}
function cancelHold() {
  clearTimeout(holdTimer);
  sosBtn.classList.remove("holding");
}
sosBtn.addEventListener("pointerdown", startHold);
["pointerup", "pointerleave", "pointercancel"].forEach((ev) => sosBtn.addEventListener(ev, cancelHold));
sosBtn.addEventListener("click", () => toast("Keep holding the SOS button for 2 seconds"));

// ---- Calling screen with timer ----
let timerInterval = null;
function startCall() {
  go("calling");
  let seconds = 0;
  $("#call-timer").textContent = "00:00";
  timerInterval = setInterval(() => {
    seconds++;
    const m = String(Math.floor(seconds / 60)).padStart(2, "0");
    const s = String(seconds % 60).padStart(2, "0");
    $("#call-timer").textContent = `${m}:${s}`;
  }, 1000);
  // Opens the phone's dialer (works on mobile; on laptops it may ask for an app)
  window.location.href = "tel:" + HELP_TEL;
}
function stopTimer() { clearInterval(timerInterval); }

// ---- GPS helper ----
// Returns { lat, lng } or null if the user blocks location.
function getGPS() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude.toFixed(5), lng: p.coords.longitude.toFixed(5) }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  });
}

$$(".use-gps").forEach((btn) => {
  btn.onclick = async () => {
    btn.textContent = "Locating…";
    const pos = await getGPS();
    const input = btn.parentElement.querySelector(".loc-input");
    input.value = pos ? `GPS ${pos.lat}, ${pos.lng}` : "SDSU Campus, Brookings SD";
    btn.textContent = "📍 Use my GPS";
    if (!pos) toast("Location blocked — using campus default");
  };
});

// ---- Emergency quick report ----
$("#emergency-form").onsubmit = (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const report = addReport("Emergency", data.location, { Description: data.description });
  e.target.reset();
  showDone("Report Sent", "Help is on the way. Stay where you are if safe.", report);
};

// ---- Non-emergency ----
let currentCategory = "";
$$(".cat[data-cat]").forEach((btn) => {
  btn.onclick = () => {
    currentCategory = btn.dataset.cat;
    $("#cat-tag").textContent = currentCategory;
    go("nonemergency-form");
  };
});

// Mental Health opens SDSU Counseling Services in a new tab
$("#btn-mental").onclick = () => window.open(MENTAL_HEALTH_URL, "_blank");

$("#nonemergency-form").onsubmit = (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const report = addReport(currentCategory, data.location, { "People involved": data.people });
  e.target.reset();
  showDone("Report Submitted", "Save your reference ID to follow up.", report);
};

function addReport(type, location, extra) {
  const report = {
    id: makeId(type === "Emergency" ? "EMG" : "NEM"),
    type, location, extra,
    name: state.user.name,
    studentId: state.user.studentId,
    time: new Date().toLocaleString(),
  };
  state.reports.unshift(report);
  save();
  return report;
}

function showDone(title, sub, report) {
  $("#done-title").textContent = title;
  $("#done-sub").textContent = sub;
  const rows = { Reference: report.id, Type: report.type, Location: report.location, ...report.extra, Time: report.time };
  $("#done-rows").innerHTML = Object.entries(rows)
    .map(([k, v]) => `<div><span>${k}</span><span>${v}</span></div>`).join("");
  go("done");
}

// ---- Live location: gets real GPS, then opens a text message ----
$("#btn-location").onclick = async () => {
  go("location");
  $("#loc-status").textContent = "Finding your location…";
  const sms = $("#sms-link");
  const pos = await getGPS();
  const where = pos
    ? `https://maps.google.com/?q=${pos.lat},${pos.lng}`
    : "SDSU Campus, Brookings SD (GPS unavailable)";
  $("#loc-status").innerHTML = pos ? `<b>${pos.lat}, ${pos.lng}</b><br><span class="small">Accurate GPS position</span>` : where;
  const body = `CampusAlert: ${state.user.name} (${state.user.studentId}) shared their live location: ${where}`;
  // "?&body=" works on both iPhone and Android
  sms.href = `sms:${HELP_TEL}?&body=${encodeURIComponent(body)}`;
  sms.onclick = () => setTimeout(() => {
    $("#done-title").textContent = "Location Sent";
    $("#done-sub").textContent = "Your location was shared by text.";
    $("#done-rows").innerHTML = `<div><span>To</span><span>${HELP_NUMBER}</span></div><div><span>Location</span><span>${pos ? pos.lat + ", " + pos.lng : "Campus default"}</span></div>`;
    go("done");
  }, 600);
};

// ---- Profile ----
function fillProfile() {
  const f = $("#profile-form");
  Object.entries(state.user).forEach(([k, v]) => { if (f[k]) f[k].value = v; });
}
$("#profile-form").onsubmit = (e) => {
  e.preventDefault();
  state.user = Object.fromEntries(new FormData(e.target));
  save();
  toast("Profile saved");
  go("home");
};
$("#btn-signout").onclick = () => { state.user = null; save(); go("login"); };

// ---- Start ----
go(state.user ? "home" : "login");
