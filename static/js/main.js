window.addEventListener("DOMContentLoaded", () => {
  document.documentElement.classList.add("js");
  if (!document.documentElement.classList.contains("page-entered")) {
    document.documentElement.classList.add("page-loading");
    document.documentElement.classList.remove("page-ready");
  }
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const mobileLiteQuery = window.matchMedia("(max-width: 900px)");
  document.documentElement.classList.toggle("mobile-lite", mobileLiteQuery.matches);
  const watchMediaQuery = (query, callback) => {
    if (typeof query?.addEventListener === "function") {
      query.addEventListener("change", callback);
    } else if (typeof query?.addListener === "function") {
      query.addListener(callback);
    }
  };

  if (window.lucide) {
    window.lucide.createIcons();
  }

  const navToggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".site-nav");
  const siteHeader = document.querySelector(".site-header");
  const mobileNavQuery = mobileLiteQuery;

  const syncNavState = () => {
    if (!nav) {
      return;
    }

    if (mobileNavQuery.matches) {
      nav.setAttribute("aria-hidden", String(!nav.classList.contains("open")));
    } else {
      nav.classList.remove("open");
      nav.removeAttribute("aria-hidden");
      navToggle?.setAttribute("aria-expanded", "false");
    }
  };

  const closeNav = () => {
    nav?.classList.remove("open");
    siteHeader?.classList.remove("is-nav-open");
    navToggle?.setAttribute("aria-expanded", "false");
    syncNavState();
  };

  let lastNavToggleAt = 0;
  const toggleNav = () => {
    const now = Date.now();
    if (now - lastNavToggleAt < 160) {
      return;
    }
    lastNavToggleAt = now;
    const isOpen = nav?.classList.toggle("open");
    siteHeader?.classList.toggle("is-nav-open", Boolean(isOpen));
    navToggle.setAttribute("aria-expanded", String(Boolean(isOpen)));
    syncNavState();
  };

  navToggle?.addEventListener("click", toggleNav);
  navToggle?.addEventListener("pointerup", (event) => {
    if (event.pointerType === "touch") {
      event.preventDefault();
      toggleNav();
    }
  });

  nav?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeNav);
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeNav();
    }
  });

  syncNavState();
  watchMediaQuery(mobileNavQuery, syncNavState);

  const initStaticBackground = () => {
    const backgroundApi = (window.onlyPTBackgroundSlideshow = window.onlyPTBackgroundSlideshow || {});
    const refresh = () => {
      const enabled = document.body.classList.contains("site-background-enabled");
      const image = document.body.style.getPropertyValue("--site-bg-image").trim();
      document.body.classList.toggle("background-static-ready", Boolean(enabled && image));
      document.body.classList.remove("background-canvas-ready");
      document.body.dataset.bgSlideshowMode = enabled && image ? "static" : "off";
      document.body.dataset.bgSlideshowCount = enabled && image ? "1" : "0";
      document.body.dataset.bgSlideshowIndex = "0";
      document.body.dataset.bgSlideshowAnimating = "false";
      document.body.dataset.bgSlideshowReady = enabled && image ? "true" : "false";
      backgroundApi.state = {
        mode: document.body.dataset.bgSlideshowMode,
        imageCount: Number(document.body.dataset.bgSlideshowCount),
        currentIndex: 0,
        animating: false,
        canvasReady: false,
      };
    };

    backgroundApi.refresh = refresh;
    refresh();
    return backgroundApi;
  };

  initStaticBackground();

  const pageSections = document.querySelectorAll("main > section");
  pageSections.forEach((section, index) => {
    section.classList.add("page-enter");
    section.style.setProperty("--page-enter-delay", `${Math.min(index * 90, 360)}ms`);
  });

  document.querySelectorAll("main > section.cta-panel").forEach((panel) => {
    const activatePanel = () => panel.classList.add("is-interactive");
    const deactivatePanel = () => {
      if (!panel.matches(":focus-within")) {
        panel.classList.remove("is-interactive");
      }
    };

    panel.addEventListener("pointerenter", activatePanel);
    panel.addEventListener("pointerleave", deactivatePanel);
    panel.addEventListener("focusin", activatePanel);
    panel.addEventListener("focusout", () => {
      window.requestAnimationFrame(deactivatePanel);
    });
  });

  document.querySelectorAll(".reveal").forEach((element, index) => {
    element.style.setProperty("--reveal-delay", `${Math.min(index * 55, 420)}ms`);
  });

  const revealElements = document.querySelectorAll(".reveal");
  const markPageReady = () => {
    document.documentElement.classList.remove("page-loading");
    document.documentElement.classList.add("page-ready", "page-entered");
  };

  const revealVisibleElements = () => {
    revealElements.forEach((element) => {
      const rect = element.getBoundingClientRect();
      const isVisible = rect.top < window.innerHeight * 0.92 && rect.bottom > 0;
      if (isVisible) {
        element.classList.add("visible");
      }
    });
  };

  if (mobileLiteQuery.matches || prefersReducedMotion) {
    revealElements.forEach((element) => {
      element.classList.add("visible");
      element.style.setProperty("--reveal-delay", "0ms");
    });
    markPageReady();
  } else {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18 }
    );

    revealElements.forEach((element) => observer.observe(element));
    revealVisibleElements();
    window.addEventListener("pageshow", () => {
      revealVisibleElements();
      window.setTimeout(markPageReady, 90);
    });
    window.setTimeout(revealVisibleElements, 120);
    window.setTimeout(markPageReady, 120);
  }

  const updateProgress = () => {
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const progress = scrollable > 0 ? window.scrollY / scrollable : 0;
    document.documentElement.style.setProperty("--scroll-progress", `${Math.max(0, Math.min(1, progress))}`);
  };

  updateProgress();
  window.addEventListener("scroll", updateProgress, { passive: true });

  const ambientShapes = document.querySelectorAll(".geo-shape");
  const randomBetween = (min, max) => Math.random() * (max - min) + min;

  const moveAmbientShape = (shape, index) => {
    const mobileScale = window.matchMedia("(max-width: 700px)").matches ? 0.58 : 1;
    const driftX = randomBetween(-48, 48) * mobileScale;
    const driftY = randomBetween(-34, 34) * mobileScale;
    const rotation = randomBetween(-24, 24) + index * 7;
    const scale = randomBetween(0.92, 1.08);
    const duration = randomBetween(17000, 34000);
    const nextMove = randomBetween(7200, 13200);

    shape.style.setProperty("--geo-x", `${driftX.toFixed(1)}px`);
    shape.style.setProperty("--geo-y", `${driftY.toFixed(1)}px`);
    shape.style.setProperty("--geo-rotate", `${rotation.toFixed(1)}deg`);
    shape.style.setProperty("--geo-scale", scale.toFixed(3));
    shape.style.setProperty("--geo-duration", `${Math.round(duration)}ms`);

    window.setTimeout(() => moveAmbientShape(shape, index), nextMove);
  };

  if (!prefersReducedMotion && ambientShapes.length && !mobileLiteQuery.matches) {
    ambientShapes.forEach((shape, index) => {
      window.setTimeout(() => moveAmbientShape(shape, index), index * 420);
    });
  }

  const practiceMap = document.querySelector(".practice-map");
  const practiceSpotlight = practiceMap?.querySelector(".practice-map-spotlight");
  const practiceNodes = practiceMap ? Array.from(practiceMap.querySelectorAll(".practice-node-list span")) : [];

  if (practiceMap && practiceSpotlight && practiceNodes.length) {
    const practiceDesktopQuery = window.matchMedia("(min-width: 901px)");
    const numberElement = practiceSpotlight.querySelector("small");
    const titleElement = practiceSpotlight.querySelector("strong");
    const detailElement = practiceSpotlight.querySelector("em");
    let activePracticeIndex = 0;
    let practiceTimer = null;
    let practiceLastSwitchAt = 0;
    let practiceTransitionTimer = null;

    const syncEditableAttributes = (target, source) => {
      if (!target || !source) {
        return;
      }

      ["data-cms-page", "data-cms-key", "data-cms-editable", "data-cms-attribute"].forEach((attribute) => {
        if (source.hasAttribute(attribute)) {
          target.setAttribute(attribute, source.getAttribute(attribute));
        } else {
          target.removeAttribute(attribute);
        }
      });
    };

    const writePracticeSpotlight = (activeNode) => {
      const activeNumber = activeNode.querySelector("small");
      const activeTitle = activeNode.querySelector("strong");
      const activeDetail = activeNode.querySelector("em");

      if (numberElement) numberElement.textContent = activeNumber?.textContent?.trim() || "";
      if (titleElement) {
        titleElement.textContent = activeTitle?.textContent?.trim() || "";
        syncEditableAttributes(titleElement, activeTitle);
      }
      if (detailElement) {
        detailElement.textContent = activeDetail?.textContent?.trim() || "";
        syncEditableAttributes(detailElement, activeDetail);
      }
    };

    const clearPracticeTransition = () => {
      if (practiceTransitionTimer) {
        window.clearTimeout(practiceTransitionTimer);
        practiceTransitionTimer = null;
      }
      practiceSpotlight.classList.remove("is-leaving", "is-entering");
      practiceMap.classList.remove("is-switching");
    };

    const setActivePractice = (index, options = {}) => {
      const nextIndex = (index + practiceNodes.length) % practiceNodes.length;
      const shouldAnimate =
        options.animate !== false &&
        practiceDesktopQuery.matches &&
        nextIndex !== activePracticeIndex &&
        !prefersReducedMotion;

      activePracticeIndex = nextIndex;
      const activeNode = practiceNodes[activePracticeIndex];

      practiceNodes.forEach((node, nodeIndex) => {
        const isActive = nodeIndex === activePracticeIndex;
        node.classList.toggle("is-active", isActive);
        node.setAttribute("aria-pressed", String(isActive));
      });

      practiceMap.style.setProperty("--practice-active", String(activePracticeIndex));
      clearPracticeTransition();

      if (!shouldAnimate) {
        writePracticeSpotlight(activeNode);
        return;
      }

      practiceSpotlight.classList.add("is-leaving");
      practiceMap.classList.add("is-switching");

      practiceTransitionTimer = window.setTimeout(() => {
        writePracticeSpotlight(activeNode);
        practiceSpotlight.classList.remove("is-leaving");
        practiceSpotlight.classList.add("is-entering");

        practiceTransitionTimer = window.setTimeout(() => {
          clearPracticeTransition();
        }, 520);
      }, 190);
    };

    const startPracticeTimer = () => {
      if (prefersReducedMotion || practiceTimer || !practiceDesktopQuery.matches) {
        return;
      }

      const tick = (now) => {
        if (!practiceTimer || document.hidden || !practiceDesktopQuery.matches) {
          practiceTimer = null;
          return;
        }

        if (!practiceLastSwitchAt) {
          practiceLastSwitchAt = now;
        }

        if (now - practiceLastSwitchAt >= 3200) {
          setActivePractice(activePracticeIndex + 1);
          practiceLastSwitchAt = now;
        }

        practiceTimer = window.requestAnimationFrame(tick);
      };

      practiceLastSwitchAt = 0;
      practiceTimer = window.requestAnimationFrame(tick);
    };

    const stopPracticeTimer = () => {
      if (practiceTimer) {
        window.cancelAnimationFrame(practiceTimer);
        practiceTimer = null;
      }
      practiceLastSwitchAt = 0;
    };

    window.onlyPTPracticeMapActivate = (index, options = {}) => {
      stopPracticeTimer();
      setActivePractice(index, { animate: options.animate !== false });
    };

    practiceNodes.forEach((node, index) => {
      node.setAttribute("role", "button");
      node.setAttribute("tabindex", "0");
      node.addEventListener("click", () => {
        setActivePractice(index);
      });
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setActivePractice(index);
        }
      });
    });

    practiceMap.addEventListener("mouseenter", stopPracticeTimer);
    practiceMap.addEventListener("mouseleave", startPracticeTimer);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stopPracticeTimer();
      } else {
        startPracticeTimer();
      }
    });
    watchMediaQuery(practiceDesktopQuery, () => {
      if (practiceDesktopQuery.matches) {
        startPracticeTimer();
      } else {
        stopPracticeTimer();
        setActivePractice(0, { animate: false });
      }
    });
    setActivePractice(0, { animate: false });
    startPracticeTimer();
  }

  const practiceKey = document.querySelector(".practice-map-key");
  const practiceKeyTrack = practiceKey?.querySelector(".practice-map-key-track");
  if (
    practiceKey &&
    practiceKeyTrack &&
    !prefersReducedMotion &&
    !(mobileLiteQuery.matches && document.body.classList.contains("site-background-enabled"))
  ) {
    const practiceKeyMobileQuery = window.matchMedia("(max-width: 700px)");
    let practiceKeyFrame = null;
    let practiceKeyLastTime = 0;
    let practiceKeyOffset = 0;
    let practiceKeyPausedUntil = 0;

    const stopPracticeKeyMotion = () => {
      if (practiceKeyFrame) {
        window.cancelAnimationFrame(practiceKeyFrame);
        practiceKeyFrame = null;
      }
      practiceKeyLastTime = 0;
    };

    const movePracticeKey = (time) => {
      if (!practiceKeyMobileQuery.matches) {
        stopPracticeKeyMotion();
        practiceKeyTrack.style.removeProperty("--practice-key-shift");
        return;
      }

      const loopDistance = practiceKeyTrack.scrollWidth / 2;
      if (loopDistance > practiceKey.clientWidth) {
        const delta = practiceKeyLastTime ? time - practiceKeyLastTime : 16;
        if (time > practiceKeyPausedUntil) {
          practiceKeyOffset -= 0.032 * delta;
          if (Math.abs(practiceKeyOffset) >= loopDistance) {
            practiceKeyOffset = 0;
          }
          practiceKeyTrack.style.setProperty("--practice-key-shift", `${practiceKeyOffset.toFixed(2)}px`);
        }
      }

      practiceKeyLastTime = time;
      practiceKeyFrame = window.requestAnimationFrame(movePracticeKey);
    };

    const startPracticeKeyMotion = () => {
      if (!practiceKeyMobileQuery.matches || practiceKeyFrame) {
        return;
      }

      document.documentElement.classList.add("practice-key-js");
      practiceKey.classList.add("is-auto-scrolling");
      practiceKeyFrame = window.requestAnimationFrame(movePracticeKey);
    };

    const syncPracticeKeyMotion = () => {
      if (practiceKeyMobileQuery.matches) {
        startPracticeKeyMotion();
      } else {
        practiceKey.classList.remove("is-auto-scrolling");
        document.documentElement.classList.remove("practice-key-js");
        stopPracticeKeyMotion();
        practiceKeyOffset = 0;
        practiceKeyTrack.style.removeProperty("--practice-key-shift");
      }
    };

    practiceKey.addEventListener(
      "pointerdown",
      () => {
        practiceKeyPausedUntil = performance.now() + 1800;
      },
      { passive: true }
    );

    watchMediaQuery(practiceKeyMobileQuery, syncPracticeKeyMotion);
    syncPracticeKeyMotion();
  }

  if (!prefersReducedMotion && window.matchMedia("(pointer: fine)").matches) {
    window.addEventListener(
      "pointermove",
      (event) => {
        document.documentElement.style.setProperty("--pointer-x", `${event.clientX}px`);
        document.documentElement.style.setProperty("--pointer-y", `${event.clientY}px`);
      },
      { passive: true }
    );

    const heroVisual = document.querySelector(".hero-visual");
    heroVisual?.addEventListener("pointermove", (event) => {
      const rect = heroVisual.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      heroVisual.style.setProperty("--tilt-x", `${(-y * 3).toFixed(2)}deg`);
      heroVisual.style.setProperty("--tilt-y", `${(x * 4).toFixed(2)}deg`);
    });
    heroVisual?.addEventListener("pointerleave", () => {
      heroVisual.style.setProperty("--tilt-x", "0deg");
      heroVisual.style.setProperty("--tilt-y", "0deg");
    });
  }
});
