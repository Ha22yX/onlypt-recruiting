(() => {
  const editor = document.querySelector(".admin-editor");
  if (!editor) {
    return;
  }

  const pages = JSON.parse(editor.dataset.editorPages || "{}");
  const form = document.querySelector("#admin-content-form");
  const fieldList = document.querySelector("[data-admin-field-list]");
  const frame = document.querySelector("#admin-preview-frame");
  const status = document.querySelector("#admin-save-status");
  const pageTitle = document.querySelector("[data-admin-page-title]");
  const previewTitle = document.querySelector("[data-admin-preview-title]");
  const fieldPanelTitle = document.querySelector("[data-admin-field-panel-title]");
  const previewOpen = document.querySelector("[data-admin-preview-open]");
  const pageButtons = Array.from(document.querySelectorAll("[data-page-switch]"));
  const saveButton = document.querySelector("[data-save-button]");
  const saveLabel = document.querySelector("[data-save-label]");
  const saveIcon = document.querySelector("[data-save-icon]");
  const backgroundUploadUrl = editor.dataset.backgroundUploadUrl;
  const backgroundDeleteUrl = editor.dataset.backgroundDeleteUrl;
  const backgroundConfigUrl = editor.dataset.backgroundConfigUrl;
  const faviconUploadUrl = editor.dataset.faviconUploadUrl;
  const faviconDeleteUrl = editor.dataset.faviconDeleteUrl;
  const trafficReportTestUrl = editor.dataset.trafficReportTestUrl;

  let pageKey = editor.dataset.adminPage;
  let activeInput = null;
  let currentInputs = [];
  let saveFeedbackTimer = null;
  let directSaveTimer = null;
  let lastPreviewBackgroundSignature = "";
  const firstBlockHeightKey = "layout.first_section_top";

  const normalizeFirstBlockHeight = (value) => {
    const parsed = Number.parseInt(String(value || "22"), 10);
    if (Number.isNaN(parsed)) {
      return 22;
    }
    return Math.max(0, Math.min(120, parsed));
  };

  const setStatus = (message, state = "") => {
    if (!status) {
      return;
    }
    status.textContent = message;
    status.classList.toggle("is-success", state === "success");
    status.classList.toggle("is-error", state === "error");
  };

  const setSaveButtonState = (state, label) => {
    if (saveFeedbackTimer) {
      window.clearTimeout(saveFeedbackTimer);
      saveFeedbackTimer = null;
    }

    if (!saveButton) {
      return;
    }

    saveButton.classList.toggle("is-saving", state === "saving");
    saveButton.classList.toggle("is-saved", state === "saved");
    saveButton.classList.toggle("is-error", state === "error");
    saveButton.disabled = state === "saving";
    saveButton.setAttribute("aria-busy", String(state === "saving"));

    if (saveLabel) {
      saveLabel.textContent = label;
    }

    if (saveIcon) {
      saveIcon.setAttribute(
        "data-lucide",
        state === "saved" ? "check" : state === "error" ? "circle-alert" : "save"
      );
      window.lucide?.createIcons();
    }
  };

  const resetSaveButtonSoon = () => {
    saveFeedbackTimer = window.setTimeout(() => {
      setSaveButtonState("idle", "Save changes");
    }, 1800);
  };

  const escapeHtml = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const selectorValue = (value) => String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');

  const parseImageList = (value) => {
    if (!value) {
      return [];
    }

    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch {
      return String(value)
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }

    return [];
  };

  const firstImageName = (value) => parseImageList(value)[0] || String(value || "").trim();

  const backgroundUrl = (filename) => `/uploads/backgrounds/${encodeURIComponent(filename)}`;
  const faviconUrl = (filename) => `/uploads/favicons/${encodeURIComponent(filename)}`;
  let backgroundThumbObserver = null;

  const hydrateBackgroundThumb = (img) => {
    if (!img || img.dataset.thumbLoaded === "true") {
      return;
    }

    const src = img.dataset.src;
    if (!src) {
      return;
    }

    img.dataset.thumbLoaded = "true";
    img.src = src;
  };

  const observeBackgroundThumbs = (preview) => {
    if (!preview) {
      return;
    }

    const images = Array.from(preview.querySelectorAll("img[data-src]"));
    if (!images.length) {
      return;
    }

    if (!("IntersectionObserver" in window)) {
      images.forEach((img, index) => {
        window.setTimeout(() => hydrateBackgroundThumb(img), index * 90);
      });
      return;
    }

    if (!backgroundThumbObserver) {
      backgroundThumbObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) {
              return;
            }
            backgroundThumbObserver.unobserve(entry.target);
            hydrateBackgroundThumb(entry.target);
          });
        },
        {
          root: null,
          rootMargin: "180px 0px",
          threshold: 0.01,
        }
      );
    }

    images.forEach((img) => backgroundThumbObserver.observe(img));
  };

  const renderBackgroundThumbs = (preview, imageName) => {
    if (!preview) {
      return;
    }

    if (backgroundThumbObserver) {
      preview.querySelectorAll("img[data-src]").forEach((img) => backgroundThumbObserver.unobserve(img));
    }

    if (!imageName) {
      preview.classList.remove("has-image");
      preview.innerHTML = `<em>No background image uploaded</em>`;
      return;
    }

    preview.classList.add("has-image");
    preview.innerHTML = `
      <span class="admin-background-thumb" data-background-thumb="${escapeHtml(imageName)}">
        <img data-src="${escapeHtml(backgroundUrl(imageName))}" alt="" loading="lazy" decoding="async" fetchpriority="low">
        <button type="button" data-remove-background="${escapeHtml(imageName)}">Remove</button>
      </span>
    `;
    observeBackgroundThumbs(preview);
  };

  const setBackgroundState = (imageName, enabled = pages.general?.values?.["background.enabled"] || "off") => {
    const nextValue = firstImageName(imageName);
    pages.general.values["background.image"] = nextValue;
    pages.general.values["background.enabled"] = enabled;

    const hiddenInput = fieldList?.querySelector('[data-editor-input][data-cms-key="background.image"]');
    const toggleInput = fieldList?.querySelector('[data-editor-input][data-cms-key="background.enabled"]');
    const toggleLabel = toggleInput?.closest(".admin-toggle-control")?.querySelector("strong");
    const preview = fieldList?.querySelector("[data-image-preview-list]");

    if (hiddenInput) {
      hiddenInput.value = nextValue;
    }
    if (toggleInput) {
      toggleInput.checked = enabled === "on";
    }
    if (toggleLabel) {
      toggleLabel.textContent = enabled === "on" ? "Enabled" : "Disabled";
    }
    renderBackgroundThumbs(preview, nextValue);
    applyBackgroundToPreview();
  };

  const removeBackgroundImage = async (button) => {
    const imageName = button.dataset.removeBackground;
    const row = button.closest("[data-field-card]");
    const uploadStatus = row?.querySelector("[data-upload-status]");
    if (!imageName || !backgroundDeleteUrl || button.disabled) {
      return;
    }

    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (uploadStatus) uploadStatus.textContent = "Removing image...";
    setStatus("Removing background image...", "");

    try {
      const response = await fetch(backgroundDeleteUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: imageName }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Could not remove image.");
      }

      setBackgroundState(payload.backgroundImage || "", payload.backgroundEnabled || pages.general.values["background.enabled"]);
      if (uploadStatus) uploadStatus.textContent = "Image removed and saved.";
      setStatus("Background image removed and saved.", "success");
    } catch (error) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      if (uploadStatus) uploadStatus.textContent = error.message || "Remove failed.";
      setStatus(error.message || "Could not remove image.", "error");
    }
  };

  const saveBackgroundEnabled = async (enabled) => {
    if (!backgroundConfigUrl) {
      return;
    }

    const image = firstImageName(pages.general?.values?.["background.image"] || "");
    try {
      const response = await fetch(backgroundConfigUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ enabled, image }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Could not save background setting.");
      }
      setBackgroundState(payload.backgroundImage || image, payload.backgroundEnabled || enabled);
      setStatus("Background setting saved.", "success");
    } catch (error) {
      setStatus(error.message || "Could not save background setting.", "error");
    }
  };

  const renderFaviconThumb = (preview, imageName) => {
    if (!preview) {
      return;
    }

    if (!imageName) {
      preview.classList.remove("has-image");
      preview.innerHTML = `<em>No page tab icon uploaded</em>`;
      return;
    }

    preview.classList.add("has-image");
    preview.innerHTML = `
      <span class="admin-favicon-thumb" data-favicon-thumb="${escapeHtml(imageName)}">
        <img src="${escapeHtml(faviconUrl(imageName))}" alt="" loading="lazy" decoding="async">
        <button type="button" data-remove-favicon="${escapeHtml(imageName)}">Remove</button>
      </span>
    `;
  };

  const applyFaviconToPreview = () => {
    const doc = previewDocument();
    if (!doc) {
      return;
    }

    const imageName = firstImageName(pages.general?.values?.["site.favicon"] || "");
    let link = doc.querySelector('link[rel~="icon"]');
    if (!imageName) {
      link?.remove();
      return;
    }

    if (!link) {
      link = doc.createElement("link");
      link.rel = "icon";
      doc.head.appendChild(link);
    }
    link.href = faviconUrl(imageName);
  };

  const setFaviconState = (imageName) => {
    const nextValue = firstImageName(imageName);
    pages.general.values["site.favicon"] = nextValue;

    const hiddenInput = fieldList?.querySelector('[data-editor-input][data-cms-key="site.favicon"]');
    const preview = fieldList?.querySelector('[data-favicon-preview-list]');

    if (hiddenInput) {
      hiddenInput.value = nextValue;
    }
    renderFaviconThumb(preview, nextValue);
    applyFaviconToPreview();
  };

  const removeFavicon = async (button) => {
    const imageName = button.dataset.removeFavicon;
    const row = button.closest("[data-field-card]");
    const uploadStatus = row?.querySelector("[data-upload-status]");
    if (!imageName || !faviconDeleteUrl || button.disabled) {
      return;
    }

    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (uploadStatus) uploadStatus.textContent = "Removing icon...";
    setStatus("Removing page tab icon...", "");

    try {
      const response = await fetch(faviconDeleteUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: imageName }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Could not remove icon.");
      }

      setFaviconState(payload.favicon || "");
      if (uploadStatus) uploadStatus.textContent = "Icon removed and saved.";
      setStatus("Page tab icon removed and saved.", "success");
    } catch (error) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      if (uploadStatus) uploadStatus.textContent = error.message || "Remove failed.";
      setStatus(error.message || "Could not remove icon.", "error");
    }
  };

  const previewDocument = () => {
    try {
      return frame?.contentDocument || frame?.contentWindow?.document || null;
    } catch {
      return null;
    }
  };

  const targetSelector = (key) =>
    `[data-cms-page="${selectorValue(pageKey)}"][data-cms-key="${selectorValue(key)}"]`;

  const getPreviewTargets = (key) => {
    const doc = previewDocument();
    if (!doc) {
      return [];
    }
    return Array.from(doc.querySelectorAll(targetSelector(key)));
  };

  const getInputValue = (input) => {
    if (input?.type === "checkbox") {
      return input.checked ? "on" : "off";
    }
    return input?.value ?? "";
  };

  const displayTarget = (target) => {
    if (!target) {
      return null;
    }

    if (target.tagName === "OPTION") {
      return target.closest("select") || target;
    }

    return target;
  };

  const applyValueToTarget = (target, value) => {
    const attributeName = target.dataset.cmsAttribute;
    if (attributeName) {
      target.setAttribute(attributeName, value);
      return;
    }

    if (target.matches("input, textarea, select")) {
      target.value = value;
      return;
    }

    target.textContent = value;
  };

  const applyBackgroundToPreview = () => {
    const doc = previewDocument();
    if (!doc) {
      return;
    }

    const enabled = pages.general?.values?.["background.enabled"] === "on";
    const imageName = firstImageName(pages.general?.values?.["background.image"] || "");
    const imageUrl = imageName ? backgroundUrl(imageName) : "";
    const shouldShow = Boolean(enabled && imageUrl);
    const signature = JSON.stringify({ enabled: shouldShow, imageUrl });

    doc.body.classList.toggle("site-background-enabled", shouldShow);
    if (shouldShow) {
      doc.body.style.setProperty("--site-bg-image", `url("${imageUrl}")`);
    } else {
      doc.body.style.removeProperty("--site-bg-image");
    }

    if (typeof doc.defaultView?.onlyPTBackgroundSlideshow?.refresh === "function") {
      doc.defaultView.onlyPTBackgroundSlideshow.refresh();
    }
    lastPreviewBackgroundSignature = signature;
  };

  const applyFirstBlockHeightToPreview = (value = pages.general?.values?.[firstBlockHeightKey] || "86") => {
    const doc = previewDocument();
    if (!doc) {
      return;
    }
    const nextValue = `${normalizeFirstBlockHeight(value)}px`;
    doc.documentElement.style.setProperty("--first-block-start", nextValue);
    doc.body?.style.setProperty("--first-block-start", nextValue);
  };

  const activatePracticePreviewCard = (fieldKey) => {
    if (pageKey !== "employers") {
      return false;
    }

    const match = String(fieldKey).match(/^practice\.node(\d+)\.(title|detail)$/);
    if (!match) {
      return false;
    }

    const doc = previewDocument();
    const cardIndex = Number(match[1]) - 1;
    if (!doc || Number.isNaN(cardIndex)) {
      return false;
    }

    const previewWindow = doc.defaultView;
    if (typeof previewWindow?.onlyPTPracticeMapActivate === "function") {
      previewWindow.onlyPTPracticeMapActivate(cardIndex, { animate: false });
      return true;
    }

    const nodes = Array.from(doc.querySelectorAll(".practice-node-list span"));
    const node = nodes[cardIndex];
    const spotlight = doc.querySelector(".practice-map-spotlight");
    const numberElement = spotlight?.querySelector("small");
    const titleElement = spotlight?.querySelector("strong");
    const detailElement = spotlight?.querySelector("em");
    const activeNumber = node?.querySelector("small");
    const activeTitle = node?.querySelector("strong");
    const activeDetail = node?.querySelector("em");

    if (!node || !spotlight || !titleElement || !detailElement) {
      return false;
    }

    nodes.forEach((item, index) => {
      const isActive = index === cardIndex;
      item.classList.toggle("is-active", isActive);
      item.setAttribute("aria-pressed", String(isActive));
    });

    doc.querySelector(".practice-map")?.style.setProperty("--practice-active", String(cardIndex));
    spotlight.classList.remove("is-leaving", "is-entering");
    if (numberElement) numberElement.textContent = activeNumber?.textContent?.trim() || "";
    titleElement.textContent = activeTitle?.textContent?.trim() || "";
    detailElement.textContent = activeDetail?.textContent?.trim() || "";

    [titleElement, detailElement].forEach((target, index) => {
      const source = index === 0 ? activeTitle : activeDetail;
      ["data-cms-page", "data-cms-key", "data-cms-editable", "data-cms-attribute"].forEach((attribute) => {
        if (source?.hasAttribute(attribute)) {
          target.setAttribute(attribute, source.getAttribute(attribute));
        } else {
          target.removeAttribute(attribute);
        }
      });
    });

    return true;
  };

  const syncField = (input) => {
    if (!input) {
      return;
    }

    pages[pageKey].values[input.dataset.cmsKey] = getInputValue(input);
    if (input.type === "range") {
      const output = input.closest(".admin-range-control")?.querySelector("output");
      if (output) output.textContent = `${normalizeFirstBlockHeight(getInputValue(input))}px`;
    }
    getPreviewTargets(input.dataset.cmsKey).forEach((target) => {
      applyValueToTarget(target, getInputValue(input));
    });
    if (pageKey === "general" && input.dataset.cmsKey === firstBlockHeightKey) {
      applyFirstBlockHeightToPreview(getInputValue(input));
    }
    if (pageKey === "general" && input.dataset.cmsKey.startsWith("background.")) {
      applyBackgroundToPreview();
    }
    if (pageKey === "general" && input.dataset.cmsKey === "site.favicon") {
      applyFaviconToPreview();
    }
  };

  const syncAll = () => {
    currentInputs.forEach(syncField);
  };

  const clearPreviewHighlights = () => {
    const doc = previewDocument();
    if (!doc) {
      return;
    }

    doc.querySelectorAll(".cms-preview-highlight").forEach((element) => {
      element.classList.remove("cms-preview-highlight");
    });
  };

  const installPreviewHelpers = () => {
    const doc = previewDocument();
    if (!doc) {
      return;
    }

    applyFirstBlockHeightToPreview();

    if (!doc.querySelector("#cms-preview-highlight-style")) {
      const style = doc.createElement("style");
      style.id = "cms-preview-highlight-style";
      style.textContent = `
        html.page-loading,
        html.page-loading body {
          opacity: 1 !important;
        }

        main > section,
        .reveal,
        .page-enter {
          opacity: 1 !important;
          transform: none !important;
          animation: none !important;
        }

        [data-cms-editable="true"] {
          transition: outline-color 180ms ease, box-shadow 180ms ease, background-color 180ms ease;
        }

        .cms-preview-highlight {
          outline: 3px solid rgba(184, 91, 55, 0.82) !important;
          outline-offset: 6px !important;
          border-radius: 8px !important;
          background-color: rgba(255, 246, 232, 0.28) !important;
          box-shadow:
            0 0 0 8px rgba(184, 91, 55, 0.1),
            0 18px 48px rgba(184, 91, 55, 0.16) !important;
        }
      `;
      doc.head.appendChild(style);
    }

    doc.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", (event) => event.preventDefault(), { capture: true });
    });
  };

  const markActiveField = (input) => {
    document.querySelectorAll("[data-field-card]").forEach((row) => {
      row.classList.toggle("is-active", row.dataset.fieldKey === input?.dataset.cmsKey);
    });
  };

  const focusPreview = (input) => {
    activeInput = input;
    markActiveField(input);
    clearPreviewHighlights();
    activatePracticePreviewCard(input.dataset.cmsKey);
    syncField(input);

    const target = displayTarget(getPreviewTargets(input.dataset.cmsKey)[0]);
    if (!target) {
      setStatus("Saved field. No visible preview target on this page.", "");
      return;
    }

    target.classList.add("cms-preview-highlight");
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    setStatus("Editing target highlighted in the preview.", "");
  };

  const saveDirectField = async (input) => {
    if (!input || !pages[pageKey]) {
      return;
    }
    const targetPageKey = pageKey;
    const fieldKey = input.dataset.cmsKey;
    const values = { [fieldKey]: getInputValue(input) };
    setStatus("Saving height...", "");
    try {
      const response = await fetch(pages[targetPageKey].saveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Save failed.");
      }
      pages[targetPageKey].values = payload.values;
      setStatus("First block height saved.", "success");
    } catch (error) {
      setStatus(error.message || "Could not save height.", "error");
    }
  };

  const scheduleDirectFieldSave = (input) => {
    if (directSaveTimer) {
      window.clearTimeout(directSaveTimer);
    }
    directSaveTimer = window.setTimeout(() => saveDirectField(input), 260);
  };

  const fieldHint = (field) => {
    if (pageKey === "general" && field.key === firstBlockHeightKey) {
      return "Moves the first container block up or down across every public page. Preview updates while sliding and saves automatically.";
    }

    if (pageKey !== "email") {
      return "";
    }

    const hints = {
      "lead_email.to": "Primary destination for every contact form notification. Use one or more admin emails separated by commas.",
      "lead_email.enabled": "Keep this on when contact form submissions should trigger email alerts.",
      "traffic_report.daily_enabled": "Sends the previous day's traffic report after the day closes.",
      "traffic_report.weekly_enabled": "Sends the previous week's traffic report every Monday.",
      "traffic_report.to": "Destination for traffic reports. Use one or more emails separated by commas.",
      "lead_email.from_email": "Use the Zoho mailbox address so SPF/DKIM alignment stays clean.",
      "lead_email.from_name": "This is the display name admins see in their inbox.",
      "lead_email.smtp_host": "Rarely changes after setup. Zoho usually uses smtppro.zoho.com.",
      "lead_email.smtp_port": "Use 465 for SSL or 587 for TLS.",
      "lead_email.smtp_security": "Use ssl for port 465 or tls for port 587.",
      "lead_email.smtp_username": "Usually the same full mailbox address as the sender email.",
      "lead_email.smtp_password": "Use the mailbox password or a Zoho app password when enabled.",
    };

    return hints[field.key] || "";
  };

  const groupHint = (groupName) => {
    if (pageKey !== "email") {
      return "";
    }

    const hints = {
      "Notification target": "Who receives contact alerts and traffic reports. Test reports use the Traffic report recipient field.",
      "Sender identity": "Inbox-facing sender details. Keep these aligned with the Zoho mailbox.",
      "SMTP access": "Connection details for Zoho. These should only change when the mailbox or provider changes.",
    };

    return hints[groupName] || "";
  };

  const fieldTemplate = (field, value) => {
    let control = "";
    const hint = fieldHint(field);
    const rowClasses = ["admin-field-row"];
    if (pageKey === "email" && field.key === "lead_email.to") {
      rowClasses.push("admin-field-row-primary");
    }
    if (field.type === "favicon") {
      rowClasses.push("admin-field-row-favicon");
    }
    if (field.type === "textarea") {
      control = `<textarea data-editor-input data-cms-key="${escapeHtml(field.key)}" rows="4">${escapeHtml(value)}</textarea>`;
    } else if (field.type === "toggle") {
      control = `
        <span class="admin-toggle-control">
          <input data-editor-input data-cms-key="${escapeHtml(field.key)}" type="checkbox" ${value === "on" ? "checked" : ""}>
          <span aria-hidden="true"></span>
          <strong>${value === "on" ? "Enabled" : "Disabled"}</strong>
        </span>
      `;
    } else if (field.type === "image") {
      const imageName = firstImageName(value);
      control = `
        <input data-editor-input data-cms-key="${escapeHtml(field.key)}" type="hidden" value="${escapeHtml(imageName)}">
        <span class="admin-image-control admin-image-control-list" data-image-control>
          <span class="admin-image-preview-list ${imageName ? "has-image" : ""}" data-image-preview-list>
            ${
              imageName
                ? `
                  <span class="admin-background-thumb" data-background-thumb="${escapeHtml(imageName)}">
                    <img data-src="${escapeHtml(backgroundUrl(imageName))}" alt="" loading="lazy" decoding="async" fetchpriority="low">
                    <button type="button" data-remove-background="${escapeHtml(imageName)}">Remove</button>
                  </span>
                `
                : `<em>No background image uploaded</em>`
            }
          </span>
          <input data-upload-input data-cms-key="${escapeHtml(field.key)}" type="file" accept="image/png,image/jpeg,image/webp,image/gif">
          <small data-upload-status>Upload one background image. New uploads replace the current background automatically.</small>
        </span>
      `;
    } else if (field.type === "favicon") {
      const imageName = firstImageName(value);
      control = `
        <input data-editor-input data-cms-key="${escapeHtml(field.key)}" type="hidden" value="${escapeHtml(imageName)}">
        <span class="admin-image-control admin-image-control-list" data-favicon-control>
          <span class="admin-image-preview-list admin-favicon-preview-list ${imageName ? "has-image" : ""}" data-favicon-preview-list>
            ${
              imageName
                ? `
                  <span class="admin-favicon-thumb" data-favicon-thumb="${escapeHtml(imageName)}">
                    <img src="${escapeHtml(faviconUrl(imageName))}" alt="" loading="lazy" decoding="async">
                    <button type="button" data-remove-favicon="${escapeHtml(imageName)}">Remove</button>
                  </span>
                `
                : `<em>No page tab icon uploaded</em>`
            }
          </span>
          <input data-favicon-upload-input data-cms-key="${escapeHtml(field.key)}" type="file" accept="image/x-icon,image/vnd.microsoft.icon,image/png,image/svg+xml,image/webp">
          <small data-upload-status>Upload an ICO, PNG, SVG, or WebP icon for the browser tab.</small>
        </span>
      `;
    } else if (field.type === "range") {
      const normalizedValue = normalizeFirstBlockHeight(value);
      const isFirstBlockRange = field.key === firstBlockHeightKey;
      control = `
        <span class="admin-range-control">
          <input data-editor-input data-cms-key="${escapeHtml(field.key)}" ${isFirstBlockRange ? 'data-direct-save="true"' : ""} type="range" min="0" max="120" step="2" value="${escapeHtml(normalizedValue)}">
          <output>${escapeHtml(normalizedValue)}px</output>
          <small>0px - 120px from the navigation. This setting is saved automatically.</small>
        </span>
      `;
    } else if (field.type === "password") {
      control = `<input data-editor-input data-cms-key="${escapeHtml(field.key)}" type="password" autocomplete="new-password" value="${escapeHtml(value)}">`;
    } else {
      control = `<input data-editor-input data-cms-key="${escapeHtml(field.key)}" type="text" value="${escapeHtml(value)}">`;
    }

    return `
      <label class="${rowClasses.join(" ")}" data-field-card data-field-key="${escapeHtml(field.key)}" data-field-type="${escapeHtml(field.type || "text")}">
        <span class="admin-field-meta">
          <span>${escapeHtml(field.label)}</span>
          <small>${escapeHtml(field.key)}</small>
        </span>
        ${hint ? `<p class="admin-field-hint">${escapeHtml(hint)}</p>` : ""}
        ${control}
      </label>
    `;
  };

  const groupActionTemplate = (groupName) => {
    if (pageKey !== "email" || groupName !== "Notification target") {
      return "";
    }

    return `
      <div class="admin-field-action-card" data-traffic-report-test-card>
        <div>
          <strong>Test traffic report</strong>
          <p>Send a one-time report for the past 24 hours to Traffic report recipient.</p>
          <small data-traffic-report-test-status></small>
        </div>
        <button type="button" class="admin-test-report-button" data-send-test-traffic-report>
          <i data-lucide="send"></i>
          <span>Send test</span>
        </button>
      </div>
    `;
  };

  const collectCurrentValues = () => {
    const values = {};
    currentInputs.forEach((input) => {
      values[input.dataset.cmsKey] = getInputValue(input);
    });
    return values;
  };

  const saveCurrentPageValues = async () => {
    const response = await fetch(pages[pageKey].saveUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ values: collectCurrentValues() }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || "Save failed.");
    }
    pages[pageKey].values = payload.values;
    return payload;
  };

  const sendTestTrafficReport = async (button) => {
    if (!trafficReportTestUrl || button.disabled) {
      return;
    }

    const statusTarget = button.closest("[data-traffic-report-test-card]")?.querySelector("[data-traffic-report-test-status]");
    const label = button.querySelector("span");
    const icon = button.querySelector("i");

    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.classList.remove("is-sent", "is-error");
    button.classList.add("is-sending");
    if (label) label.textContent = "Sending...";
    if (icon) icon.setAttribute("data-lucide", "loader-circle");
    if (statusTarget) statusTarget.textContent = "Saving settings, then sending the report...";
    setStatus("Sending test traffic report...", "");
    window.lucide?.createIcons();

    try {
      await saveCurrentPageValues();
      const response = await fetch(trafficReportTestUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Could not send test report.");
      }

      button.classList.remove("is-sending");
      button.classList.add("is-sent");
      if (label) label.textContent = "Sent";
      if (icon) icon.setAttribute("data-lucide", "check");
      if (statusTarget) statusTarget.textContent = payload.message || "Test report sent.";
      setStatus(payload.message || "Test traffic report sent.", "success");
    } catch (error) {
      button.classList.remove("is-sending");
      button.classList.add("is-error");
      if (label) label.textContent = "Send test";
      if (icon) icon.setAttribute("data-lucide", "circle-alert");
      if (statusTarget) statusTarget.textContent = error.message || "Could not send test report.";
      setStatus(error.message || "Could not send test report.", "error");
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      window.lucide?.createIcons();
      window.setTimeout(() => {
        button.classList.remove("is-sent", "is-error", "is-sending");
        if (label) label.textContent = "Send test";
        if (icon) icon.setAttribute("data-lucide", "send");
        window.lucide?.createIcons();
      }, 2600);
    }
  };

  const renderFields = () => {
    const page = pages[pageKey];
    let activeGroup = "";
    let html = "";

    page.fields.forEach((field) => {
      if (field.group !== activeGroup) {
        if (activeGroup) {
          html += groupActionTemplate(activeGroup);
          html += `</div></section>`;
        }
        activeGroup = field.group;
        const hint = groupHint(activeGroup);
        html += `
          <section class="admin-field-group" data-field-group="${escapeHtml(activeGroup)}">
            <header class="admin-field-group-label">
              <span>${escapeHtml(activeGroup)}</span>
              <small>${page.fields.filter((item) => item.group === activeGroup).length} fields</small>
            </header>
            ${hint ? `<p class="admin-field-group-hint">${escapeHtml(hint)}</p>` : ""}
            <div class="admin-field-group-body">
        `;
      }
      html += fieldTemplate(field, page.values[field.key] ?? field.default ?? "");
    });
    if (activeGroup) {
      html += groupActionTemplate(activeGroup);
      html += `</div></section>`;
    }

    fieldList.innerHTML = html;
    currentInputs = Array.from(fieldList.querySelectorAll("[data-editor-input]"));
    activeInput = currentInputs[0] || null;
    fieldList.querySelectorAll("[data-image-preview-list]").forEach(observeBackgroundThumbs);

    currentInputs.forEach((input) => {
      input.addEventListener("input", () => {
        syncField(input);
        if (input.dataset.directSave === "true") {
          scheduleDirectFieldSave(input);
        }
      });
      input.addEventListener("change", () => {
        syncField(input);
        if (input.dataset.directSave === "true") {
          scheduleDirectFieldSave(input);
        }
        const toggleLabel = input.closest(".admin-toggle-control")?.querySelector("strong");
        if (toggleLabel) {
          toggleLabel.textContent = input.checked ? "Enabled" : "Disabled";
        }
        if (pageKey === "general" && input.dataset.cmsKey === "background.enabled") {
          saveBackgroundEnabled(input.checked ? "on" : "off");
        }
      });
      input.addEventListener("focus", () => focusPreview(input));
      input.addEventListener("click", () => focusPreview(input));
    });

    fieldList.querySelector("[data-send-test-traffic-report]")?.addEventListener("click", (event) => {
      sendTestTrafficReport(event.currentTarget);
    });

    fieldList.querySelectorAll("[data-upload-input]").forEach((uploadInput) => {
      uploadInput.addEventListener("change", async () => {
        const files = Array.from(uploadInput.files || []);
        if (!files.length || !backgroundUploadUrl) {
          return;
        }

        const fieldKey = uploadInput.dataset.cmsKey;
        const hiddenInput = fieldList.querySelector(`[data-editor-input][data-cms-key="${selectorValue(fieldKey)}"]`);
        const row = uploadInput.closest("[data-field-card]");
        const preview = row?.querySelector("[data-image-preview-list]");
        const uploadStatus = row?.querySelector("[data-upload-status]");
        const formData = new FormData();
        formData.append("background", files[0]);

        if (uploadStatus) uploadStatus.textContent = "Uploading image...";
        setStatus("Uploading background image...", "");

        try {
          const response = await fetch(backgroundUploadUrl, {
            method: "POST",
            credentials: "same-origin",
            body: formData,
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || "Upload failed.");
          }

          setBackgroundState(payload.backgroundImage || "", payload.backgroundEnabled || "on");
          renderBackgroundThumbs(preview, payload.backgroundImage || "");
          uploadInput.value = "";
          if (uploadStatus) uploadStatus.textContent = "Image uploaded and saved.";
          applyBackgroundToPreview();
          setStatus("Background image uploaded and saved.", "success");
        } catch (error) {
          if (uploadStatus) uploadStatus.textContent = error.message || "Upload failed.";
          setStatus(error.message || "Could not upload image.", "error");
        }
      });
    });

    fieldList.querySelectorAll("[data-favicon-upload-input]").forEach((uploadInput) => {
      uploadInput.addEventListener("change", async () => {
        const files = Array.from(uploadInput.files || []);
        if (!files.length || !faviconUploadUrl) {
          return;
        }

        const row = uploadInput.closest("[data-field-card]");
        const uploadStatus = row?.querySelector("[data-upload-status]");
        const formData = new FormData();
        formData.append("favicon", files[0]);

        if (uploadStatus) uploadStatus.textContent = "Uploading icon...";
        setStatus("Uploading page tab icon...", "");

        try {
          const response = await fetch(faviconUploadUrl, {
            method: "POST",
            credentials: "same-origin",
            body: formData,
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || "Upload failed.");
          }

          setFaviconState(payload.favicon || "");
          uploadInput.value = "";
          if (uploadStatus) uploadStatus.textContent = "Icon uploaded and saved.";
          setStatus("Page tab icon uploaded and saved.", "success");
        } catch (error) {
          if (uploadStatus) uploadStatus.textContent = error.message || "Upload failed.";
          setStatus(error.message || "Could not upload icon.", "error");
        }
      });
    });

  };

  fieldList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest("[data-remove-background]");
    if (!button || !fieldList.contains(button)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    removeBackgroundImage(button);
  });

  fieldList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest("[data-remove-favicon]");
    if (!button || !fieldList.contains(button)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    removeFavicon(button);
  });

  const updatePageChrome = () => {
    const page = pages[pageKey];
    editor.dataset.adminPage = pageKey;
    if (pageTitle) pageTitle.textContent = page.label;
    if (previewTitle) previewTitle.textContent = page.label;
    if (fieldPanelTitle) fieldPanelTitle.textContent = page.label;
    if (previewOpen) previewOpen.href = page.previewUrl;

    pageButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.pageSwitch === pageKey);
    });
  };

  const setPage = (nextPageKey, options = {}) => {
    if (!pages[nextPageKey]) {
      return;
    }

    pageKey = nextPageKey;
    updatePageChrome();
    renderFields();
    setStatus("Preview is live. Save when ready.", "");
    setSaveButtonState("idle", "Save changes");

    if (frame && frame.getAttribute("src") !== pages[pageKey].previewUrl) {
      frame.setAttribute("src", pages[pageKey].previewUrl);
    } else {
      installPreviewHelpers();
      syncAll();
      if (activeInput) {
        focusPreview(activeInput);
      }
    }

    fieldList?.scrollTo({ top: 0 });

    if (options.pushState !== false) {
      window.history.pushState({ pageKey }, "", pages[pageKey].editorUrl);
    }
  };

  pageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setPage(button.dataset.pageSwitch);
    });
  });

  window.addEventListener("popstate", () => {
    const matchingPageKey = Object.keys(pages).find((key) => pages[key].editorUrl === window.location.pathname);
    if (matchingPageKey) {
      setPage(matchingPageKey, { pushState: false });
    }
  });

  frame?.addEventListener("load", () => {
    installPreviewHelpers();
    syncAll();
    if (activeInput) {
      window.setTimeout(() => focusPreview(activeInput), 90);
    }
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    syncAll();
    setStatus("Saving changes...", "");
    setSaveButtonState("saving", "Saving...");

    const values = {};
    currentInputs.forEach((input) => {
      values[input.dataset.cmsKey] = getInputValue(input);
    });

    try {
      const response = await fetch(pages[pageKey].saveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ values }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Save failed.");
      }

      pages[pageKey].values = payload.values;
      setStatus("Saved. Your changes are live.", "success");
      setSaveButtonState("saved", "Saved");
      resetSaveButtonSoon();
    } catch (error) {
      setStatus(error.message || "Could not save changes.", "error");
      setSaveButtonState("error", "Save failed");
      resetSaveButtonSoon();
    }
  });

  setPage(pageKey, { pushState: false });

  window.setTimeout(() => {
    installPreviewHelpers();
    syncAll();
  }, 400);
})();
