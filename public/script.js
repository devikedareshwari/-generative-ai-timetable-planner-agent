/**
 * SmartSched – Client-side JavaScript
 * Handles dynamic form management, API communication, table rendering,
 * day filtering, natural language rescheduling, and printing.
 */

(function () {
  if (window.__smartsched_initialized) return;
  window.__smartsched_initialized = true;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
  } else {
    initApp();
  }

  function initApp() {
    initSubjectManager();
    initFormHandler();
    initTimetablePage();
    initSavedTimetablesModal();
  }

/* ==========================================================================
   1. Dynamic Subject & Difficulty Manager (Index Form)
   ========================================================================== */
function initSubjectManager() {
  const container = document.getElementById("subjectsContainer");
  const addBtn = document.getElementById("btnAddSubject");
  if (!container || !addBtn) return;

  const defaultSubjects = [
    { name: "Mathematics", diff: "Hard" },
    { name: "Computer Science", diff: "Medium" },
    { name: "Physics", diff: "Hard" }
  ];

  // Render initial default subject inputs if container is empty
  if (container.children.length === 0) {
    defaultSubjects.forEach(s => addSubjectRow(s.name, s.diff));
  }

  addBtn.addEventListener("click", () => {
    addSubjectRow("", "Medium");
  });
}

function addSubjectRow(name = "", difficulty = "Medium") {
  const container = document.getElementById("subjectsContainer");
  if (!container) return;

  const row = document.createElement("div");
  row.className = "subject-item-row";
  row.innerHTML = `
    <input type="text" class="form-control subject-name-input" placeholder="Subject name (e.g. Chemistry)" value="${escapeHtml(name)}" required>
    <select class="form-control subject-diff-select">
      <option value="Easy" ${difficulty === "Easy" ? "selected" : ""}>Easy</option>
      <option value="Medium" ${difficulty === "Medium" ? "selected" : ""}>Medium</option>
      <option value="Hard" ${difficulty === "Hard" ? "selected" : ""}>Hard</option>
    </select>
    <button type="button" class="btn-remove-subject" title="Remove subject" aria-label="Remove">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
    </button>
  `;

  row.querySelector(".btn-remove-subject").addEventListener("click", () => {
    if (container.querySelectorAll(".subject-item-row").length > 1) {
      row.remove();
    } else {
      showFormError("You must have at least one subject.");
    }
  });

  container.appendChild(row);
}

/* ==========================================================================
   2. Student Input Form Submission & Validation
   ========================================================================== */
function initFormHandler() {
  const form = document.getElementById("timetableForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFormError();

    // Gather and validate inputs
    const name = document.getElementById("studentName")?.value.trim();
    if (!name) {
      showFormError("Please enter your name.");
      return;
    }

    const subjectRows = document.querySelectorAll(".subject-item-row");
    const subjects = [];
    const difficulties = {};

    subjectRows.forEach(row => {
      const sName = row.querySelector(".subject-name-input")?.value.trim();
      const sDiff = row.querySelector(".subject-diff-select")?.value || "Medium";
      if (sName) {
        subjects.push(sName);
        difficulties[sName] = sDiff;
      }
    });

    if (subjects.length === 0) {
      showFormError("Please enter at least one subject.");
      return;
    }

    const availableHours = parseFloat(document.getElementById("studyHours")?.value || "4");
    if (isNaN(availableHours) || availableHours < 1 || availableHours > 16) {
      showFormError("Available study hours per day must be between 1 and 16.");
      return;
    }

    const preferredStart = document.getElementById("startTime")?.value || "08:00";
    const preferredEnd = document.getElementById("endTime")?.value || "21:00";

    if (preferredStart >= preferredEnd) {
      showFormError("Preferred study start time must be earlier than the end time.");
      return;
    }

    const breakDuration = parseInt(document.getElementById("breakDuration")?.value || "15", 10);
    const examDates = document.getElementById("examDates")?.value.trim() || "";
    const instructions = document.getElementById("instructions")?.value.trim() || "";

    const payload = {
      name,
      subjects,
      difficulties,
      exam_dates: examDates,
      available_hours: availableHours,
      preferred_start: preferredStart,
      preferred_end: preferredEnd,
      break_duration: breakDuration,
      instructions
    };

    // Show loading state
    setLoadingState(true);

    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (!response.ok || result.status !== "success") {
        throw new Error(result.message || "Failed to generate timetable.");
      }

      // Save latest timetable in sessionStorage for seamless handover
      sessionStorage.setItem("smartsched_latest", JSON.stringify(result));

      // Navigate to timetable view
      const targetUrl = result.timetable_id ? `/timetable?id=${result.timetable_id}` : "/timetable";
      window.location.href = targetUrl;
    } catch (err) {
      setLoadingState(false);
      showFormError(err.message || "An unexpected error occurred while generating the timetable.");
    }
  });
}

