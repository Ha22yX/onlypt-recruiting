(() => {
  const workspace = document.querySelector(".admin-editor-leads");
  if (!workspace) {
    return;
  }

  const leads = JSON.parse(workspace.dataset.leads || "[]");
  const leadById = new Map(leads.map((lead) => [lead.lead_id, lead]));
  const rows = Array.from(document.querySelectorAll("[data-lead-row]"));
  const detail = document.querySelector("[data-lead-detail]");
  const searchInput = document.querySelector("[data-lead-search]");
  const noResults = document.querySelector("[data-leads-no-results]");

  let activeLeadId = rows[0]?.dataset.leadRow || "";

  const escapeHtml = (value) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const displayValue = (value) => escapeHtml(String(value || "").trim() || "-");

  const statusLabel = (value) => String(value || "new").replace(/_/g, " ");

  const formatDate = (value) => {
    if (!value) {
      return "-";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString("en-US", {
      timeZone: "America/New_York",
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  };

  const formatLeadDate = (lead) => lead?.created_at_display || formatDate(lead?.created_at);

  document.querySelectorAll(".lead-date[data-created-at]").forEach((element) => {
    const value = element.getAttribute("data-created-at") || "";
    element.textContent = formatDate(value);
    element.title = value || element.textContent;
  });

  const mailtoLink = (lead) => {
    if (!lead.email) {
      return "";
    }

    const subject = encodeURIComponent("Re: onlyPT Recruiting inquiry");
    const body = encodeURIComponent(`Hi ${lead.name || ""},\n\n`);
    return `mailto:${encodeURIComponent(lead.email)}?subject=${subject}&body=${body}`;
  };

  const leadSourceMarkup = (lead) => {
    const hasSource = lead.ip || lead.user_agent || lead.referrer;
    if (!hasSource) {
      return "";
    }

    return `
      <section class="lead-detail-message lead-source-panel">
        <span>Submission source</span>
        <dl class="lead-detail-grid">
          <div><dt>IP</dt><dd>${displayValue(lead.ip)}</dd></div>
          <div><dt>Referrer</dt><dd>${displayValue(lead.referrer)}</dd></div>
          <div><dt>User agent</dt><dd>${displayValue(lead.user_agent)}</dd></div>
        </dl>
        ${
          lead.ip
            ? `<button class="lead-source-block-button" type="button" data-lead-block-ip="${escapeHtml(lead.ip)}"><i data-lucide="ban"></i> Block this IP from contact form</button>`
            : ""
        }
        <small class="lead-source-status" data-lead-source-status></small>
      </section>
    `;
  };

  const renderNotes = (lead) => {
    const notes = Array.isArray(lead.thread_notes) ? lead.thread_notes : [];
    if (!notes.length) {
      return `
        <div class="lead-thread-empty">
          <span>No conversation notes yet.</span>
        </div>
      `;
    }

    return notes
      .slice()
      .reverse()
      .map(
        (note) => `
          <article class="lead-thread-note">
            <time>${escapeHtml(formatDate(note.created_at))}</time>
            <p>${escapeHtml(note.body).replace(/\n/g, "<br>")}</p>
          </article>
        `
      )
      .join("");
  };

  const renderDetail = (lead) => {
    if (!detail || !lead) {
      return;
    }

    const replyHref = mailtoLink(lead);
    detail.innerHTML = `
      <div class="lead-detail-card" data-active-lead="${escapeHtml(lead.lead_id)}">
        <header class="lead-detail-head">
          <div>
            <span class="lead-pill lead-status-pill" data-status="${escapeHtml(lead.thread_status || "new")}">${escapeHtml(statusLabel(lead.thread_status))}</span>
            <h2>${displayValue(lead.name)}</h2>
            <p>${displayValue(lead.organization)} · ${displayValue(lead.role)}</p>
          </div>
          ${replyHref ? `<a class="lead-reply-button" href="${replyHref}"><i data-lucide="reply"></i> Reply</a>` : ""}
        </header>

        <dl class="lead-detail-grid">
          <div><dt>Received</dt><dd>${escapeHtml(formatLeadDate(lead))}</dd></div>
          <div><dt>Audience</dt><dd>${displayValue(lead.audience)}</dd></div>
          <div><dt>Email</dt><dd>${lead.email ? `<a href="mailto:${escapeHtml(lead.email)}">${escapeHtml(lead.email)}</a>` : "-"}</dd></div>
          <div><dt>Phone</dt><dd>${lead.phone ? `<a href="tel:${escapeHtml(lead.phone)}">${escapeHtml(lead.phone)}</a>` : "-"}</dd></div>
        </dl>

        <section class="lead-detail-message">
          <span>Original message</span>
          <p>${escapeHtml(lead.message || "-").replace(/\n/g, "<br>")}</p>
        </section>

        ${leadSourceMarkup(lead)}

        <form class="lead-thread-form" data-lead-thread-form>
          <label>
            <span>Status</span>
            <select name="status">
              ${["new", "contacted", "in_conversation", "follow_up", "closed"]
                .map((status) => `<option value="${status}" ${status === (lead.thread_status || "new") ? "selected" : ""}>${statusLabel(status)}</option>`)
                .join("")}
            </select>
          </label>
          <label>
            <span>Next step</span>
            <input name="next_step" type="text" value="${escapeHtml(lead.thread_next_step || "")}" placeholder="Follow up date, call outcome, hiring note...">
          </label>
          <label class="lead-note-field">
            <span>Add conversation note</span>
            <textarea name="note" rows="4" placeholder="Paste reply context, call notes, next action, or status update."></textarea>
          </label>
          <button class="button primary lead-save-button" type="submit">
            <i data-lucide="save"></i>
            Save tracking
          </button>
          <span class="lead-save-status" data-lead-save-status></span>
        </form>

        <section class="lead-thread">
          <div class="lead-thread-title">
            <span>Conversation timeline</span>
            <small>${escapeHtml(String((lead.thread_notes || []).length))} notes</small>
          </div>
          <div data-lead-thread-notes>${renderNotes(lead)}</div>
        </section>
      </div>
    `;
    window.lucide?.createIcons();
  };

  const selectLead = (leadId) => {
    const lead = leadById.get(leadId);
    if (!lead) {
      return;
    }

    activeLeadId = leadId;
    rows.forEach((row) => row.classList.toggle("is-selected", row.dataset.leadRow === leadId));
    renderDetail(lead);
  };

  const updateRowStatus = (lead) => {
    const row = document.querySelector(`[data-lead-row="${CSS.escape(lead.lead_id)}"]`);
    if (!row) {
      return;
    }

    const statusPill = row.querySelector(".lead-status-pill");
    const noteCount = row.querySelector(".lead-note-count");
    const count = Array.isArray(lead.thread_notes) ? lead.thread_notes.length : 0;
    if (statusPill) {
      statusPill.textContent = statusLabel(lead.thread_status);
      statusPill.dataset.status = lead.thread_status || "new";
    }
    if (count && !noteCount) {
      const marker = document.createElement("small");
      marker.className = "lead-note-count";
      marker.textContent = `${count} notes`;
      row.querySelector('[data-label="Name"]')?.appendChild(marker);
    } else if (noteCount) {
      noteCount.textContent = count ? `${count} notes` : "";
    }
  };

  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("a")) {
        return;
      }
      selectLead(row.dataset.leadRow);
    });
  });

  searchInput?.addEventListener("input", () => {
    const query = searchInput.value.trim().toLowerCase();
    let visibleCount = 0;
    rows.forEach((row) => {
      const isVisible = !query || row.dataset.searchText.includes(query);
      row.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    });
    if (noResults) {
      noResults.hidden = visibleCount !== 0;
    }
  });

  detail?.addEventListener("submit", async (event) => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form?.matches("[data-lead-thread-form]")) {
      return;
    }

    event.preventDefault();
    const lead = leadById.get(activeLeadId);
    const status = form.querySelector("[data-lead-save-status]");
    const button = form.querySelector(".lead-save-button");
    if (!lead) {
      return;
    }

    if (status) status.textContent = "Saving...";
    if (button) button.disabled = true;

    const payload = {
      status: form.elements.namedItem("status")?.value || "new",
      next_step: form.elements.namedItem("next_step")?.value || "",
      note: form.elements.namedItem("note")?.value || "",
    };

    try {
      const response = await fetch(`/admin/api/leads/${encodeURIComponent(activeLeadId)}/conversation`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.message || "Could not save tracking.");
      }

      lead.thread_status = result.thread.status;
      lead.thread_next_step = result.thread.next_step;
      lead.thread_updated_at = result.thread.updated_at;
      lead.thread_notes = result.thread.notes || [];
      updateRowStatus(lead);
      renderDetail(lead);
    } catch (error) {
      if (status) status.textContent = error.message || "Save failed.";
      if (button) button.disabled = false;
    }
  });

  detail?.addEventListener("click", async (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-lead-block-ip]") : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }

    const status = detail.querySelector("[data-lead-source-status]");
    button.disabled = true;
    if (status) status.textContent = "Blocking...";

    try {
      const response = await fetch("/admin/api/contact-ip-blocks", {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ip: button.dataset.leadBlockIp, blocked: true}),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.message || "Could not block this IP.");
      }
      if (status) status.textContent = "IP blocked from contact form submissions.";
      button.textContent = "IP blocked";
    } catch (error) {
      if (status) status.textContent = error.message || "Could not block this IP.";
      button.disabled = false;
    }
  });

  if (activeLeadId) {
    selectLead(activeLeadId);
  }
})();
