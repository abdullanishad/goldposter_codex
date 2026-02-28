(function () {
  const boot = window.CALIBRATE_DATA;
  if (!boot) {
    return;
  }

  const FIELD_META = {
    todays_date: { label: "DATE", color: "#8e44ad", defaultArea: { x: 0.05, y: 0.05, width: 0.25, height: 0.08 } },
    price_1g: { label: "1G", color: "#b8860b", defaultArea: { x: 0.30, y: 0.35, width: 0.40, height: 0.12 } },
    price_8g: { label: "8G", color: "#d35400", defaultArea: { x: 0.30, y: 0.50, width: 0.40, height: 0.12 } },
    logo_area: { label: "LOGO", color: "#0056b3", defaultArea: { x: 0.75, y: 0.05, width: 0.20, height: 0.20 } },
    address: { label: "ADDRESS", color: "#1d7a46", defaultArea: { x: 0.10, y: 0.80, width: 0.80, height: 0.08 } },
    whatsapp_number: { label: "WHATSAPP", color: "#0f9d58", defaultArea: { x: 0.10, y: 0.88, width: 0.40, height: 0.06 } },
    social_handle: { label: "SOCIAL", color: "#c0392b", defaultArea: { x: 0.55, y: 0.88, width: 0.35, height: 0.06 } },
  };

  const fields = Object.keys(FIELD_META);
  const image = document.getElementById("template-image");
  const stage = document.getElementById("editor-stage");
  const boxLayer = document.getElementById("box-layer");
  const gridOverlay = document.getElementById("grid-overlay");
  const activeFieldLabel = document.getElementById("active-field");
  const saveStatus = document.getElementById("save-status");

  const liveEls = {};
  fields.forEach(function (field) {
    liveEls[field] = document.getElementById(`${field}-live`);
  });

  const areas = {};
  fields.forEach(function (field) {
    areas[field] = normalizeArea(boot.existingAreas[field]);
  });

  const boxEls = {};
  let activeField = null;
  let gridVisible = true;
  let interaction = null;

  function normalizeArea(area) {
    if (!area || typeof area !== "object") {
      return null;
    }
    const x = Number(area.x);
    const y = Number(area.y);
    const width = Number(area.width);
    const height = Number(area.height);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height)) {
      return null;
    }
    if (width <= 0 || height <= 0) {
      return null;
    }
    return {
      x: clamp(x, 0, 1),
      y: clamp(y, 0, 1),
      width: clamp(width, 0.01, 1),
      height: clamp(height, 0.01, 1),
    };
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function stageSize() {
    return {
      width: image.clientWidth,
      height: image.clientHeight,
    };
  }

  function areaToPixels(area) {
    const size = stageSize();
    return {
      x: Math.round(area.x * size.width),
      y: Math.round(area.y * size.height),
      width: Math.round(area.width * size.width),
      height: Math.round(area.height * size.height),
    };
  }

  function pixelsToArea(px) {
    const size = stageSize();
    const width = Math.max(20, Math.min(size.width, px.width));
    const height = Math.max(20, Math.min(size.height, px.height));
    const x = clamp(px.x, 0, size.width - width);
    const y = clamp(px.y, 0, size.height - height);
    return {
      x: x / size.width,
      y: y / size.height,
      width: width / size.width,
      height: height / size.height,
    };
  }

  function setActiveField(field) {
    activeField = field;
    activeFieldLabel.textContent = `Active field: ${field || "none"}`;
  }

  function ensureArea(field) {
    if (!areas[field]) {
      areas[field] = FIELD_META[field].defaultArea;
    }
    renderField(field);
    updateLiveValues();
  }

  function createBox(field) {
    const meta = FIELD_META[field];
    const box = document.createElement("div");
    box.className = "layout-box";
    box.dataset.field = field;
    box.style.position = "absolute";
    box.style.border = `2px solid ${meta.color}`;
    box.style.background = "rgba(255,255,255,0.10)";
    box.style.boxSizing = "border-box";
    box.style.cursor = "move";

    const label = document.createElement("div");
    label.textContent = meta.label;
    label.style.position = "absolute";
    label.style.left = "0";
    label.style.top = "-20px";
    label.style.fontSize = "12px";
    label.style.padding = "2px 6px";
    label.style.background = meta.color;
    label.style.color = "#fff";
    label.style.borderRadius = "4px";
    box.appendChild(label);

    ["nw", "ne", "sw", "se"].forEach(function (corner) {
      const handle = document.createElement("div");
      handle.className = "resize-handle";
      handle.dataset.corner = corner;
      handle.style.position = "absolute";
      handle.style.width = "10px";
      handle.style.height = "10px";
      handle.style.background = meta.color;
      handle.style.border = "1px solid #fff";
      handle.style.boxSizing = "border-box";
      handle.style.borderRadius = "50%";
      handle.style.zIndex = "2";

      if (corner === "nw") {
        handle.style.left = "-6px";
        handle.style.top = "-6px";
      }
      if (corner === "ne") {
        handle.style.right = "-6px";
        handle.style.top = "-6px";
      }
      if (corner === "sw") {
        handle.style.left = "-6px";
        handle.style.bottom = "-6px";
      }
      if (corner === "se") {
        handle.style.right = "-6px";
        handle.style.bottom = "-6px";
      }
      box.appendChild(handle);
    });

    box.addEventListener("pointerdown", onPointerDown);
    boxLayer.appendChild(box);
    boxEls[field] = box;
    return box;
  }

  function renderField(field) {
    if (!areas[field]) {
      return;
    }
    const box = boxEls[field] || createBox(field);
    const px = areaToPixels(areas[field]);
    box.style.left = `${px.x}px`;
    box.style.top = `${px.y}px`;
    box.style.width = `${px.width}px`;
    box.style.height = `${px.height}px`;
    box.style.display = "block";
  }

  function renderAll() {
    const size = stageSize();
    stage.style.width = `${size.width}px`;
    stage.style.height = `${size.height}px`;
    boxLayer.style.width = `${size.width}px`;
    boxLayer.style.height = `${size.height}px`;
    gridOverlay.style.width = `${size.width}px`;
    gridOverlay.style.height = `${size.height}px`;

    fields.forEach(renderField);
    updateLiveValues();
  }

  function applyGridStyle() {
    if (!gridVisible) {
      gridOverlay.style.backgroundImage = "none";
      return;
    }
    gridOverlay.style.backgroundSize = "50px 50px";
    gridOverlay.style.backgroundImage =
      "linear-gradient(to right, rgba(255,255,255,0.30) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.30) 1px, transparent 1px)";
  }

  function updateLiveValues() {
    fields.forEach(function (field) {
      if (!areas[field]) {
        liveEls[field].textContent = "not set";
        return;
      }
      const px = areaToPixels(areas[field]);
      const a = areas[field];
      liveEls[field].textContent =
        `x:${px.x}, y:${px.y}, w:${px.width}, h:${px.height} | % x:${a.x.toFixed(4)}, y:${a.y.toFixed(4)}, w:${a.width.toFixed(4)}, h:${a.height.toFixed(4)}`;
    });
  }

  function onPointerDown(evt) {
    const box = evt.currentTarget;
    const field = box.dataset.field;
    const handle = evt.target.closest(".resize-handle");
    const mode = handle ? "resize" : "move";
    const corner = handle ? handle.dataset.corner : null;

    setActiveField(field);
    saveStatus.textContent = "";

    interaction = {
      mode,
      corner,
      field,
      startX: evt.clientX,
      startY: evt.clientY,
      startBox: areaToPixels(areas[field]),
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    evt.preventDefault();
  }

  function onPointerMove(evt) {
    if (!interaction) {
      return;
    }

    const dx = evt.clientX - interaction.startX;
    const dy = evt.clientY - interaction.startY;
    const size = stageSize();

    let next = {
      x: interaction.startBox.x,
      y: interaction.startBox.y,
      width: interaction.startBox.width,
      height: interaction.startBox.height,
    };

    if (interaction.mode === "move") {
      next.x = interaction.startBox.x + dx;
      next.y = interaction.startBox.y + dy;
    } else {
      const minSize = 20;
      if (interaction.corner.indexOf("w") !== -1) {
        next.x = interaction.startBox.x + dx;
        next.width = interaction.startBox.width - dx;
      }
      if (interaction.corner.indexOf("e") !== -1) {
        next.width = interaction.startBox.width + dx;
      }
      if (interaction.corner.indexOf("n") !== -1) {
        next.y = interaction.startBox.y + dy;
        next.height = interaction.startBox.height - dy;
      }
      if (interaction.corner.indexOf("s") !== -1) {
        next.height = interaction.startBox.height + dy;
      }

      if (next.width < minSize) {
        if (interaction.corner.indexOf("w") !== -1) {
          next.x = next.x - (minSize - next.width);
        }
        next.width = minSize;
      }
      if (next.height < minSize) {
        if (interaction.corner.indexOf("n") !== -1) {
          next.y = next.y - (minSize - next.height);
        }
        next.height = minSize;
      }
    }

    next.width = Math.min(next.width, size.width);
    next.height = Math.min(next.height, size.height);
    next.x = clamp(next.x, 0, size.width - next.width);
    next.y = clamp(next.y, 0, size.height - next.height);

    areas[interaction.field] = pixelsToArea(next);
    renderField(interaction.field);
    updateLiveValues();
  }

  function onPointerUp() {
    interaction = null;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
  }

  function roundedArea(area) {
    return {
      x: Number(area.x.toFixed(6)),
      y: Number(area.y.toFixed(6)),
      width: Number(area.width.toFixed(6)),
      height: Number(area.height.toFixed(6)),
    };
  }

  document.querySelectorAll("[data-field-btn]").forEach(function (button) {
    button.addEventListener("click", function () {
      const field = button.getAttribute("data-field-btn");
      setActiveField(field);
      ensureArea(field);
    });
  });

  document.getElementById("toggle-grid-btn").addEventListener("click", function (evt) {
    gridVisible = !gridVisible;
    evt.currentTarget.textContent = gridVisible ? "Hide Grid" : "Show Grid";
    applyGridStyle();
  });

  document.getElementById("save-template-btn").addEventListener("click", async function () {
    const missing = fields.filter(function (field) {
      return !areas[field];
    });

    if (missing.length > 0) {
      saveStatus.textContent = `Define all fields before saving. Missing: ${missing.join(", ")}`;
      return;
    }

    const payload = {
      template_name: boot.selectedTemplate,
    };
    fields.forEach(function (field) {
      payload[field] = roundedArea(areas[field]);
    });

    const response = await fetch(boot.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const result = await response.json();
    if (!response.ok) {
      saveStatus.textContent = result.error || "Failed to save template.";
      return;
    }

    saveStatus.textContent = `Saved layout for ${result.template_name}.`;
  });

  function init() {
    applyGridStyle();
    renderAll();
  }

  if (image.complete) {
    init();
  } else {
    image.addEventListener("load", init);
  }

  window.addEventListener("resize", renderAll);
})();