function setLoadingState(isLoading) {
  const loadingBox = document.getElementById("loadingBox");
  const formCard = document.getElementById("formCard");
  const submitBtn = document.getElementById("btnGenerate");

  if (loadingBox && formCard) {
    if (isLoading) {
      loadingBox.style.display = "block";
      submitBtn.disabled = true;
      loadingBox.scrollIntoView({ behavior: "smooth" });
      startProgressMessageCycle();
    } else {
      loadingBox.style.display = "none";
      submitBtn.disabled = false;
    }
  }
}

let progressInterval = null;
function startProgressMessageCycle() {
  const stepText = document.getElementById("loadingSteps");
  if (!stepText) return;

  const messages = [
    "Step 1: Reading and understanding your subjects & exam priorities...",
    "Step 2: Analyzing workload and difficult topics...",
    "Step 3: Generating balanced daily study blocks with Gemini AI...",
    "Step 4: Running scheduling validator to verify breaks and avoid overlaps...",
    "Step 5: Finalizing your personalized weekly timetable..."
  ];

  let idx = 0;
  stepText.textContent = messages[0];

  clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    idx = (idx + 1) % messages.length;
    stepText.textContent = messages[idx];
  }, 2200);
}

function showFormError(msg) {
  let alertBox = document.getElementById("formAlert");
  if (!alertBox) {
    alertBox = document.createElement("div");
    alertBox.id = "formAlert";
    alertBox.className = "alert alert-danger";
    const formCard = document.getElementById("formCard");
    if (formCard) formCard.prepend(alertBox);
  }
  alertBox.textContent = msg;
  alertBox.style.display = "flex";
  alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function clearFormError() {
  const alertBox = document.getElementById("formAlert");
  if (alertBox) alertBox.style.display = "none";
}

/* ==========================================================================
   3. Timetable Display Page Logic
   ========================================================================== */
let currentTimetableState = null;

function initTimetablePage() {
  const tableContainer = document.getElementById("timetableContainer");
  if (!tableContainer) return;

  // Check if timetable data is embedded from server or in sessionStorage
  const serverDataElement = document.getElementById("serverTimetableData");
  if (serverDataElement && serverDataElement.textContent.trim()) {
    try {
      currentTimetableState = JSON.parse(serverDataElement.textContent);
    } catch (e) {
      console.warn("Could not parse server timetable data:", e);
    }
  }

  if (!currentTimetableState) {
    const cached = sessionStorage.getItem("smartsched_latest");
    if (cached) {
      try {
        currentTimetableState = JSON.parse(cached);
      } catch (e) {
        console.warn("Could not parse cached timetable data:", e);
      }
    }
  }

  if (currentTimetableState) {
    renderTimetableDetails(currentTimetableState);
  } else {
    // Show placeholder or prompt to create
    document.getElementById("noTimetableAlert").style.display = "block";
  }

  // Setup Reschedule Form & Chips
  initRescheduling();

  // Setup Print Button
  const printBtn = document.getElementById("btnPrint");
  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  // Setup Regenerate Button
  const regenBtn = document.getElementById("btnRegenerate");
  if (regenBtn) {
    regenBtn.addEventListener("click", () => {
      regenerateTimetable();
    });
  }
}

function renderTimetableDetails(data) {
  const schedule = data.schedule || [];
  const stats = data.stats || {};
  const student = data.student_data || {};
  const studentName = data.student_name || student.name || "Student";
  const genType = data.generation_type || "AI Generated";

  // Name & badge
  const nameEl = document.getElementById("displayStudentName");
  if (nameEl) nameEl.textContent = studentName;

  const badgeEl = document.getElementById("generationBadge");
  if (badgeEl) {
    badgeEl.textContent = genType;
    badgeEl.className = genType === "AI Generated" ? "badge badge-ai" : "badge badge-demo";
  }

  // Stats
  const hoursEl = document.getElementById("statTotalHours");
  if (hoursEl) hoursEl.textContent = `${stats.total_hours || 0} hrs`;

  const avgEl = document.getElementById("statAvgDaily");
  if (avgEl) avgEl.textContent = `${stats.avg_daily_hours || 0} hrs`;

  const subjectsCountEl = document.getElementById("statSubjectsCount");
  const subjectsList = student.subjects || Object.keys(stats.subject_breakdown || {});
  if (subjectsCountEl) subjectsCountEl.textContent = subjectsList.length;

  const breaksEl = document.getElementById("statBreakCount");
  if (breaksEl) breaksEl.textContent = stats.break_sessions || 0;

  // AI Message & Suggestions
  const messageEl = document.getElementById("aiExplanationText");
  if (messageEl) {
    messageEl.textContent = data.message || "Timetable balanced for optimal learning and cognitive recovery.";
  }

  const suggListEl = document.getElementById("aiSuggestionsList");
  if (suggListEl) {
    suggListEl.innerHTML = "";
    const suggestions = data.suggestions || [
      "Review difficult topics earlier in the study period.",
      "Hydrate and stretch during break intervals."
    ];
    suggestions.forEach(s => {
      const li = document.createElement("li");
      li.textContent = s;
      suggListEl.appendChild(li);
    });
  }

  // Day Filter Tabs
  renderDayTabs();

  // Render Table Rows
  renderScheduleTable(schedule, "all");
}

function renderDayTabs() {
  const container = document.getElementById("dayTabs");
  if (!container) return;

  const days = ["all", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  container.innerHTML = "";

  days.forEach(day => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `day-tab ${day === "all" ? "active" : ""}`;
    btn.textContent = day === "all" ? "All Days (Mon - Sun)" : day;
    btn.addEventListener("click", () => {
      container.querySelectorAll(".day-tab").forEach(t => t.classList.remove("active"));
      btn.classList.add("active");
      renderScheduleTable(currentTimetableState.schedule || [], day);
    });
    container.appendChild(btn);
  });
}

function renderScheduleTable(schedule, filterDay = "all") {
  const tbody = document.getElementById("timetableBody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const filtered = filterDay === "all" 
    ? schedule 
    : schedule.filter(s => s.day === filterDay);

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 2rem; color: var(--text-muted);">No study sessions scheduled for ${filterDay}.</td></tr>`;
    return;
  }

  filtered.forEach(session => {
    const tr = document.createElement("tr");
    const isBreak = (session.subject || "").toLowerCase().includes("break") ||
                    (session.activity || "").toLowerCase().includes("break") ||
                    (session.subject || "").toLowerCase().includes("rest");

    if (isBreak) {
      tr.className = "row-break";
    }

    const badgeClass = isBreak ? "badge badge-break" : "badge badge-medium";

    tr.innerHTML = `
      <td class="day-col">${escapeHtml(session.day)}</td>
      <td class="time-slot">${escapeHtml(session.start)}</td>
      <td class="time-slot">${escapeHtml(session.end)}</td>
      <td>
        <span class="${badgeClass}">${escapeHtml(session.subject)}</span>
      </td>
      <td>${escapeHtml(session.activity)}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   4. Natural Language Rescheduling
   ========================================================================== */
function initRescheduling() {
  const form = document.getElementById("rescheduleForm");
  const input = document.getElementById("rescheduleInput");
  const submitBtn = document.getElementById("btnReschedule");
  const alertBox = document.getElementById("rescheduleAlert");

  // Chips
  const chips = document.querySelectorAll(".prompt-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      if (input) {
        input.value = chip.dataset.prompt || chip.textContent.trim();
        input.focus();
      }
    });
  });

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const reqText = input.value.trim();
    if (!reqText) return;

    if (!currentTimetableState) {
      alert("No active timetable loaded to adjust.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Updating Timetable...";
    if (alertBox) alertBox.style.display = "none";

    try {
      const response = await fetch("/api/reschedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          timetable_id: currentTimetableState.id || currentTimetableState.timetable_id,
          request: reqText,
          current_schedule: currentTimetableState.schedule,
          student_data: currentTimetableState.student_data
        })
      });

      const result = await response.json();

      if (!response.ok || result.status === "error") {
        throw new Error(result.message || "Failed to update timetable.");
      }

      // Update state
      currentTimetableState.schedule = result.schedule;
      currentTimetableState.stats = result.stats;
      if (result.message) currentTimetableState.message = result.message;
      if (result.suggestions) currentTimetableState.suggestions = result.suggestions;

      // Update cache
      sessionStorage.setItem("smartsched_latest", JSON.stringify(currentTimetableState));

      // Re-render
      renderTimetableDetails(currentTimetableState);

      if (alertBox) {
        alertBox.className = "alert alert-success";
        alertBox.textContent = result.message || "Timetable adjusted successfully!";
        alertBox.style.display = "flex";
      }
      input.value = "";
    } catch (err) {
      if (alertBox) {
        alertBox.className = "alert alert-danger";
        alertBox.textContent = err.message;
        alertBox.style.display = "flex";
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Update Timetable";
    }
  });
}

/* ==========================================================================
   5. Regenerate Timetable Action
   ========================================================================== */
async function regenerateTimetable() {
  if (!currentTimetableState || !currentTimetableState.student_data) {
    window.location.href = "/";
    return;
  }

  const btn = document.getElementById("btnRegenerate");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Regenerating...";
  }

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentTimetableState.student_data)
    });

    const result = await response.json();
    if (!response.ok || result.status !== "success") {
      throw new Error(result.message || "Failed to regenerate.");
    }

    currentTimetableState = result;
    sessionStorage.setItem("smartsched_latest", JSON.stringify(result));
    renderTimetableDetails(result);
  } catch (err) {
    alert("Error regenerating timetable: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Regenerate Timetable";
    }
  }
}

/* ==========================================================================
   6. Saved Timetables Modal & Drawer
   ========================================================================== */
function initSavedTimetablesModal() {
  const modal = document.getElementById("savedModal");
  const openBtns = document.querySelectorAll(".btn-open-saved");
  const closeBtn = document.getElementById("closeSavedModal");
  const listContainer = document.getElementById("savedListContainer");

  if (!modal) return;

  openBtns.forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      modal.style.display = "flex";
      await loadSavedTimetables(listContainer);
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.style.display = "none";
    });
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.style.display = "none";
    }
  });
}

async function loadSavedTimetables(container) {
  if (!container) return;
  container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Loading saved timetables...</div>`;

  try {
    const response = await fetch("/api/timetables");
    const data = await response.json();

    if (!response.ok || data.status !== "success") {
      throw new Error(data.message || "Could not fetch saved timetables.");
    }

    const items = data.timetables || [];
    if (items.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding: 2rem; color: var(--text-muted);">
          No saved timetables found yet. Generate your first timetable!
        </div>
      `;
      return;
    }

    let html = "";
    items.forEach(item => {
      const badgeClass = item.generation_type === "AI Generated" ? "badge badge-ai" : "badge badge-demo";
      html += `
        <div class="saved-item-card">
          <div>
            <div style="font-weight: 700; font-size: 1rem; color: var(--text-main);">
              ${escapeHtml(item.student_name)}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              Subjects: ${escapeHtml(item.subjects || "None")} • ${item.total_hours || 0} hrs/week
            </div>
            <div style="font-size: 0.75rem; color: var(--text-light); margin-top: 0.2rem;">
              Saved: ${escapeHtml(item.created_at || "")}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="${badgeClass}">${escapeHtml(item.generation_type || "Timetable")}</span>
            <a href="/timetable?id=${item.id}" class="btn btn-secondary btn-sm">Open</a>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">${escapeHtml(err.message)}</div>`;
  }
}

// Utility: HTML escaping
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
})();
