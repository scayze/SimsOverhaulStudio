/* Sim Overhaul Studio - frontend */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  status: null,
  project: { name: "My Sim Overhaul", sims: {} },
  selected: null,
  tab: "identity",
  saves: [],
  save: null,
  saveLoading: false,
  tray: [],
  trayLoading: false,
  catalog: {},
  catalogMeta: null,
  gamedata: null,
  relView: "links",
  showConditions: true,
  sourceFilter: "all",
  includeBatuu: false,
  includeNpc: false,
  ageFilter: true,
  scanTimer: null,
  saveTimer: null,
  modalPick: null,
  modalMulti: false,
  modalKind: null,
};

const ITEM_DESCRIPTIONS = {
  Active: "Energized more often, loves exercise, and gets tense without activity.",
  Ambitious: "Wants promotions and big life goals; can get tense when stuck.",
  "Art Lover": "Gets strong moodlets from art and loves discussing and making art.",
  Bookworm: "Loves reading and gains fun from books and learning.",
  Bro: "Gets along easily with other bros and enjoys guy time.",
  Cheerful: "Gets happy easily and spreads good moods.",
  Childish: "Loves toys and play; can get sad when forced to be serious.",
  Clumsy: "Breaks things and trips more often, but is endearing.",
  Creative: "Inspired more often and better at creative work.",
  "Dance Machine": "Loves dancing and gets fun from music and parties.",
  Erratic: "Mood swings and unpredictable behavior.",
  Evil: "Enjoys mischief and others' misfortune.",
  "Family Oriented": "Loves family time and is great with children.",
  Foodie: "Loves cooking and eating; gets excited about good food.",
  Genius: "Learns logic and skills faster; enjoys mental challenges.",
  Gloomy: "Sad more often, but gets creative boosts from melancholy.",
  Glutton: "Loves eating and can eat more without gaining weight.",
  Goofball: "Loves jokes and playful interactions.",
  Good: "Kind, helpful, and upset by mean behavior.",
  "Hates Children": "Dislikes children and family interactions.",
  "Hates Outdoors": "Dislikes being outside and outdoor activities.",
  "Hot-Headed": "Gets angry easily and has strong angry moodlets.",
  Jealous: "Gets jealous when their partner talks to others.",
  Kleptomaniac: "Can swipe items and enjoys mischief.",
  Lazy: "Gets tense from exercise and loves relaxing.",
  Loner: "Needs alone time and gets drained by crowds.",
  "Loves Outdoors": "Happy outside and enjoys fishing, gardening, and exploring.",
  "Music Lover": "Gets moodlets from music and loves playing instruments.",
  Neat: "Cleans automatically and dislikes messes.",
  Noncommittal: "Avoids commitment and gets tense in serious relationships.",
  Outgoing: "Loves socializing and gets energy from being around others.",
  Perfectionist: "Wants things done perfectly and works carefully.",
  Romantic: "Loves romance and flirty interactions.",
  "Self-Assured": "Confident and rarely embarrassed.",
  "Self-Deprecating": "Makes jokes at their own expense and doubts themselves.",
  Slob: "Doesn't mind messes and hates cleaning.",
  Snob: "Loves expensive things and looks down on cheap items.",
  Unflirty: "Dislikes flirting and romantic gestures.",
  Vegetarian: "Prefers vegetarian food and gets unhappy eating meat.",
  "Family Sim": "Reward trait: especially family-focused.",
  Muser: "Reward trait: stronger creative boosts when inspired.",
  "Business Savvy": "Reward trait: better at business and money-making.",
  "Painter Extraordinaire": "Aspiration: master painting and become a famous artist.",
  "Bestselling Author": "Aspiration: write great books and become a famous author.",
  "Musical Genius": "Aspiration: master instruments and become a music legend.",
  "Admired Icon": "Aspiration: become famous and adored by fans.",
  Soulmate: "Aspiration: find and keep a perfect romantic partner.",
  "Big Happy Family": "Aspiration: raise a large, close family.",
  "Successful Lineage": "Aspiration: build a family legacy across generations.",
  "Computer Whiz": "Aspiration: master computers and programming.",
  "Nerd Brain": "Aspiration: become a well-rounded genius.",
  "Renaissance Sim": "Aspiration: master several different skills.",
  "Fabulously Wealthy": "Aspiration: earn a huge fortune.",
  "Mansion Baron": "Aspiration: build and own a grand mansion.",
  "Freelance Botanist": "Aspiration: master gardening and nature.",
  "The Curator": "Aspiration: complete collections.",
  "Angling Ace": "Aspiration: catch every fish and master fishing.",
  "Master Chef": "Aspiration: master cooking and gourmet food.",
  "Master Mixologist": "Aspiration: master drinks and bartending.",
  "Public Enemy": "Aspiration: become a famous criminal.",
  "Chief of Mischief": "Aspiration: master mischief and pranks.",
  "Serial Romantic": "Aspiration: date many sims without settling down.",
  Player: "Aspiration: break hearts and master romance.",
  "Child Cool Kid": "Child aspiration: become the coolest kid on the block.",
  "Nature Critter Hunter": "Aspiration: find and befriend every critter in the world.",
  "Country Caretaker": "Aspiration: run a self-sufficient farm and care for animals.",
  "Championship Rider": "Aspiration: train horses and become a champion rider.",
  "Crystal Crafter": "Aspiration: master crystal crafting and collect crystals.",
  "Beach Life": "Aspiration: live a relaxed life by the ocean.",
  "City Native": "Aspiration: experience everything city life offers.",
  Academic: "Aspiration: become a top student and respected scholar.",
  "Appliance Wiz": "Aspiration: master handiness and household appliances.",
};

const AGE_OPTIONS = ["Baby", "Toddler", "Child", "Teen", "Young Adult", "Adult", "Elder"];
const GENDER_OPTIONS = ["Female", "Male", "Non-binary"];
const OCCULT_OPTIONS = ["Human", "Vampire", "Spellcaster", "Werewolf", "Mermaid", "Alien", "Ghost", "Fairy"];

function maskStyle(mask) {
  if (!mask) return "";
  return `-webkit-mask-image:url('${mask}');mask-image:url('${mask}');-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function initials(first, last) {
  return `${(first || "?")[0] || "?"}${(last || "")[0] || ""}`.toUpperCase();
}
function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return "§" + Number(value).toLocaleString("en-US");
}
function simByKey(key) {
  const saveSim = (state.save?.sims || []).find((s) => s.key === key);
  if (saveSim) return saveSim;
  return (state.tray || []).flatMap((h) => h.sims).find((s) => s.key === key);
}
function currentSim() {
  return state.selected ? state.project.sims[state.selected] : null;
}
function gameMark(item) {
  return "";
}

const PORTRAIT_CACHE = new Map();
const _IMG_CACHE = new Map();
function loadImage(src) {
  if (_IMG_CACHE.has(src)) return _IMG_CACHE.get(src);
  const p = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("image failed"));
    img.src = src;
  });
  _IMG_CACHE.set(src, p);
  return p;
}

function portraitInfo(sim) {
  const cropped = PORTRAIT_CACHE.get(sim.key);
  if (cropped) return { src: cropped, mask: "", cropped: true };
  return { src: sim.image || "", mask: sim.image_mask || "", cropped: false };
}

async function ensurePortrait(sim) {
  if (!sim.portrait_crop || !sim.image || PORTRAIT_CACHE.has(sim.key)) return;
  try {
    const [img, mask] = await Promise.all([
      loadImage(sim.image),
      sim.image_mask ? loadImage(sim.image_mask).catch(() => null) : Promise.resolve(null),
    ]);
    const [x0, y0, x1, y1] = sim.portrait_crop;
    const cw = Math.max(1, x1 - x0), ch = Math.max(1, y1 - y0);
    const scale = Math.min(1, 320 / ch);
    const W = Math.max(1, Math.round(cw * scale)), H = Math.max(1, Math.round(ch * scale));
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, x0, y0, cw, ch, 0, 0, W, H);
    if (mask) {
      ctx.globalCompositeOperation = "destination-in";
      ctx.drawImage(mask, x0, y0, cw, ch, 0, 0, W, H);
    }
    PORTRAIT_CACHE.set(sim.key, canvas.toDataURL("image/png"));
  } catch (err) {
    PORTRAIT_CACHE.set(sim.key, "");
  }
}

async function preparePortraits() {
  const sims = Object.values(state.project.sims || {}).filter(
    (s) => s.portrait_crop && s.image && !PORTRAIT_CACHE.has(s.key)
  );
  if (!sims.length) return;
  await Promise.all(sims.map(ensurePortrait));
  renderSidebar();
  renderStage();
}
function isPartnerLabel(label) {
  return ["Spouse", "Partner", "Fiancé(e)", "Steady", "Fiancée", "Husband", "Wife"].includes(label || "");
}
function relationMeta(f) {
  // Normalised links from the game templates carry full metadata; manual /
  // placeholder links fall back to a small local map.
  if (!f) return { label: "Relative", inverse: "Relative", generation: 0, category: "relative" };
  if (f.generation !== undefined && f.category) {
    return { label: f.relation, inverse: f.inverse || "Relative", generation: f.generation, category: f.category };
  }
  const known = {
    Parent: ["Parent", "Child", 1, "parent"], Mother: ["Mother", "Child", 1, "parent"], Father: ["Father", "Child", 1, "parent"],
    Child: ["Child", "Parent", -1, "child"], Son: ["Son", "Parent", -1, "child"], Daughter: ["Daughter", "Parent", -1, "child"],
    Sibling: ["Sibling", "Sibling", 0, "sibling"], Brother: ["Brother", "Sibling", 0, "sibling"], Sister: ["Sister", "Sibling", 0, "sibling"],
    "Half-Sibling": ["Half-Sibling", "Half-Sibling", 0, "sibling"],
    Spouse: ["Spouse", "Spouse", 0, "partner"], Partner: ["Partner", "Partner", 0, "partner"],
    "Fiancé(e)": ["Fiancé(e)", "Fiancé(e)", 0, "partner"], Steady: ["Steady", "Steady", 0, "partner"],
    Grandparent: ["Grandparent", "Grandchild", 2, "grandparent"], Grandchild: ["Grandchild", "Grandparent", -2, "grandchild"],
    Cousin: ["Cousin", "Cousin", 0, "cousin"], "Aunt / Uncle": ["Aunt / Uncle", "Niece / Nephew", 1, "collateral"],
    "Niece / Nephew": ["Niece / Nephew", "Aunt / Uncle", -1, "collateral"],
  };
  const hit = known[f.relation] || [f.relation || "Relative", "Relative", 0, "relative"];
  return { label: hit[0], inverse: hit[1], generation: hit[2], category: hit[3] };
}
function generationLabel(gen, category) {
  if (gen >= 3) return "Great-Grandparent";
  if (gen === 2) return "Grandparent";
  if (gen === 1) return category === "collateral" ? "Aunt / Uncle" : "Parent";
  if (gen === -1) return category === "collateral" ? "Niece / Nephew" : "Child";
  if (gen === -2) return "Grandchild";
  if (gen <= -3) return "Great-Grandchild";
  if (category === "sibling") return "Sibling";
  if (category === "partner") return "Partner";
  if (category === "cousin") return "Cousin";
  return "Relative";
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("The studio server did not respond in time.");
    }
    if (err instanceof TypeError || String(err.message).includes("fetch")) {
      throw new Error("Cannot reach the studio server. Keep the black Sim Overhaul Studio window open, then retry.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

function showOffline(err) {
  const app = document.querySelector("#app");
  if (!app) return;
  app.innerHTML = `
    <div class="offline-screen">
      <div class="offline-card">
        <span class="plumbob"></span>
        <h1>Waiting for the studio server</h1>
        <p>${esc(err.message || "Cannot reach the studio server.")}</p>
        <p class="muted">Keep the black <strong>Sim Overhaul Studio</strong> console window open while you use the studio. If you closed it, run <strong>Start Studio.bat</strong> again.</p>
        <div class="progress-wrap" style="margin:18px 0">
          <div class="progress-bar"><span style="width:35%"></span></div>
        </div>
        <button class="btn primary" onclick="location.reload()">Retry now</button>
      </div>
    </div>`;
  const retry = async () => {
    try {
      await fetch("/api/status", { cache: "no-store" });
      location.reload();
    } catch {
      setTimeout(retry, 2500);
    }
  };
  setTimeout(retry, 2500);
}

function toast(message, kind = "") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast ${kind}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 4200);
}

/* ------------------------------------------------------------------ startup */
async function boot() {
  bindGlobal();
  try {
    state.status = await api("/api/status");
    state.saves = state.status.saves || [];
    state.catalogMeta = state.status.catalog?.meta || null;
    state.project = await api("/api/project");
    try {
      state.gamedata = await api("/api/gamedata");
    } catch {
      state.gamedata = { condition_guide: [], career_groups: [], majors: [], university_jobs: [], career_branches: {}, relations: {} };
    }
    state.selected = Object.keys(state.project.sims || {})[0] || null;
    state.project.dynasties = state.project.dynasties || [];
    $("#project-name").value = state.project.name || "My Sim Overhaul";
    renderAll();
    renderPaths();
    preparePortraits();
    if (!state.status.catalog.cached) {
      openScanModal(true);
      startScan();
    } else {
      pollScanOnce();
    }
  } catch (err) {
    showOffline(err);
  }
}

function bindGlobal() {
  $$("#tabs .tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      state.tab = tab.dataset.tab;
      $$("#tabs .tab").forEach((t) => t.classList.toggle("active", t === tab));
      renderEditor();
    })
  );

  $("#sim-search").addEventListener("input", renderSidebar);
  $("#sim-search-clear")?.addEventListener("click", () => {
    const input = $("#sim-search");
    input.value = "";
    renderSidebar();
    input.focus();
  });
  const newBtn = $("#new-project-btn");
  if (newBtn) newBtn.addEventListener("click", openNewProject);
  $("#clear-project").addEventListener("click", clearProject);
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

  $("#export-btn").addEventListener("click", doExport);
  $("#export-btn-2").addEventListener("click", doExport);
  $$("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.dataset.open;
      if (kind === "saves") openSavesModal();
      if (kind === "tray") openTrayModal();
      if (kind === "scan") openScanModal(false);
    });
  });

  $("#project-name").addEventListener("change", (e) => {
    state.project.name = e.target.value.trim() || "My Sim Overhaul";
    queueSave();
    renderSummary();
  });

  const editor = $("#editor");
  editor.addEventListener("click", onEditorClick);
  editor.addEventListener("input", onEditorInput);
  $("#sim-list").addEventListener("click", onSidebarClick);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "e") { e.preventDefault(); doExport(); }
  });
}

/* ------------------------------------------------------------------- render */
function renderAll() {
  renderSidebar();
  renderStage();
  renderEditor();
  renderSummary();
}

function renderSidebar() {
  const query = ($("#sim-search").value || "").toLowerCase();
  const sims = Object.values(state.project.sims || {});
  $("#sim-count").textContent = sims.length;

  const filtered = sims.filter((s) => {
    const text = `${s.first} ${s.last} ${s.household}`.toLowerCase();
    return !query || text.includes(query);
  });

  const groups = {};
  filtered.forEach((s) => {
    const key = s.household_key || s.household || s.last || "Household";
    (groups[key] ||= []).push(s);
  });

  const nameCounts = {};
  Object.values(groups).forEach((rows) => {
    const name = rows[0].household || rows[0].last || "Household";
    nameCounts[name] = (nameCounts[name] || 0) + 1;
  });

  const list = $("#sim-list");
  const keys = Object.keys(groups).sort((a, b) => {
    const an = groups[a][0].household || "";
    const bn = groups[b][0].household || "";
    return an.localeCompare(bn);
  });
  list.innerHTML = keys
    .map((group) => {
      const first = groups[group][0];
      const name = first.household || first.last || "Household";
      let label = name;
      if (nameCounts[name] > 1) {
        const suffix = String(first.source_ref || "").slice(-5).replace(/^0x/, "");
        label = `${name} · ${suffix || "project"}`;
      }
      const rows = groups[group]
        .sort((a, b) => `${a.first}${a.last}`.localeCompare(`${b.first}${b.last}`))
        .map(
          (sim) => {
            const pic = portraitInfo(sim);
            return `
        <div class="sim-row ${sim.key === state.selected ? "active" : ""}" data-sim="${esc(sim.key)}">
          <div class="mini-avatar ${pic.src ? "has-photo" : ""}">${pic.src ? `<img class="portrait-img" src="${esc(pic.src)}" style="${maskStyle(pic.mask)}" alt="" />` : esc(initials(sim.first, sim.last))}</div>
          <div class="who">
            <strong>${esc(sim.first)} ${esc(sim.last)}</strong>
            <span>${esc(sim.age || "Adult")}${sim.occult && sim.occult !== "Human" ? " · " + esc(sim.occult) : ""}</span>
          </div>
          <div class="row-actions">
            <button class="row-menu" data-sim-menu="${esc(sim.key)}" title="Sim options">⋯</button>
            <button class="del" data-del="${esc(sim.key)}" title="Remove">✕</button>
          </div>
        </div>`;
          }
        )
        .join("");
      return `<div class="hh-label">${first.household_image ? `<img class="hh-img" src="${esc(first.household_image)}" style="${maskStyle(first.household_image_mask)}" alt="" />` : ""}<span>${esc(label)}</span><button class="hh-del" data-del-hh="${esc(group)}" title="Delete entire household">✕</button></div>${rows}`;
    })
    .join("");

  $("#sidebar-empty").classList.toggle("hidden", keys.length > 0);
}

function ageIcon(age) {
  const map = {
    Baby: "Age1.png",
    Toddler: "Age1.png",
    Child: "Age2.png",
    Teen: "Age3.png",
    "Young Adult": "Age4.png",
    Adult: "Age4.png",
    Elder: "Age5.png",
  };
  return "sims%202/_norm/" + (map[age] || "Age4.png");
}

function genderIcon(gender) {
  if (gender === "Male") return "sims%202/_norm/Male.png";
  if (gender === "Female") return "sims%202/_norm/Female.png";
  return "sims%202/_norm/Female.png";
}

function occultIcon(occult) {
  const life = {
    Vampire: "Vampire.png",
    Werewolf: "Werewolf.png",
    Spellcaster: "Spellcaster.png",
    Mermaid: "Mermaid.png",
    Alien: "Alien.png",
    Ghost: "Ghost.png",
    PlantSim: "PlantSim.png",
    Servo: "Servo.png",
    Fairy: "Fairy.png",
  };
  if (life[occult]) {
    return "sims%204/_pack/Misc%20Traits/Life%20States/" + encodeURIComponent(life[occult]);
  }
  const map = {
    Human: "human.png",
    Zombie: "Zombie.ico",
  };
  return map[occult] || "human.png";
}

function qualityBadge(sim) {
  const q = sim.data_quality || (sim.source === "save" ? "names" : "manual");
  if (q === "full") return `<span class="quality-badge full">Game data</span>`;
  if (q === "tray_match") return `<span class="quality-badge match">Tray match</span>`;
  if (q === "names") return `<span class="quality-badge names">Name only</span>`;
  return "";
}

function renderStage() {
  const sim = currentSim();
  const art = state.save?.thumbnail;
  const artEl = $("#stage-art");
  if (artEl) artEl.style.backgroundImage = art && sim ? `url('${art}')` : "none";

  if (!sim) {
    $("#sim-household").textContent = "No sim selected";
    $("#sim-name").textContent = "Choose a sim";
    $("#sim-badges").innerHTML = `<span class="badge">Add a sim to begin</span>`;
    $("#avatar-initials").textContent = "?";
    $("#avatar").classList.remove("has-photo");
    $("#avatar").style.backgroundImage = "none";
    const noAvatarImg = $("#avatar-img");
    if (noAvatarImg) { noAvatarImg.src = ""; noAvatarImg.style.cssText = ""; }
    $("#stage-stats").innerHTML = `<div class="stat"><img src="/icons/Aspiration2.png" alt="" /><span>Funds</span><strong>—</strong></div><div class="stat"><img src="/icons/Aspiration.ico" alt="" /><span>Traits</span><strong>0</strong></div><div class="stat"><img src="/icons/buy_hobbies_knowledge.png" alt="" /><span>Skills</span><strong>0</strong></div>`;
    return;
  }
  $("#sim-household").textContent = sim.household || sim.last || "Household";
  $("#sim-name").textContent = `${sim.first} ${sim.last}`;
  const avatar = $("#avatar");
  const avatarImg = $("#avatar-img");
  const pic = portraitInfo(sim);
  if (pic.src) {
    avatarImg.src = pic.src;
    avatarImg.style.cssText = maskStyle(pic.mask);
    avatar.classList.add("has-photo");
  } else {
    avatarImg.src = "";
    avatarImg.style.cssText = "";
    avatar.classList.remove("has-photo");
  }
  avatar.classList.toggle("household-photo", !pic.cropped && sim.image_kind === "household");
  avatar.classList.toggle("cropped-photo", pic.cropped);
  avatar.style.backgroundImage = "none";
  $("#avatar-initials").textContent = initials(sim.first, sim.last);

  const badges = [
    `<span class="badge blue"><img class="badge-ico ico-age" src="/icons/${ageIcon(sim.age)}" alt="" />${esc(sim.age || "Adult")}</span>`,
    `<span class="badge"><img class="badge-ico ${sim.gender === "Male" ? "ico-male" : "ico-female"}" src="/icons/${genderIcon(sim.gender)}" alt="" />${esc(sim.gender || "Female")}${sim.pronouns ? ` (${esc(sim.pronouns)})` : ""}</span>`,
    `<span class="badge ${sim.occult && sim.occult !== "Human" ? "purple" : "green"}"><img class="badge-ico ico-occult" src="/icons/${occultIcon(sim.occult)}" alt="" />${esc(sim.occult || "Human")}</span>`,
    qualityBadge(sim),
  ];
  if ((sim.traits || []).some((t) => t.modded) || (sim.skills || []).some((t) => t.modded)) {
    badges.push(`<span class="badge purple"><img class="mod-icon" src="/icons/x_mods.png" alt="MOD" /> Modded content</span>`);
  }
  $("#sim-badges").innerHTML = badges.join("");
  $("#stage-stats").innerHTML = `
    <div class="stat"><img src="/icons/Aspiration2.png" alt="" /><span>Funds</span><strong>${money(sim.funds)}</strong></div>
    <div class="stat"><img src="/icons/Aspiration.ico" alt="" /><span>Traits</span><strong>${(sim.traits || []).length}</strong></div>
    <div class="stat"><img src="/icons/buy_hobbies_knowledge.png" alt="" /><span>Skills</span><strong>${(sim.skills || []).length}</strong></div>`;
}

function renderEditor() {
  const sim = currentSim();
  const editor = $("#editor");
  if (!sim) {
    editor.innerHTML = `<div class="empty-stage">
      <span class="plumbob"></span>
      <h2>No sim loaded</h2>
      <p>Open <strong>Saves</strong> or <strong>Tray</strong> to add sims to this overhaul project.</p>
      <button class="btn primary" onclick="document.querySelector('[data-open=saves]').click()">Browse Saves</button>
    </div>`;
    return;
  }
  const renderers = {
    identity: renderIdentity,
    traits: renderTraits,
    skills: renderSkills,
    career: renderCareer,
    relationships: renderRelationships,
    life: renderLife,
  };
  editor.innerHTML = renderers[state.tab] ? renderers[state.tab](sim) : "";
}

const SPECIES_OPTIONS = ["Human", "Cat", "Dog", "Horse", "Fox", "Servo", "PlantSim"];

function renderIdentity(sim) {
  const pic = portraitInfo(sim);
  const pictures = (pic.src || sim.household_image)
    ? `<div class="card full">
        <h3>Pictures</h3>
        <p class="hint">The game's own picture for this sim (its household image). A sim imported from the Tray keeps its Tray portrait.</p>
        <div class="picture-row">
          ${pic.src ? `<div class="picture-box"><img src="${esc(pic.src)}" style="${maskStyle(pic.mask)}" alt="${esc(sim.first)} ${esc(sim.last)}" /><span>${esc(sim.first)} ${esc(sim.last)}</span></div>` : ""}
          ${sim.household_image && sim.household_image !== pic.src ? `<div class="picture-box"><img src="${esc(sim.household_image)}" style="${maskStyle(sim.household_image_mask)}" alt="${esc(sim.household)} household" /><span>${esc(sim.household)} household</span></div>` : ""}
        </div>
        ${sim.lot ? `<div class="sum-item" style="margin-top:10px"><span>Home lot</span><strong>${esc(sim.lot)}</strong></div>` : ""}
        ${sim.household_description ? `<p class="hint" style="margin-top:8px">${esc(sim.household_description)}</p>` : ""}
      </div>`
    : "";
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Identity &amp; household</h3>
      <p class="hint">Names are used to match the sim when the exported mod runs. Keep them exactly as they are in game.</p>
      <div class="row-3">
        <div class="field"><label>First name</label><input class="input" data-edit="first" value="${esc(sim.first)}" /></div>
        <div class="field"><label>Last name</label><input class="input" data-edit="last" value="${esc(sim.last)}" /></div>
        <div class="field"><label>Household</label><input class="input" data-edit="household" value="${esc(sim.household)}" /></div>
      </div>
      <div class="row-3">
        <div class="field"><label>Life stage</label>
          <select class="select" data-edit="age">${AGE_OPTIONS.map((a) => `<option ${a === sim.age ? "selected" : ""}>${a}</option>`).join("")}</select>
        </div>
        <div class="field"><label>Gender</label>
          <select class="select" data-edit="gender">${GENDER_OPTIONS.map((g) => `<option ${g === sim.gender ? "selected" : ""}>${g}</option>`).join("")}</select>
        </div>
        <div class="field"><label>Species</label>
          <select class="select" data-edit="species">${SPECIES_OPTIONS.map((s) => `<option ${s === (sim.species || "Human") ? "selected" : ""}>${s}</option>`).join("")}</select>
        </div>
      </div>
      ${sim.pronouns ? `<p class="hint">Pronouns from the install files: <strong>${esc(sim.pronouns)}</strong>${sim.frame && sim.frame !== sim.gender ? ` · physical frame: <strong>${esc(sim.frame)}</strong>` : ""}.</p>` : ""}
      <div class="row-2">
        <div class="field"><label>Occult</label>
          <select class="select" data-edit="occult">${OCCULT_OPTIONS.map((o) => `<option ${o === sim.occult ? "selected" : ""}>${o}</option>`).join("")}</select>
        </div>
        <div class="field"><label>Household funds</label>
          <input class="input" type="number" min="0" step="1000" data-edit="funds" value="${sim.funds ?? ""}" placeholder="${sim.funds == null ? "Current value is unknown — set a new amount" : "Leave blank to keep current"}" />
        </div>
      </div>
      <div class="add-line">
        <button class="btn sm" data-replace-tray>Replace data from Tray…</button>
      </div>
      ${sim._replace_undo ? `<div class="undo-banner">Last replaced from <strong>${esc(sim._replace_undo.source)}</strong><button class="btn sm ghost" data-undo-replace>Undo</button></div>` : ""}
    </div>
    ${pictures}
  </div>`;
}

function traitChips(list, kind) {
  if (!list || !list.length) return `<div class="chip-empty">Nothing added yet. Use the button below to browse your game + mods.</div>`;
  return `<div class="chips">${list
    .map((t, i) => {
      const label = kind === "milestones"
        ? (t.label || "").replace(/^(?:Life Milestone|Infant Milestones|Toddler Milestones|Milestone)\s+/i, "")
        : (t.label || "");
      return `<span class="chip ${t.modded ? "modded" : ""}">${t.icon ? `<img class="chip-ico" src="${esc(t.icon)}" alt="" />` : ""}${esc(label)}${gameMark(t)}${t.modded ? ` <img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}<button class="x" data-remove="${kind}:${i}">✕</button></span>`;
    })
    .join("")}</div>`;
}

function aspirationTrackHint(track) {
  const family = (track || "").split(" ")[0];
  const examples = {
    Popularity: "Friend of the World, Party Animal, Neighborhood Confidante",
    Knowledge: "Renaissance Sim, Computer Whiz, Nerd Brain",
    Creativity: "Painter Extraordinaire, Bestselling Author, Musical Genius",
    Love: "Soulmate, Serial Romantic, Player",
    Romance: "Soulmate, Serial Romantic, Player",
    Family: "Successful Lineage, Big Happy Family, Super Parent",
    Fortune: "Fabulously Wealthy, Mansion Baron, Business Savvy",
    Athletic: "Bodybuilder, Fitness Nut",
    Nature: "Freelance Botanist, The Curator, Angling Ace",
    Food: "Master Chef, Master Mixologist",
    Deviance: "Public Enemy, Chief of Mischief, Sleight of Hand",
    Mental: "Whiz Kid / child mental aspirations",
  };
  return examples[family] || "";
}

function renderTraits(sim) {
  const removed = (sim.remove_traits || []).length
    ? `<div class="removed-block">
        <div class="removed-head">Will be removed when the mod runs <button class="btn sm ghost" data-clear="remove_traits">Clear</button></div>
        <div class="chips">${sim.remove_traits
          .map((t, i) => `<span class="chip removed-chip">${t.icon ? `<img class="chip-ico" src="${esc(t.icon)}" alt="" />` : ""}${esc(t.label)}<button class="x" data-restore-trait="${i}" title="Keep this trait">↺</button></span>`)
          .join("")}</div>
      </div>`
    : "";
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Personality traits</h3>
      <p class="hint">Removing a trait from a clean-save sim adds it to the remove list below, so the exported mod takes it away in game. Traits you add here are applied on top.</p>
      ${traitChips(sim.traits, "traits")}
      <div class="add-line">
        <button class="btn sm" data-add="traits">+ Add trait</button>
        <button class="btn sm ghost" data-clear="traits">Clear all</button>
      </div>
      ${removed}
    </div>
    <div class="card full">
      <h3>Aspiration</h3>
      <p class="hint">One aspiration per sim. Replaces the sim's current aspiration when the mod runs.</p>
      ${sim.aspiration ? `<div class="chips"><span class="chip ${sim.aspiration.modded ? "modded" : ""}">${sim.aspiration.icon ? `<img class="chip-ico" src="${esc(sim.aspiration.icon)}" alt="" />` : ""}${esc(sim.aspiration.label)}${sim.aspiration.modded ? ` <img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}<button class="x" data-remove="aspiration:0">✕</button></span></div>` : sim.aspiration_track ? `<div class="chip-empty">Aspiration track: <strong>${esc(sim.aspiration_track)}</strong>. The install files store the track only, not the specific aspiration.${aspirationTrackHint(sim.aspiration_track) ? ` Track options: ${esc(aspirationTrackHint(sim.aspiration_track))}.` : ""}</div>` : `<div class="chip-empty">No aspiration selected.</div>`}
      <div class="add-line"><button class="btn sm" data-add="aspirations">Choose aspiration</button></div>
    </div>
  </div>`;
}

function renderSkills(sim) {
  const rows = (sim.skills || [])
    .map((s, i) => {
      const unknown = s.level_unknown || s.level === null || s.level === undefined;
      const level = unknown ? 1 : s.level;
      return `
    <div class="skill-row">
      <div class="skill-name">${s.icon ? `<img class="chip-ico" src="${esc(s.icon)}" alt="" />` : ""}${esc(s.label)} ${gameMark(s)} ${s.modded ? `<img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}</div>
      <div class="slider-wrap">
        <input type="range" min="0" max="10" step="1" value="${level}" data-skill="${i}" style="--pct:${(level / 10) * 100}%" />
        <span class="level-pill" data-level="${i}" ${unknown ? 'title="Level not stored in the install template"' : ""}>${unknown ? "?" : level}</span>
      </div>
      <button class="btn sm ghost" data-remove="skills:${i}">✕</button>
    </div>`;
    })
    .join("");
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Skills</h3>
      <p class="hint">Drag to set the skill level. Levels are derived from the template's XP values using the game XP curve. Levels marked <strong>?</strong> are not stored in the install template. Hidden or pack-locked skills are skipped safely.</p>
      ${rows || `<div class="chip-empty">No skills added yet.</div>`}
      <div class="add-line">
        <button class="btn sm" data-add="skills">+ Add skill</button>
        <button class="btn sm ghost" data-clear="skills">Clear all</button>
      </div>
    </div>
  </div>`;
}

function isMainCareerTrack(item) {
  const text = `${item.tuning || ""} ${item.label || ""}`.toLowerCase();
  return /(^|[_\s])track1([_\s]|$)|(^|[_\s])(main|basic)([_\s]|$)/.test(text);
}

function suggestedBranchFamily(careerLabel) {
  const families = Object.keys(state.gamedata?.career_branches || {});
  const low = (careerLabel || "").toLowerCase();
  if (!low) return "";
  const first = low.split(/\s+/)[0];
  return (
    families.find((f) => f.toLowerCase() === low) ||
    families.find((f) => f.toLowerCase().startsWith(first)) ||
    families.find((f) => low.startsWith(f.toLowerCase().split(" ")[0])) ||
    ""
  );
}

function renderCareer(sim) {
  const family = suggestedBranchFamily(sim.career?.label);
  const tracks = (state.gamedata?.career_branches || {})[family] || [];
  const isStudent = !!sim.career?.university_student;
  // A career only has specialisations if the game data actually defines
  // branches for it; the level comes from gamedata when known.
  const levels = state.gamedata?.branch_levels || {};
  const branchLevel = levels[family] || state.gamedata?.branch_level || 5;
  const hasBranches = isStudent || tracks.some((t) => !t.main);
  const level = sim.career?.level ?? 1;
  const canBranch = !!sim.career && hasBranches && (isStudent || level >= branchLevel);
  const pct = ((level - 1) / 9) * 100;
  const specialisation = sim.career_track
    ? `<span class="chip ${canBranch ? "" : "locked-chip"}">${esc(sim.career_track.label)}${canBranch ? `<button class="x" data-remove="career_track:0">✕</button>` : `<span class="chip-lock" title="Applies at level ${branchLevel}">🔒</span>`}</span>`
    : "";
  let branchBody;
  if (!sim.career) {
    branchBody = `<span class="chip-empty">Choose a career first.</span>`;
  } else if (!hasBranches) {
    branchBody = `<div class="branch-locked">This career has no specialisations — the game does not branch it.</div>`;
  } else if (!canBranch) {
    branchBody = `<div class="branch-locked"><strong>Specialisations unlock at career level ${branchLevel}.</strong> This sim is at level ${level} — raise the level first.</div>`;
  } else {
    branchBody = `<div class="chips">${specialisation || `<span class="chip-empty">No ${isStudent ? "course slots" : "specialisation"} chosen yet.</span>`}</div>`;
  }
  const branchBtn = !sim.career || !hasBranches
    ? ""
    : canBranch
      ? `<button class="btn sm ghost" data-open-branches="${esc(isStudent ? "university" : family)}">Choose ${isStudent ? "course slots" : "specialisation"}</button>`
      : `<button class="btn sm ghost" disabled title="Reach level ${branchLevel} first">Choose ${isStudent ? "course slots" : "specialisation"} 🔒</button>`;
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Career</h3>
      <p class="hint">${isStudent
        ? "University enrolment gives four course slots; choose them here. They are always available while the sim is a student."
        : `In game a career runs from level 1 to 10. Careers that branch split into <strong>specialisations</strong> at level ${branchLevel}; careers without branches don't offer one. It stays locked until that level is reached.`}</p>
      ${!sim.career && sim.game_dynasty
        ? `<p class="hint">No career is stored in the install template for this dynasty sim. Noble/career roles can be assigned by runtime systems after the save starts.</p>`
        : ""}
      ${
        sim.career
          ? `<div class="chips"><span class="chip ${sim.career.modded ? "modded" : ""}">${sim.career.icon ? `<img class="chip-ico" src="${esc(sim.career.icon)}" alt="" />` : ""}${esc(sim.career.label)}${sim.career.modded ? ` <img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}<button class="x" data-remove="career:0">✕</button></span></div>
              <div class="field" style="margin-top:16px"><label>Career level</label>
                <div class="slider-wrap career-slider">
                  <input type="range" min="1" max="10" step="1" value="${level}" data-career-level style="--pct:${pct}%" />
                  <span class="level-pill">${level}</span>
                </div>
              </div>`
          : `<div class="chip-empty">No career selected.</div>`
      }
      <div class="add-line">
        <button class="btn sm" data-add="careers">Choose career</button>
        ${branchBtn}
      </div>
      <div class="field" style="margin-top:14px"><label>${isStudent ? "Course slots" : "Specialisation"}</label><div id="branch-area">${branchBody}</div></div>
    </div>
    <div class="card full">
      <h3>University degrees</h3>
      <p class="hint">Discover University stores degrees as traits. Degrees are grouped by major in the catalog (standard and Honours BA/BS). You can also enrol as an active university student by choosing <strong>University student (active)</strong> in the career catalog.</p>
      ${traitChips(sim.degrees, "degrees")}
      <div class="add-line"><button class="btn sm" data-add="degrees">+ Add degree</button></div>
    </div>
  </div>`;
}

function relationshipRow(sim, rel, index) {
  const target = state.project.sims[rel.target];
  const name = target ? `${target.first} ${target.last}` : rel.target;
  const bits = (rel.bits || [])
    .map(
      (b, bi) =>
        `<span class="chip mini-chip">${esc(b.label)}${b.modded ? ` <img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}<button class="x" data-remove-bit="${index}:${bi}">✕</button></span>`
    )
    .join("");
  return `
    <div class="rel-row">
      <div class="rel-who"><img class="rel-ico" src="/icons/${relationIcon(rel.label)}" alt="" />${esc(name)}<small>${target ? esc(target.household) : "Not in project"}${rel.label ? ` · ${esc(rel.label)}` : ""}</small></div>
      <div class="rel-slider friend">
        <label>Friendship <span>${rel.friendship ?? 0}</span></label>
        <input type="range" min="-100" max="100" step="1" value="${rel.friendship ?? 0}" data-rel="${index}" data-field="friendship" style="--pct:${(((rel.friendship ?? 0) + 100) / 200) * 100}%" />
      </div>
      <div class="rel-slider romance">
        <label>Romance <span>${rel.romance ?? 0}</span></label>
        <input type="range" min="-100" max="100" step="1" value="${rel.romance ?? 0}" data-rel="${index}" data-field="romance" style="--pct:${(((rel.romance ?? 0) + 100) / 200) * 100}%" />
      </div>
      <button class="btn sm ghost" data-remove="relationships:${index}">✕</button>
      <div class="rel-bits">
        ${bits || `<span class="muted-xs">No relationship bits or sentiments</span>`}
        <button class="btn sm ghost" data-add-bit="${index}">+ Bit / Sentiment</button>
      </div>
    </div>`;
}

function relativeRow(targetKey, relationLabel, depth = 0) {
  const target = state.project.sims[targetKey];
  if (!target) return "";
  return `<div class="ftree-row" data-tree-sim="${esc(targetKey)}" style="margin-left:${Math.min(depth, 3) * 16}px">
    <img class="rel-ico" src="/icons/${relationIcon(relationLabel)}" alt="" />
    <strong>${esc(target.first)} ${esc(target.last)}</strong>
    <span class="badge blue">${esc(relationLabel)}</span>
    <small>${esc(target.household || "")}</small>
  </div>`;
}

function renderLinksView(sim) {
  const others = Object.keys(state.project.sims).filter((k) => k !== sim.key);
  const rels = (sim.relationships || []).map((r, i) => relationshipRow(sim, r, i)).join("");
  const partnerLinks = (sim.relationships || [])
    .map((r, i) => ({ ...r, index: i }))
    .filter((r) => isPartnerLabel(r.label));
  const secretsCard = (sim.secrets || []).length
    ? `<div class="card full">
        <h3>Secrets <span class="badge">${sim.secrets.length}</span></h3>
        <p class="hint">Hidden connections seeded by the game's <code>SimInfoFixup</code> tunings. They are secrets, not friendship or romance scores.</p>
        <div class="secret-list">${sim.secrets.map((s) => `<div class="secret-row">
          <strong>${esc(s.label || "Secret")}</strong>
          ${s.target ? `<span class="badge blue">${esc(s.target)}</span>` : ""}
          ${s.target_key ? `<button class="btn sm ghost" data-dyn-sim="${esc(s.target_key)}">View sim</button>` : ""}
        </div>`).join("")}</div>
      </div>`
    : "";
  const family =
    (sim.family || [])
      .map((f, i) => {
        const target = state.project.sims[f.target];
        return `<div class="rel-row">
          <div class="rel-who"><img class="rel-ico" src="/icons/${relationIcon(f.relation)}" alt="" />${esc(target ? `${target.first} ${target.last}` : f.target)}<small>Family tree${f.from_game ? " · from game files" : ""}</small></div>
          <div class="rel-who"><span class="badge blue">${esc(f.relation)}</span>${f.source === "inferred" ? `<span class="badge" title="Inferred from tuning family trope, not explicit genealogy">Inferred</span>` : ""}</div>
          <div></div>
          <button class="btn sm ghost" data-remove="family:${i}">✕</button>
        </div>`;
      })
      .join("") +
    partnerLinks
      .map((r) => {
        const target = state.project.sims[r.target];
        return `<div class="rel-row">
          <div class="rel-who"><img class="rel-ico" src="/icons/${relationIcon(r.label)}" alt="" />${esc(target ? `${target.first} ${target.last}` : r.target)}<small>Partner link</small></div>
          <div class="rel-who"><span class="badge blue">${esc(r.label)}</span></div>
          <div></div>
          <button class="btn sm ghost" data-remove="relationships:${r.index}">✕</button>
        </div>`;
      })
      .join("");
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Relationships</h3>
      <p class="hint">Family links are decoded from the game's own household templates (parents, grandparents, spouses and their inverses). The specific household bits (Roommate, Lovers, Lovebirds, …), club members and the extra friendships, romances, exes and rivalries come from the game's own tuning — all are shown here. Both sims must exist when the mod runs.</p>
      ${rels || `<div class="chip-empty">No relationships yet.</div>`}
      <div class="add-line">
        <select class="select" id="rel-target" ${others.length ? "" : "disabled"}>
          <option value="">Choose a sim…</option>
          ${others.map((k) => `<option value="${esc(k)}">${esc(state.project.sims[k].first)} ${esc(state.project.sims[k].last)}</option>`).join("")}
        </select>
        <button class="btn sm" data-add="relationship" ${others.length ? "" : "disabled"}>+ Add relationship</button>
      </div>
    </div>
    ${secretsCard}
    <div class="card full">
      <h3>Family links</h3>
      <p class="hint">Every direct family link is listed once. Use the Relationships card above for friendship/romance scores and non-family relationships. Switch to <strong>Family tree</strong> or <strong>Dynasties</strong> above for the expanded view.</p>
      <div class="ftree-edit">
        ${family || `<div class="chip-empty">No direct family links yet.</div>`}
        <div class="add-connection">
          <div class="add-connection-head">Add connection</div>
          <div class="add-line">
            <select class="select" id="fam-target" ${others.length ? "" : "disabled"}>
              <option value="">Choose a sim…</option>
              ${others.map((k) => `<option value="${esc(k)}">${esc(state.project.sims[k].first)} ${esc(state.project.sims[k].last)}</option>`).join("")}
            </select>
            <select class="select" id="fam-relation" style="max-width:170px">
              <option>Parent</option><option>Child</option><option>Sibling</option>
              <option>Spouse</option><option>Fiancé(e)</option><option>Steady</option>
              <option>Grandparent</option><option>Grandchild</option>
              <option>Aunt / Uncle</option><option>Niece / Nephew</option><option>Cousin</option>
            </select>
            <button class="btn sm" data-add="family" ${others.length ? "" : "disabled"}>+ Connect</button>
          </div>
          <p class="hint">The inverse link is added automatically, and the new connection appears in the Family tree.</p>
        </div>
        <div class="add-line" style="margin-top:8px">
          <input class="input" id="ph-first" placeholder="First name" style="max-width:120px" />
          <input class="input" id="ph-last" placeholder="Last name" style="max-width:120px" />
          <select class="select" id="ph-relation" style="max-width:130px">
            <option>Parent</option><option>Child</option><option>Sibling</option><option>Spouse</option>
          </select>
          <button class="btn sm ghost" data-add-placeholder>+ Placeholder relative</button>
        </div>
      </div>
    </div>
  </div>`;
}

function collectFamilyTree(sim) {
  // Full breadth-first walk of the connected family graph. Every reachable
  // relative is placed at its generation depth relative to the selected sim.
  const byKey = state.project.sims || {};
  const depth = new Map([[sim.key, 0]]);
  const info = new Map();
  const queue = [sim.key];
  while (queue.length) {
    const cur = queue.shift();
    const curSim = byKey[cur];
    const d = depth.get(cur);
    if (!curSim) continue;
    for (const f of curSim.family || []) {
      const t = f.target;
      if (!byKey[t] || depth.has(t)) continue;
      const meta = relationMeta(f);
      depth.set(t, d + meta.generation);
      info.set(t, { label: generationLabel(d + meta.generation, meta.category), inferred: f.source === "inferred" });
      queue.push(t);
    }
    for (const r of curSim.relationships || []) {
      if (!isPartnerLabel(r.label) || !byKey[r.target] || depth.has(r.target)) continue;
      depth.set(r.target, d);
      info.set(r.target, { label: "Partner", inferred: false });
      queue.push(r.target);
    }
  }
  const rows = [];
  for (const [key, d] of depth) {
    if (key === sim.key) continue;
    const meta = info.get(key) || { label: "Relative", inferred: false };
    rows.push({ key, gen: d, depth: Math.abs(d), label: meta.label, inferred: Boolean(meta.inferred) });
  }
  rows.sort((a, b) => b.gen - a.gen || a.depth - b.depth || (a.label || "").localeCompare(b.label || ""));
  return rows;
}

function treeGroupLabel(gen) {
  if (gen >= 3) return "Great-grandparents & above";
  if (gen === 2) return "Grandparents";
  if (gen === 1) return "Parents, aunts & uncles";
  if (gen === 0) return "Same generation";
  if (gen === -1) return "Children, nieces & nephews";
  if (gen === -2) return "Grandchildren";
  return "Great-grandchildren & below";
}

function dynastyFor(simKey) {
  return (state.project.dynasties || []).find((d) => (d.members || []).includes(simKey)) || null;
}

function treeNodeCard(key, label, isSelf = false, inferred = false) {
  const m = state.project.sims[key];
  if (!m) return "";
  const pic = portraitInfo(m);
  const avatar = pic.src
    ? `<img class="ftree-avatar" src="${esc(pic.src)}" style="${maskStyle(pic.mask)}" alt="" />`
    : `<span class="ftree-avatar ftree-initials">${esc(initials(m.first, m.last))}</span>`;
  const dyn = dynastyFor(key);
  const role = dyn ? dynRole(dyn, key) : "";
  return `<button class="ftree-node ${isSelf ? "self" : ""}" data-tree-sim="${esc(key)}" title="${inferred ? "Inferred family edge: tuning family trope, not explicit genealogy" : ""}">
    ${avatar}
    <strong>${esc(m.first)} ${esc(m.last)}</strong>
    <span class="ftree-rel">${esc(label || "Relative")}</span>
    <small>${esc(m.household || "")}${role}${inferred ? " · inferred" : ""}</small>
  </button>`;
}

function ancestorNodeCard(a) {
  return `<div class="ftree-node ancestor">
    <span class="ftree-avatar ftree-initials">${esc(initials(a.sim || "?", ""))}</span>
    <strong>${esc(a.sim || "Ancestor")}</strong>
    <span class="ftree-rel">${esc(a.title ? `${a.title}${a.region ? ` of ${a.region}` : ""}` : "Ancestor")}</span>
    <small>${a.gender ? esc(String(a.gender).toLowerCase()) : ""}${a.death ? ` · ${esc(a.death)}` : ""}</small>
  </div>`;
}

let _treeResizeBound = false;

function drawTreeEdges() {
  const graph = document.querySelector(".ftree-graph");
  const svg = graph && graph.querySelector(".ftree-lines");
  if (!graph || !svg) return;
  const nodes = new Map();
  graph.querySelectorAll(".ftree-node[data-tree-sim]").forEach((el) => nodes.set(el.dataset.treeSim, el));
  const gr = graph.getBoundingClientRect();
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { x: r.left - gr.left + graph.scrollLeft, y: r.top - gr.top + graph.scrollTop, w: r.width, h: r.height };
  };
  const paths = [];
  const drawn = new Set();
  const parentChild = (upKeys, downKey) => {
    const ups = [...new Set(upKeys || [])].filter((k) => nodes.has(k));
    const down = nodes.get(downKey);
    if (!ups.length || !down) return;
    const id = "c:" + downKey + ":" + ups.slice().sort().join("|");
    if (drawn.has(id)) return;
    const boxes = ups.map((k) => box(nodes.get(k)));
    const b = box(down);
    const y1 = Math.max(...boxes.map((x) => x.y + x.h));
    const x1 = boxes.reduce((sum, x) => sum + x.x + x.w / 2, 0) / boxes.length;
    const x2 = b.x + b.w / 2, y2 = b.y;
    if (y2 <= y1) return;
    drawn.add(id);
    const mid = y1 + Math.max(14, (y2 - y1) / 2);
    paths.push(`<path class="ftree-edge" d="M ${x1} ${y1} V ${mid} H ${x2} V ${y2}" />`);
  };
  const partner = (aKey, bKey, solid = false) => {
    if (!aKey || !bKey || aKey === bKey) return;
    const id = "p:" + [aKey, bKey].sort().join(":");
    if (drawn.has(id)) return;
    let a = nodes.get(aKey), b = nodes.get(bKey);
    if (!a || !b) return;
    const ba = box(a), bb = box(b);
    if (bb.x < ba.x) [a, b] = [b, a];
    const a2 = box(a), b2 = box(b);
    drawn.add(id);
    paths.push(`<path class="ftree-edge ${solid ? "couple" : "partner"}" d="M ${a2.x + a2.w} ${a2.y + a2.h / 2} H ${b2.x}" />`);
  };
  for (const key of nodes.keys()) {
    const sim = state.project.sims[key];
    if (!sim) continue;
    let parents = (sim.family || [])
      .filter((f) => nodes.has(f.target) && relationMeta(f).category === "parent")
      .map((f) => f.target);
    if (!parents.length) {
      parents = (sim.family || [])
        .filter((f) => nodes.has(f.target) && relationMeta(f).category === "grandparent")
        .map((f) => f.target);
    }
    if (parents.length) parentChild(parents, key);
    for (const f of sim.family || []) {
      const meta = relationMeta(f);
      if (meta.category === "partner" && nodes.has(f.target)) partner(key, f.target, f.relation === "Spouse");
    }
    for (const r of sim.relationships || []) {
      if (isPartnerLabel(r.label) && nodes.has(r.target)) {
        partner(key, r.target, ["Spouse", "Husband", "Wife"].includes(r.label));
      }
    }
  }
  const width = graph.scrollWidth || graph.clientWidth;
  const height = graph.scrollHeight || graph.clientHeight;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = paths.join("");
}

function renderTreeView(sim) {
  const allRows = collectFamilyTree(sim);
  const dyn = dynastyFor(sim.key);
  const byKey = state.project.sims;
  const labelMap = new Map(allRows.map((r) => [r.key, r.label]));
  const inferredKeys = new Set(allRows.filter((r) => r.inferred).map((r) => r.key));
  const uniq = (list) => [...new Set(list)].filter((k) => byKey[k]);
  const partnerKeys = (key) => {
    const s = byKey[key];
    if (!s) return [];
    return uniq([
      ...(s.relationships || []).filter((r) => isPartnerLabel(r.label)).map((r) => r.target),
      ...(s.family || []).filter((f) => relationMeta(f).category === "partner").map((f) => f.target),
    ]);
  };
  const parentKeys = (key) => {
    const s = byKey[key];
    if (!s) return [];
    return uniq((s.family || [])
      .filter((f) => relationMeta(f).category === "parent" ||
        ["Father", "Mother", "Parent"].includes(f.relation))
      .map((f) => f.target));
  };
  const childKeys = (key) => {
    const s = byKey[key];
    if (!s) return [];
    return uniq((s.family || [])
      .filter((f) => relationMeta(f).category === "child" ||
        ["Child", "Son", "Daughter"].includes(f.relation))
      .map((f) => f.target));
  };
  const siblingKeys = (key) => {
    const s = byKey[key];
    if (!s) return [];
    return uniq((s.family || [])
      .filter((f) => relationMeta(f).category === "sibling" ||
        ["Sibling", "Brother", "Sister", "Half-Sibling"].includes(f.relation))
      .map((f) => f.target));
  };
  const parents = parentKeys(sim.key);
  const partners = partnerKeys(sim.key);
  const siblings = siblingKeys(sim.key).filter((k) => !partners.includes(k));
  const children = childKeys(sim.key);
  const grandparents = uniq(parents.flatMap(parentKeys));
  const grandchildren = uniq(children.flatMap(childKeys));
  const mainKeys = new Set([sim.key, ...parents, ...partners, ...siblings, ...children, ...grandparents, ...grandchildren]);
  for (const key of [...mainKeys]) {
    for (const p of partnerKeys(key)) mainKeys.add(p);
  }
  const extended = allRows.filter((r) => !mainKeys.has(r.key));
  const unitsFor = (keys) => {
    const remaining = uniq(keys);
    const used = new Set();
    const units = [];
    for (const key of remaining) {
      if (used.has(key)) continue;
      const pair = partnerKeys(key).filter((p) => !used.has(p) && byKey[p]);
      units.push([key, ...pair]);
      used.add(key);
      pair.forEach((p) => used.add(p));
    }
    return units;
  };
  const labelFor = (key) => labelMap.get(key) || (key === sim.key ? "This sim" : "Relative");
  const unitHtml = (keys, cls = "") => `<div class="ftree-unit ${cls}">${keys
    .map((k) => treeNodeCard(k, k === sim.key ? "This sim" : labelFor(k), k === sim.key, inferredKeys.has(k)))
    .join("")}</div>`;
  const rowHtml = (units) => units.length
    ? `<div class="ftree-generation">
        <div class="ftree-row">${units.map((u) => unitHtml(u)).join("")}</div>
      </div>`
    : "";
  const selfUnits = [unitHtml([sim.key, ...partners], "self-unit"), ...unitsFor(siblings).map((u) => unitHtml(u))];
  const graphRows = [
    rowHtml(unitsFor(grandparents)),
    rowHtml(unitsFor(parents)),
    selfUnits.length ? `<div class="ftree-generation">
      <div class="ftree-row">${selfUnits.join("")}</div>
    </div>` : "",
    rowHtml(unitsFor(children)),
    rowHtml(unitsFor(grandchildren)),
  ].join("");
  const hasTree = Boolean(parents.length || partners.length || siblings.length || children.length || grandparents.length || grandchildren.length);
  const ancestorMap = new Map();
  for (const a of [...((dyn && dyn.ancestors) || []), ...(sim.ancestors || [])]) {
    if (a && a.sim) ancestorMap.set(a.sim, a);
  }
  const ancestorRow = ancestorMap.size
    ? `<div class="ftree-generation">
        <div class="ftree-row">${[...ancestorMap.values()].map(ancestorNodeCard).join("")}</div>
      </div>`
    : "";
  const badge = dyn ? `<span class="badge blue">${esc(dyn.name)}</span>` : "";
  const dynastyCard = dyn && (dyn.members || []).length
    ? `<div class="card full">
        <h3>${esc(dyn.name)} <span class="badge green">In the game</span></h3>
        <p class="hint">${dyn.description ? esc(dyn.description) : "All members of this game-defined dynasty, across households."}</p>
        <div class="dyn-members">${(dyn.members || []).map((k) => {
          const m = state.project.sims[k];
          return m ? `<button class="dyn-member ${k === sim.key ? "active" : ""}" data-dyn-sim="${esc(k)}">${esc(m.first)} ${esc(m.last)}<small>${esc(m.household || "")}${dynRole(dyn, k)}</small></button>` : "";
        }).join("")}</div>
        ${dynastyExtras(dyn, false)}
      </div>`
    : "";
  const graph = (hasTree || ancestorRow)
    ? `<div class="ftree-graph">
        <svg class="ftree-lines" aria-hidden="true"></svg>
        ${ancestorRow}
        ${graphRows}
      </div>`
    : `<div class="chip-empty">No direct family links yet. Use <strong>Add connection</strong> under Family links, or create a placeholder relative, and the tree builds itself here.</div>`;
  const extendedCard = extended.length
    ? `<div class="card full">
        <h3>Extended family <span class="badge">${extended.length}</span></h3>
        <p class="hint">Aunts, uncles, cousins, nieces and nephews outside the direct tree. Click one to jump to that sim.</p>
        <div class="ftree-extended">${extended.map((r) => {
          const m = state.project.sims[r.key];
          return m ? `<button class="ftree-ext-chip" data-tree-sim="${esc(r.key)}"><strong>${esc(m.first)} ${esc(m.last)}</strong><span>${esc(r.label || "Relative")}</span><small>${esc(m.household || "")}</small></button>` : "";
        }).join("")}</div>
      </div>`
    : "";
  if (!_treeResizeBound) {
    _treeResizeBound = true;
    window.addEventListener("resize", () => drawTreeEdges());
  }
  setTimeout(drawTreeEdges, 0);
  setTimeout(drawTreeEdges, 150);
  setTimeout(drawTreeEdges, 500);
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Family tree · ${esc(sim.first)} ${esc(sim.last)} ${badge}</h3>
      <p class="hint">A direct family tree like the game: ancestors above, parents, this generation and children below. Solid lines are parent/child; dashed lines are partners. Cards marked <strong>· inferred</strong> come from tuning family tropes, not explicit genealogy. Extended relatives are listed separately.</p>
      <div class="add-line">
        <button class="btn sm ghost" data-rel-view="links">+ Add or edit connections</button>
        <span class="muted-xs">${allRows.length} relative${allRows.length === 1 ? "" : "s"}${ancestorMap.size ? ` · ${ancestorMap.size} ancestor${ancestorMap.size === 1 ? "" : "s"}` : ""}</span>
      </div>
      ${graph}
    </div>
    ${extendedCard}
    ${dynastyCard}
  </div>`;
}

const DYNASTY_ROLES = { head: "Head", heir: "Heir", "black sheep": "Black sheep" };

function dynRole(d, key) {
  const role = (d.roles || {})[key];
  return role ? ` · ${DYNASTY_ROLES[role] || role}` : "";
}

function ancestorChips(list) {
  return (list || []).map((a) => `<span class="dyn-ancestor"><strong>${esc(a.sim)}</strong>${a.title ? ` <em>${esc(a.title)}${a.region ? ` of ${esc(a.region)}` : ""}</em>` : ""}${a.gender ? `<small>${esc(String(a.gender).toLowerCase())}</small>` : ""}${a.death ? `<small>Death: ${esc(a.death)}</small>` : ""}</span>`).join("");
}

function dynastyExtras(d, includeAncestors = true) {
  const ideals = (d.ideals || []).length
    ? `<div class="dyn-meta"><span>Ideals</span>${d.ideals.map((x) => `<span class="mini-chip2">${esc(x)}</span>`).join("")}</div>`
    : "";
  const skills = (d.skills || []).length
    ? `<div class="dyn-meta"><span>Skills</span>${d.skills.map((x) => `<span class="mini-chip2">${esc(x)}</span>`).join("")}</div>`
    : "";
  const ties = [
    ...(d.allies || []).map((x) => `Ally: ${x}`),
    ...(d.rivals || []).map((x) => `Rival: ${x}`),
  ];
  const tiesHtml = ties.length
    ? `<div class="dyn-meta"><span>Ties</span>${ties.map((x) => `<span class="mini-chip2">${esc(x)}</span>`).join("")}</div>`
    : "";
  const ancestors = includeAncestors && (d.ancestors || []).length
    ? `<div class="dyn-ancestors">
        <div class="dyn-ancestor-head">Ancestors <span>${d.ancestors.length}</span></div>
        <div class="dyn-ancestor-list">${ancestorChips(d.ancestors)}</div>
      </div>`
    : "";
  return ideals + skills + tiesHtml + ancestors;
}

function renderDynastiesView(sim) {
  const dynasties = state.project.dynasties || [];
  const sims = state.project.sims || {};
  const memberChip = (key, d) => {
    const m = sims[key];
    if (!m) return "";
    return `<button class="dyn-member ${key === sim.key ? "active" : ""}" data-dyn-sim="${esc(key)}">${esc(m.first)} ${esc(m.last)}<small>${esc(m.household || "")}${dynRole(d, key)}</small></button>`;
  };
  const cards = dynasties
    .map((d, i) => {
      const head = sims[d.head];
      return `<div class="dyn-card">
        <div class="dyn-head">
          <div><strong>${esc(d.name)}</strong>${d.from_game ? `<span class="badge green">In the game</span>` : ""}<div class="hint">Head: ${esc(head ? `${head.first} ${head.last}` : "—")} · ${(d.members || []).length} members · ${d.generations || 1} generations</div>${d.description ? `<p class="hint" style="margin-top:6px">${esc(d.description)}</p>` : ""}</div>
          <div class="dyn-actions">
            <button class="btn sm ghost" data-dyn-edit="${i}">Edit</button>
            <button class="btn sm ghost" data-dyn-remove="${i}">Remove</button>
          </div>
        </div>
        <div class="dyn-members">${(d.members || []).map((k) => memberChip(k, d)).join("")}</div>
        ${dynastyExtras(d)}
      </div>`;
    })
    .join("");
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Dynasties <span class="badge">${dynasties.length}</span></h3>
      <p class="hint">These are the dynasties the game itself defines (DynastySeed tuning). Other families are never turned into dynasties. You can edit or add your own.</p>
      <div class="add-line"><button class="btn sm" data-dyn-add>+ Add dynasty</button></div>
      ${cards || `<div class="chip-empty">No dynasties in this project yet.</div>`}
    </div>
  </div>`;
}

function renderRelationships(sim) {
  const views = [
    ["links", "Links"],
    ["tree", "Family tree"],
    ["dynasties", "Dynasties"],
  ];
  const seg = `<div class="rel-seg">${views
    .map(([id, label]) => `<button class="rel-seg-btn ${state.relView === id ? "active" : ""}" data-rel-view="${id}">${label}</button>`)
    .join("")}</div>`;
  const body =
    state.relView === "tree" ? renderTreeView(sim)
    : state.relView === "dynasties" ? renderDynastiesView(sim)
    : renderLinksView(sim);
  return seg + body;
}

function openDynastyEditor(index) {
  if (!state.project.dynasties) state.project.dynasties = [];
  const list = state.project.dynasties;
  const d = index >= 0
    ? { ...list[index] }
    : { id: `dynasty:${Date.now()}`, name: "", head: "", members: [], generations: 1, from_game: false };
  const sims = Object.values(state.project.sims || {});
  const body = `
    <div class="field"><label>Name</label><input class="input" id="dyn-name" value="${esc(d.name)}" placeholder="e.g. Goth family" /></div>
    <div class="field" style="margin-top:12px"><label>Head of the dynasty</label>
      <select class="select" id="dyn-head"><option value="">— none —</option>${sims.map((s) => `<option value="${esc(s.key)}" ${s.key === d.head ? "selected" : ""}>${esc(s.first)} ${esc(s.last)}</option>`).join("")}</select>
    </div>
    <div class="field" style="margin-top:12px"><label>Members</label>
      <input class="input" id="dyn-search" placeholder="Filter sims…" style="margin-bottom:8px" />
      <div class="dyn-pick" id="dyn-members">${sims.map((s) => `<label class="toggle dyn-pick-row"><input type="checkbox" value="${esc(s.key)}" ${(d.members || []).includes(s.key) ? "checked" : ""}/> ${esc(s.first)} ${esc(s.last)} <small>${esc(s.household || "")}</small></label>`).join("")}</div>
    </div>`;
  openModal(index >= 0 ? "Edit dynasty" : "Add dynasty", body,
    `<button class="btn" id="dyn-cancel">Cancel</button><button class="btn primary" id="dyn-save">Save</button>`, true);
  $("#dyn-cancel").addEventListener("click", closeModal);
  $("#dyn-search").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    $$("#dyn-members .dyn-pick-row").forEach((row) => {
      row.style.display = !q || row.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });
  $("#dyn-save").addEventListener("click", () => {
    const name = ($("#dyn-name").value || "").trim() || "New dynasty";
    const members = $$("#dyn-members input:checked").map((x) => x.value);
    const head = $("#dyn-head").value || members[0] || "";
    const obj = { ...d, name, head, members };
    if (index >= 0) list[index] = obj; else list.push(obj);
    queueSave();
    closeModal();
    renderEditor();
    toast("Dynasty saved", "ok");
  });
}

function renderLife(sim) {
  return `
  <div class="editor-grid">
    <div class="card full">
      <h3>Milestones</h3>
      <p class="hint">Milestones are the game's life-event records. Install-seeded milestones come from the premade template. Dynasty, career and other event milestones are created by runtime systems after the save starts and are not present in the install files.</p>
      ${traitChips(sim.milestones, "milestones")}
      <div class="add-line"><button class="btn sm" data-add="milestones">+ Add milestone</button></div>
    </div>
    <div class="card full">
      <h3>Likes &amp; dislikes</h3>
      <p class="hint">One grouped list, like in game. Pick Like or Dislike once per item; choosing the other replaces it.</p>
      <div class="pref-summary">
        <span class="badge green">${(sim.likes || []).length} likes</span>
        <span class="badge">${(sim.dislikes || []).length} dislikes</span>
      </div>
      <div class="chips" style="margin-top:10px">
        ${(sim.likes || []).map((l, i) => `<span class="chip">${esc(l.label.replace(/^Likes /, ""))}<button class="x" data-life-pref-remove="likes:${i}" title="Remove like">✕</button></span>`).join("")}
        ${(sim.dislikes || []).map((l, i) => `<span class="chip" style="background:var(--gold-soft);border-color:#e3d49b;color:#6b5717">${esc(l.label.replace(/^Dislikes /, ""))}<button class="x" data-life-pref-remove="dislikes:${i}" title="Remove dislike">✕</button></span>`).join("")}
        ${(sim.likes || []).length + (sim.dislikes || []).length ? "" : `<span class="chip-empty">No likes or dislikes yet.</span>`}
      </div>
      <div class="add-line"><button class="btn sm primary" data-open-prefs>+ Add or edit likes &amp; dislikes</button></div>
    </div>
  </div>`;
}

function renderSummary() {
  const sims = Object.values(state.project.sims || {});
  const modded = sims.some(
    (s) =>
      (s.traits || []).some((t) => t.modded) ||
      (s.skills || []).some((t) => t.modded) ||
      (s.career && s.career.modded)
  );
  $("#summary").innerHTML = `
    <div class="sum-item"><span>Sims in project</span><strong>${sims.length}</strong></div>
    <div class="sum-item"><span>Modded content</span><strong>${modded ? "Yes" : "No"}</strong></div>`;
}

function renderPaths() {
  const p = state.status?.paths || {};
  $("#paths").innerHTML = `
    <div>Game: <code>${esc(p.game || "not found")}</code></div>
    <div>User: <code>${esc(p.docs || "not found")}</code></div>
    <div>Export: <code>${esc(p.exports || "")}</code></div>`;
}

/* ------------------------------------------------------------------ sidebar */
function onSidebarClick(event) {
  const delHh = event.target.closest("[data-del-hh]");
  if (delHh) {
    event.stopPropagation();
    removeHousehold(delHh.dataset.delHh);
    return;
  }
  const menu = event.target.closest("[data-sim-menu]");
  if (menu) {
    event.stopPropagation();
    openSimMenu(menu.dataset.simMenu);
    return;
  }
  const del = event.target.closest("[data-del]");
  if (del) {
    event.stopPropagation();
    removeSim(del.dataset.del);
    return;
  }
  const row = event.target.closest("[data-sim]");
  if (row) {
    state.selected = row.dataset.sim;
    renderAll();
  }
}

const REPLACE_FIELDS = [
  { id: "identity", label: "Name & household", fields: ["first", "last", "household", "household_key"], def: false },
  { id: "core", label: "Age, gender, species & occult", fields: ["age", "gender", "species", "occult"], def: true },
  { id: "traits", label: "Personality traits", fields: ["traits"], def: true },
  { id: "skills", label: "Skills", fields: ["skills"], def: true },
  { id: "career", label: "Career, level, specialisation & history", fields: ["career", "career_history", "career_track"], def: true },
  { id: "aspiration", label: "Aspiration", fields: ["aspiration"], def: true },
  { id: "degrees", label: "University degrees", fields: ["degrees"], def: true },
  { id: "milestones", label: "Milestones", fields: ["milestones"], def: true },
  { id: "likes", label: "Likes & dislikes", fields: ["likes", "dislikes"], def: true },
  { id: "relations", label: "Relationships & family links", fields: ["relationships", "family"], def: false },
  { id: "picture", label: "Portrait & household picture", fields: ["image", "image_mask", "image_kind", "household_image", "household_image_mask"], def: true },
  { id: "funds", label: "Household funds", fields: ["funds"], def: false },
];

function openSimMenu(key) {
  const sim = state.project.sims[key];
  if (!sim) return;
  const origin = state.project.origin || {};
  const originLabel = origin.label || "clean new-save world";
  const body = `
    <p class="hint">Options for <strong>${esc(sim.first)} ${esc(sim.last)}</strong>. This project started from <strong>${esc(originLabel)}</strong>.</p>
    <div class="sim-menu">
      <button class="menu-item" data-menu="tray">Replace data from Tray… <small>Choose a Tray sim, then pick exactly which fields to replace</small></button>
      <button class="menu-item" data-menu="reset">Reset to game template <small>Restore the original values from ${esc(originLabel)}</small></button>
      <button class="menu-item danger" data-menu="remove">Remove sim</button>
    </div>`;
  openModal("Sim options", body, `<button class="btn" id="menu-close-btn">Cancel</button>`, true);
  $("#menu-close-btn").addEventListener("click", closeModal);
  $$("[data-menu]").forEach((btn) => btn.addEventListener("click", () => {
    const action = btn.dataset.menu;
    closeModal();
    if (action === "tray") openTrayReplaceFields(sim);
    else if (action === "reset") resetSimTemplate(sim);
    else if (action === "remove") removeSim(key);
  }));
}

function openTrayReplaceFields(target) {
  openTrayPicker("Replace data from Tray", (source) => {
    const body = `<p class="hint">Choose what to copy from <strong>${esc(source.first)} ${esc(source.last)}</strong> onto <strong>${esc(target.first)} ${esc(target.last)}</strong>. Anything unchecked stays exactly as it is.</p>
      <div class="replace-fields">${REPLACE_FIELDS.map((f) => `<label class="toggle replace-row"><input type="checkbox" data-replace-field="${f.id}" ${f.def ? "checked" : ""}/> ${esc(f.label)}</label>`).join("")}</div>
      <div class="add-line" style="margin-top:10px"><button class="btn sm ghost" id="rf-none">Uncheck all</button><button class="btn sm ghost" id="rf-all">Check all</button></div>`;
    openModal("Choose what to replace", body, `<button class="btn" id="rf-cancel">Cancel</button><button class="btn primary" id="rf-apply">Apply</button>`, true);
    $("#rf-cancel").addEventListener("click", closeModal);
    $("#rf-none").addEventListener("click", () => $$("[data-replace-field]").forEach((x) => { x.checked = false; }));
    $("#rf-all").addEventListener("click", () => $$("[data-replace-field]").forEach((x) => { x.checked = true; }));
    $("#rf-apply").addEventListener("click", () => {
      const chosen = new Set($$("[data-replace-field]:checked").map((x) => x.dataset.replaceField));
      const before = cloneSim(target);
      let n = 0;
      for (const group of REPLACE_FIELDS) {
        if (!chosen.has(group.id)) continue;
        for (const field of group.fields) {
          if (!(field in source)) continue;
          const incoming = JSON.parse(JSON.stringify(source[field] ?? null));
          // Merge list fields by id/label so edits made in this tool survive.
          if (Array.isArray(incoming) && Array.isArray(target[field])) {
            const keyOf = (x) => (x && (x.id ?? x.label ?? x.target)) ?? x;
            const seen = new Set(target[field].map(keyOf));
            for (const item of incoming) if (!seen.has(keyOf(item))) target[field].push(item);
          } else {
            target[field] = incoming;
          }
          n++;
        }
      }
      if (chosen.has("picture")) PORTRAIT_CACHE.delete(target.key);
      target._replace_undo = { at: Date.now(), source: `${source.first} ${source.last}`, before: JSON.stringify(before) };
      queueSave();
      closeModal();
      renderAll();
      showReplaceDiff(target, before, source);
      toast(`Merged ${n} field${n === 1 ? "" : "s"} from ${source.first} ${source.last}`, "ok");
    });
  });
}

function cloneSim(sim) {
  const out = {};
  for (const [k, v] of Object.entries(sim)) {
    if (k.startsWith("_")) continue;
    out[k] = JSON.parse(JSON.stringify(v ?? null));
  }
  return out;
}

function describeValue(v) {
  if (v == null || v === "") return "—";
  if (Array.isArray(v)) {
    if (!v.length) return "none";
    const labels = v.slice(0, 3).map((x) => (x && (x.label || x.relation || x.target)) || String(x));
    return labels.join(", ") + (v.length > 3 ? ` +${v.length - 3}` : "");
  }
  if (typeof v === "object") return v.label || v.name || JSON.stringify(v).slice(0, 40);
  return String(v);
}

function showReplaceDiff(target, before, source) {
  const changed = [];
  for (const k of Object.keys(before)) {
    const a = JSON.stringify(before[k] ?? null);
    const b = JSON.stringify(target[k] ?? null);
    if (a !== b) changed.push({ field: k, before: before[k], after: target[k] });
  }
  const rows = changed
    .map((c) => `<tr><td><strong>${esc(c.field)}</strong></td><td class="diff-old">${esc(describeValue(c.before))}</td><td class="diff-new">${esc(describeValue(c.after))}</td></tr>`)
    .join("");
  const body = changed.length
    ? `<p class="hint">Compared to the original sim before copying from <strong>${esc(source.first)} ${esc(source.last)}</strong>.</p>
       <table class="diff-table"><thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead><tbody>${rows}</tbody></table>`
    : `<p class="hint">Nothing changed.</p>`;
  openModal("What changed", body,
    `<button class="btn" id="diff-close">Close</button><button class="btn primary" id="diff-undo">Undo this replace</button>`, false);
  $("#diff-close").addEventListener("click", closeModal);
  $("#diff-undo").addEventListener("click", () => {
    undoReplace(target);
    closeModal();
    toast("Reversed the replace", "ok");
  });
}

function undoReplace(target) {
  const undo = target._replace_undo;
  if (!undo) return;
  const before = JSON.parse(undo.before);
  const key = target.key;
  for (const k of Object.keys(target)) if (!k.startsWith("_")) delete target[k];
  Object.assign(target, before, { key });
  delete target._replace_undo;
  PORTRAIT_CACHE.delete(key);
  queueSave();
  renderAll();
}

function openTrayPicker(title, onPick) {
  const show = async () => {
    if (!state.tray?.length) {
      try { state.tray = (await api("/api/tray")).households || []; }
      catch (err) { toast(err.message, "err"); return; }
    }
    const body = `
      <input class="input" id="tp-search" placeholder="Search Tray households or sims…" />
      <div class="list" id="tp-list" style="max-height:52vh;overflow:auto;margin-top:10px"></div>`;
    openModal(title, body, `<button class="btn" id="tp-cancel">Cancel</button>`, true);
    $("#tp-cancel").addEventListener("click", closeModal);
    const renderList = (query = "") => {
      const q = query.toLowerCase();
      const items = [...state.tray]
        .filter((h) => !q || `${h.household} ${h.sims.map((s) => `${s.first} ${s.last}`).join(" ")}`.toLowerCase().includes(q))
        .sort((a, b) => a.household.localeCompare(b.household)).slice(0, 200);
      $("#tp-list").innerHTML = items.map((h) => `<div class="list-item" data-tp-hh="${esc(h.id)}">
        ${h.household_image ? `<img class="list-thumb" src="${esc(h.household_image)}" style="${maskStyle(h.household_image_mask)}" alt="" />` : ""}
        <div class="list-who"><strong>${esc(h.household)}</strong><span>${h.sims.length} sims · ${esc(h.modified_label)}</span></div>
      </div>`).join("") || `<div class="chip-empty">No matching Tray households.</div>`;
      $$("[data-tp-hh]").forEach((el) => el.addEventListener("click", async () => {
        $("#tp-list").innerHTML = `<div class="progress-wrap"><span class="spinner"></span> Reading sim data…</div>`;
        try {
          const hh = await api(`/api/tray/household?id=${encodeURIComponent(el.dataset.tpHh)}`);
          $("#tp-list").innerHTML = hh.sims.map((s, i) => `<div class="list-item">
            ${s.image ? `<img class="list-thumb" src="${esc(s.image)}" style="${maskStyle(s.image_mask)}" alt="" />` : ""}
            <div class="list-who"><strong>${esc(s.first)} ${esc(s.last)}</strong><span>${esc(s.age || "")} · ${esc(s.gender || "")}</span></div>
            <button class="btn sm primary" data-tp-use="${i}">Choose</button>
          </div>`).join("");
          $$("[data-tp-use]").forEach((btn) => btn.addEventListener("click", () => {
            closeModal();
            onPick(hh.sims[Number(btn.dataset.tpUse)]);
          }));
        } catch (err) { $("#tp-list").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`; }
      }));
    };
    $("#tp-search").addEventListener("input", (e) => renderList(e.target.value));
    renderList("");
  };
  show();
}

async function resetSimTemplate(target) {
  try {
    const data = await api(`/api/project/sim_template?key=${encodeURIComponent(target.key)}`);
    if (!data.sim) { toast("No original template found for this sim.", "err"); return; }
    const fresh = data.sim;
    const key = target.key;
    for (const field of Object.keys(target)) if (field !== "key") delete target[field];
    Object.assign(target, fresh, { key });
    PORTRAIT_CACHE.delete(key);
    queueSave();
    renderAll();
    toast(`Reset to the original ${data.origin?.label || "game"} values`, "ok");
  } catch (err) { toast(err.message, "err"); }
}

async function removeSim(key) {
  const sim = state.project.sims[key];
  if (!sim) return;
  if (!confirm(`Remove ${sim.first} ${sim.last} from this project?`)) return;
  try {
    const data = await api("/api/project/remove_sim", { method: "POST", body: JSON.stringify({ key }) });
    state.project = data.project;
    if (state.selected === key) state.selected = Object.keys(state.project.sims)[0] || null;
    renderAll();
  } catch (err) {
    toast(err.message, "err");
  }
}

async function removeHousehold(key) {
  const rows = Object.values(state.project.sims || {}).filter((s) => (s.household_key || s.household) === key);
  if (!rows.length) return;
  const name = rows[0].household || rows[0].last || "this household";
  if (!confirm(`Remove the whole ${name} household (${rows.length} sim${rows.length === 1 ? "" : "s"}) from the project?`)) return;
  try {
    const data = await api("/api/project/remove_household", { method: "POST", body: JSON.stringify({ household_key: key }) });
    state.project = data.project;
    if (!state.project.sims[state.selected]) state.selected = Object.keys(state.project.sims)[0] || null;
    renderAll();
  } catch (err) {
    toast(err.message, "err");
  }
}

function addManualSim() {
  const first = prompt("First name?");
  if (!first) return;
  const last = prompt("Last name?") || "";
  state.project.sims[`${first}|${last}`] = {
    key: `${first}|${last}`,
    first,
    last,
    household: last || first,
    source: "manual",
    age: "Adult",
    gender: "Female",
    occult: "Human",
    traits: [],
    skills: [],
    career: null,
    aspiration: null,
    funds: null,
    relationships: [],
    family: [],
    degrees: [],
    milestones: [],
    likes: [],
    dislikes: [],
    notes: "",
  };
  state.selected = `${first}|${last}`;
  queueSave();
  renderAll();
}

async function clearProject() {
  if (!confirm("Clear every sim from this project?")) return;
  const data = await api("/api/project/reset", { method: "POST", body: JSON.stringify({ name: state.project.name }) });
  state.project = data.project;
  state.selected = null;
  renderAll();
}

const TRAIT_CONFLICTS = {
  Active: "Lazy",
  Lazy: "Active",
  Cheerful: "Gloomy",
  Gloomy: "Cheerful",
  Good: "Evil",
  Evil: "Good",
  Neat: "Slob",
  Slob: "Neat",
  "Loves Outdoors": "Hates Outdoors",
  "Hates Outdoors": "Loves Outdoors",
  Romantic: "Unflirty",
  Unflirty: "Romantic",
  "Family Oriented": "Hates Children",
  "Hates Children": "Family Oriented",
  Outgoing: "Loner",
  Loner: "Outgoing",
  "Self-Assured": "Self-Deprecating",
  "Self-Deprecating": "Self-Assured",
};

function traitConflict(sim, item) {
  const opposite = TRAIT_CONFLICTS[item.label];
  if (!opposite) return null;
  return (sim.traits || []).find((t) => t.label === opposite) || null;
}

function ageMismatch(sim, item) {
  return item.age_hint && sim.age && item.age_hint !== sim.age ? item.age_hint : null;
}

function relationIcon(label) {
  const low = (label || "").toLowerCase();
  if (low.includes("spouse") || low.includes("partner") || low.includes("romance")) return "Aspiration4.png";
  if (low.includes("parent") || low.includes("child") || low.includes("sibling") || low.includes("family")) return "Aspiration1.png";
  return "Relationship%20Positive.png";
}

/* ------------------------------------------------------------------- editor */
function onEditorClick(event) {
  const treeSim = event.target.closest("[data-tree-sim], [data-dyn-sim]");
  if (treeSim) {
    state.selected = treeSim.dataset.treeSim || treeSim.dataset.dynSim;
    renderAll();
    return;
  }

  const relView = event.target.closest("[data-rel-view]");
  if (relView) {
    state.relView = relView.dataset.relView;
    renderEditor();
    return;
  }

  const dynAdd = event.target.closest("[data-dyn-add]");
  if (dynAdd) { openDynastyEditor(-1); return; }
  const dynEdit = event.target.closest("[data-dyn-edit]");
  if (dynEdit) { openDynastyEditor(Number(dynEdit.dataset.dynEdit)); return; }
  const dynRemove = event.target.closest("[data-dyn-remove]");
  if (dynRemove) {
    state.project.dynasties.splice(Number(dynRemove.dataset.dynRemove), 1);
    queueSave();
    renderEditor();
    return;
  }

  const majorPick = event.target.closest("[data-major-pick]");
  if (majorPick) {
    const sim = currentSim();
    if (sim) {
      openCatalog("degrees", (item) => {
        sim.degrees = sim.degrees || [];
        if (!sim.degrees.some((d) => d.id === item.id)) {
          sim.degrees.push({ id: item.id, label: item.label, modded: item.modded, pack: item.pack_label, major: item.major });
        }
        queueSave();
        renderEditor();
        renderStage();
        renderSummary();
      }, true, majorPick.dataset.majorPick);
    }
    return;
  }

  const branchesBtn = event.target.closest("[data-open-branches]");
  if (branchesBtn) {
    const sim = currentSim();
    if (sim) {
      openCatalog("career_tracks", (item) => {
        sim.career_track = { id: item.id, label: item.label, modded: item.modded, icon: item.icon };
        queueSave();
        renderEditor();
      }, true, branchesBtn.dataset.openBranches);
    }
    return;
  }

  const prefsBtn = event.target.closest("[data-open-prefs]");
  if (prefsBtn) {
    const sim = currentSim();
    if (sim) openPreferencesPicker(sim);
    return;
  }

  const replaceTray = event.target.closest("[data-replace-tray]");
  if (replaceTray) {
    const sim = currentSim();
    if (sim) openTrayReplaceFields(sim);
    return;
  }

  const undoRep = event.target.closest("[data-undo-replace]");
  if (undoRep) {
    const sim = currentSim();
    if (sim) { undoReplace(sim); toast("Reversed the replace", "ok"); }
    return;
  }

  const lifePref = event.target.closest("[data-life-pref-remove]");
  if (lifePref) {
    const sim = currentSim();
    if (!sim) return;
    const [field, index] = lifePref.dataset.lifePrefRemove.split(":");
    sim[field] = (sim[field] || []).filter((_, i) => i !== Number(index));
    queueSave();
    renderEditor();
    renderStage();
    return;
  }

  const addBit = event.target.closest("[data-add-bit]");
  if (addBit) {
    const sim = currentSim();
    if (!sim) return;
    const index = Number(addBit.dataset.addBit);
    openCatalog(
      "relationship_bits",
      (item) => {
        sim.relationships[index].bits = sim.relationships[index].bits || [];
        if (!sim.relationships[index].bits.some((b) => b.id === item.id)) {
          sim.relationships[index].bits.push({ id: item.id, label: item.label, modded: item.modded });
        }
        queueSave();
        renderEditor();
      },
      true
    );
    return;
  }

  const removeBit = event.target.closest("[data-remove-bit]");
  if (removeBit) {
    const sim = currentSim();
    if (!sim) return;
    const [index, bitIndex] = removeBit.dataset.removeBit.split(":").map(Number);
    sim.relationships[index].bits = (sim.relationships[index].bits || []).filter((_, i) => i !== bitIndex);
    queueSave();
    renderEditor();
    return;
  }

  const placeholder = event.target.closest("[data-add-placeholder]");
  if (placeholder) {
    const sim = currentSim();
    if (!sim) return;
    const first = ($("#ph-first")?.value || "").trim();
    const last = ($("#ph-last")?.value || sim.last || "").trim();
    const relation = $("#ph-relation")?.value || "Parent";
    if (!first) { toast("Enter a first name for the placeholder.", "err"); return; }
    const key = `manual:${first}|${last}:${Date.now()}`;
    const ph = {
      key, first, last, household: sim.household || last, household_key: sim.household_key || last,
      source: "manual", source_ref: null, age: "Adult", gender: "Female", species: "Human", occult: "Human",
      traits: [], remove_traits: [], skills: [], career: null, career_history: [], aspiration: null,
      funds: null, relationships: [], family: [], degrees: [], milestones: [], likes: [], dislikes: [],
      notes: "", data_quality: "manual",
    };
    const opposite = { Parent: "Child", Child: "Parent", Sibling: "Sibling", Spouse: "Spouse" }[relation] || "Relative";
    sim.family.push({ target: key, relation });
    ph.family.push({ target: sim.key, relation: opposite });
    sim.relationships.push({ target: key, label: relation, friendship: relation === "Spouse" ? 45 : 45, romance: relation === "Spouse" ? 75 : 0 });
    ph.relationships.push({ target: sim.key, label: opposite, friendship: 45, romance: relation === "Spouse" ? 75 : 0 });
    state.project.sims[key] = ph;
    queueSave();
    renderAll();
    toast(`Added placeholder ${relation.toLowerCase()} ${first} ${last}`, "ok");
    return;
  }

  const add = event.target.closest("[data-add]");
  if (add) return handleAdd(add.dataset.add);

  const clear = event.target.closest("[data-clear]");
  if (clear) {
    const sim = currentSim();
    if (!sim) return;
    sim[clear.dataset.clear] = [];
    queueSave();
    renderEditor();
    renderStage();
    renderSummary();
    return;
  }

  const restore = event.target.closest("[data-restore-trait]");
  if (restore) {
    const sim = currentSim();
    if (!sim) return;
    const i = Number(restore.dataset.restoreTrait);
    const t = (sim.remove_traits || [])[i];
    if (t) {
      sim.remove_traits.splice(i, 1);
      sim.traits = sim.traits || [];
      if (!sim.traits.some((x) => x.id === t.id)) sim.traits.push(t);
      queueSave();
      renderEditor();
      renderStage();
      renderSummary();
    }
    return;
  }

  const remove = event.target.closest("[data-remove]");
  if (remove) {
    const sim = currentSim();
    if (!sim) return;
    const [field, index] = remove.dataset.remove.split(":");
    if (field === "career") sim.career = null;
    else if (field === "career_track") sim.career_track = null;
    else if (field === "aspiration") sim.aspiration = null;
    else if (field === "traits") {
      const t = (sim.traits || [])[Number(index)];
      sim.traits = (sim.traits || []).filter((_, i) => i !== Number(index));
      if (t && (sim.source === "premade" || sim.data_quality === "full")) {
        sim.remove_traits = sim.remove_traits || [];
        if (!sim.remove_traits.some((x) => x.id === t.id)) sim.remove_traits.push(t);
      }
    } else if (field === "family") {
      const link = (sim.family || [])[Number(index)];
      const target = link && state.project.sims[link.target];
      sim.family = (sim.family || []).filter((_, i) => i !== Number(index));
      if (target) {
        target.family = (target.family || []).filter((f) => f.target !== sim.key);
      }
    } else sim[field] = (sim[field] || []).filter((_, i) => i !== Number(index));
    queueSave();
    renderEditor();
    renderStage();
    renderSummary();
  }
}

function onEditorInput(event) {
  const sim = currentSim();
  if (!sim) return;
  const target = event.target;

  if (target.dataset.edit) {
    const field = target.dataset.edit;
    sim[field] = target.type === "number" ? (target.value === "" ? null : Number(target.value)) : target.value;
    if (field === "first" || field === "last") {
      const oldKey = sim.key;
      const newKey = `${sim.first}|${sim.last}`;
      if (newKey !== oldKey && !state.project.sims[newKey]) {
        delete state.project.sims[oldKey];
        sim.key = newKey;
        state.project.sims[newKey] = sim;
        state.selected = newKey;
      }
    }
    queueSave();
    renderSidebar();
    renderStage();
    return;
  }

  if (target.dataset.skill !== undefined) {
    const index = Number(target.dataset.skill);
    const value = Number(target.value);
    sim.skills[index].level = value;
    delete sim.skills[index].level_unknown;
    target.style.setProperty("--pct", `${(value / 10) * 100}%`);
    const pill = $(`[data-level="${index}"]`);
    if (pill) {
      pill.textContent = value;
      pill.removeAttribute("title");
    }
    queueSave();
    return;
  }

  if (target.dataset.rel !== undefined) {
    const index = Number(target.dataset.rel);
    const field = target.dataset.field;
    const value = Number(target.value);
    sim.relationships[index][field] = value;
    const label = target.closest(".rel-slider").querySelector("label span");
    if (label) label.textContent = value;
    target.style.setProperty("--pct", `${((value + 100) / 200) * 100}%`);
    queueSave();
    return;
  }

  if (target.hasAttribute("data-career-level")) {
    const value = Number(target.value);
    sim.career.level = value;
    target.style.setProperty("--pct", `${((value - 1) / 9) * 100}%`);
    const pill = target.parentElement.querySelector(".level-pill");
    if (pill) pill.textContent = value;
    queueSave();
    // Re-render the career card once the drag ends so the specialisation
    // lock/unlock state updates, without breaking the slider drag itself.
    clearTimeout(target._careerTimer);
    target._careerTimer = setTimeout(() => renderEditor(), 180);
  }
}

function applyRewardEffects(sim, item, added) {
  const eff = item.reward_effects;
  if (!eff) return;
  if (eff.aspiration_id && !sim.aspiration) {
    sim.aspiration = { id: eff.aspiration_id, label: eff.aspiration, modded: false };
    added.push(`aspiration ${eff.aspiration}`);
  }
  if (eff.career_id) {
    const exists = (sim.career && sim.career.id === eff.career_id) ||
      (sim.career_history || []).some((c) => c.id === eff.career_id);
    if (!exists) {
      sim.career_history = sim.career_history || [];
      sim.career_history.push({ id: eff.career_id, label: eff.career, modded: false, level: 10 });
      added.push(`ex-career ${eff.career}`);
    }
  }
  for (const sk of eff.skills || []) {
    if (!sim.skills.some((s) => s.id === sk.id)) {
      sim.skills.push({ id: sk.id, label: sk.label, modded: false, level: 5 });
      added.push(`skill ${sk.label}`);
    }
  }
}

function handleAdd(kind) {
  const sim = currentSim();
  if (!sim) return;

  if (kind === "relationship") {
    const key = $("#rel-target")?.value;
    if (!key) return;
    sim.relationships.push({ target: key, friendship: 0, romance: 0, bits: [] });
    queueSave();
    renderEditor();
    renderSummary();
    return;
  }
  if (kind === "family") {
    const key = $("#fam-target")?.value;
    const relation = $("#fam-relation")?.value || "Parent";
    if (!key || key === sim.key) return;
    const target = state.project.sims[key];
    if (!target) return;
    const meta = relationMeta({ relation });
    const inverse = meta.inverse || "Relative";
    const addSide = (a, b, rel, gen) => {
      if (!a.family) a.family = [];
      if (!a.family.some((f) => f.target === b.key)) {
        a.family.push({
          target: b.key,
          relation: rel,
          inverse: rel === relation ? inverse : relation,
          generation: gen,
          category: meta.category,
          from_game: false,
        });
      }
    };
    addSide(sim, target, relation, meta.generation);
    addSide(target, sim, inverse, -(meta.generation || 0));
    const pair = (a, b, label, friendship, romance) => {
      let row = (a.relationships || []).find((r) => r.target === b.key);
      if (!row) {
        row = { target: b.key, label, friendship, romance, bits: [] };
        a.relationships = a.relationships || [];
        a.relationships.push(row);
      } else if (!row.label || ["Knows", "Has met", "Acquaintance", "Household member"].includes(row.label)) {
        row.label = label;
      }
    };
    const partner = meta.category === "partner";
    pair(sim, target, relation, partner ? 60 : 45, partner ? 60 : 0);
    pair(target, sim, inverse, partner ? 60 : 45, partner ? 60 : 0);
    queueSave();
    renderEditor();
    renderStage();
    renderSummary();
    return;
  }
  if (kind === "degrees") {
    openCatalog("degrees", (item) => {
      sim.degrees = sim.degrees || [];
      if (!sim.degrees.some((d) => d.id === item.id)) {
        sim.degrees.push({ id: item.id, label: item.label, modded: item.modded, pack: item.pack_label, major: item.major });
      }
      queueSave();
      renderEditor();
      renderStage();
      renderSummary();
    }, true);
    return;
  }

  const catalogKind = {
    traits: "traits",
    remove_traits: "traits",
    aspirations: "aspirations",
    skills: "skills",
    careers: "careers",
    career_tracks: "career_tracks",
    milestones: "milestones",
    preferences: "preferences",
    likes: "preferences",
    dislikes: "preferences",
  }[kind];
  if (!catalogKind) return;

  openCatalog(catalogKind, (item) => {
    const added = [];
    if (kind === "traits") {
      if ((sim.traits || []).some((t) => t.id === item.id)) {
        toast("That trait is already on this sim.", "err");
        return;
      }
      const conflict = traitConflict(sim, item);
      if (conflict && !confirm(`${item.label} conflicts with ${conflict.label}. Add it anyway?`)) return;
      const mismatch = ageMismatch(sim, item);
      if (mismatch && !confirm(`${item.label} is normally ${mismatch}-only. Add it anyway?`)) return;
      sim.traits.push({ id: item.id, label: item.label, modded: item.modded, pack: item.pack_label, icon: item.icon });
      applyRewardEffects(sim, item, added);
    } else if (kind === "remove_traits") sim.remove_traits.push({ id: item.id, label: item.label, modded: item.modded, pack: item.pack_label, icon: item.icon });
    else if (kind === "aspirations") sim.aspiration = { id: item.id, label: item.label, modded: item.modded, pack: item.pack_label, icon: item.icon };
    else if (kind === "skills") {
      if (!sim.skills.some((s) => s.id === item.id)) sim.skills.push({ id: item.id, label: item.label, modded: item.modded, level: 1, icon: item.icon });
    } else if (kind === "careers") {
      sim.career = { id: item.id, label: item.label, modded: item.modded, level: 1, icon: item.icon };
      if (item.university_student) sim.career.university_student = true;
      sim.career_track = null;
    } else if (kind === "career_tracks") {
      const family = suggestedBranchFamily(sim.career?.label);
      const tracks = (state.gamedata?.career_branches || {})[family] || [];
      const levels = state.gamedata?.branch_levels || {};
      const need = levels[family] || state.gamedata?.branch_level || 5;
      const hasBranches = !!sim.career?.university_student || tracks.some((t) => !t.main);
      if (!sim.career || !hasBranches || (!sim.career.university_student && (sim.career.level || 1) < need)) {
        toast(!sim.career ? "Choose a career first." : !hasBranches ? "This career has no specialisations." : `Reach career level ${need} before choosing a specialisation.`, "err");
        return;
      }
      sim.career_track = { id: item.id, label: item.label, modded: item.modded, icon: item.icon };
    } else if (kind === "milestones") sim.milestones.push({ id: item.id, label: item.label, modded: item.modded, icon: item.icon });
    else if (kind === "preferences" || kind === "likes") sim.likes.push({ id: item.id, label: item.label, modded: item.modded });
    else if (kind === "dislikes") sim.dislikes.push({ id: item.id, label: item.label, modded: item.modded });
    queueSave();
    renderEditor();
    renderStage();
    renderSummary();
    if (added.length) toast(`Also applied: ${added.join(", ")}`, "ok");
  }, true);
}

/* ---------------------------------------------------------------- new project */
async function openNewProject() {
  let saves = [];
  try {
    saves = (await api("/api/saves")).saves || [];
  } catch (err) {
    saves = [];
  }
  const options = saves
    .map((s, i) => `<option value="${esc(s.file)}" ${i === 0 ? "selected" : ""}>${esc(s.slot)} · ${esc(s.modified_label)}</option>`)
    .join("");
  openModal(
    "Start a new overhaul",
    `<div class="new-project-grid">
      <div class="mode-card active">
        <h4>Clean premade world</h4>
        <p>Loads the game's own premade sims exactly as they start in a new save — original looks, traits, skills, careers, funds and family links. Tray sims are only used if you explicitly choose them.</p>
      </div>
      <div class="field"><label>Project name</label><input class="input" id="new-project-name" value="${esc(state.project.name || "My Sim Overhaul")}" /></div>
      <div class="field"><label>Premades to start with</label>
        <select class="select" id="new-source">
          <option value="premade" selected>Game premades — clean new-save world (recommended)</option>
          <option value="tray">Tray library premades only</option>
          <option value="save">Copy every household from a save</option>
          <option value="empty">Empty project</option>
        </select>
      </div>
      <div class="field" id="new-save-wrap" style="display:none">
        <label>Save to copy households from</label>
        <select class="select" id="new-project-save">${options || `<option value="">No saves found</option>`}</select>
      </div>
      <p class="hint" id="new-source-hint">Loads the <strong>clean premade sims from the game files</strong> — the same sims the game places when you start a new save, with their original looks, traits, skills, careers, funds and family links. No Tray sims are used.</p>
      <div class="card">
        <h3>How it works</h3>
        <ul class="new-project-steps">
          <li>The game still places the premades when you start a new save.</li>
          <li>This project decides what the mod changes: traits, skills, careers, relationships, funds and more.</li>
          <li>Export the mod, install it in <code>Mods</code>, and start a new save.</li>
        </ul>
      </div>
    </div>`,
    `<button class="btn" id="create-empty">Cancel</button>
     <button class="btn primary" id="create-project">Create project</button>`,
    true
  );
  $("#new-source").addEventListener("change", (e) => {
    const source = e.target.value;
    $("#new-save-wrap").style.display = source === "save" ? "" : "none";
    $("#new-source-hint").innerHTML =
      source === "premade"
        ? "Loads the <strong>clean premade sims from the game files</strong> — the same sims the game places when you start a new save, with their original looks, traits, skills, careers, funds and family links. No Tray sims are used."
        : source === "save"
        ? "Copies every household from the selected save. Use the save only as a data source — the exported mod still applies to a <strong>new</strong> save."
        : source === "tray"
        ? "Imports the known premade households (Goths, Calientes, Landgraabs, etc.) from your Tray library. If one is missing, add it afterwards with <strong>From Tray</strong>."
        : "Starts with no sims. Add them later with <strong>From Saves</strong> or <strong>From Tray</strong>.";
  });
  $("#create-project").addEventListener("click", () => createProject(false));
  $("#create-empty").addEventListener("click", closeModal);
}

async function createProject(openSaves) {
  const name = ($("#new-project-name")?.value || "My Sim Overhaul").trim() || "My Sim Overhaul";
  const source = $("#new-source")?.value || "premade";
  const file = $("#new-project-save")?.value;
  const button = $("#create-project");
  if (button) { button.disabled = true; button.textContent = "Creating…"; }
  try {
    const data = await api("/api/project/reset", { method: "POST", body: JSON.stringify({ name }) });
    state.project = data.project;
    state.selected = null;
    $("#project-name").value = name;

    if (source === "save" && file) {
      const save = await api(`/api/save?file=${encodeURIComponent(file)}`);
      state.save = save;
      if (save.sims?.length) {
        const origin = { mode: "save", label: `save ${save.slot || file}`, file };
        const added = await api("/api/project/add_sims", {
          method: "POST",
          body: JSON.stringify({ sims: save.sims, source_ref: file, origin }),
        });
        state.project = added.project;
        state.selected = added.added[0]?.key || null;
      }
    } else if (source === "premade") {
      const added = await api("/api/project/seed_world_template", { method: "POST", body: "{}" });
      state.project = added.project;
      state.selected = added.added[0]?.key || null;
      if (!added.added.length) {
        toast("The clean premade world data is missing. Click Scan Content, then try again.", "err");
      } else {
        toast(`Loaded ${added.households} clean premade households from the game files`, "ok");
      }
    } else if (source === "tray") {
      const added = await api("/api/project/seed_tray_premades", { method: "POST", body: "{}" });
      state.project = added.project;
      state.selected = added.added[0]?.key || null;
      if (!added.added.length) toast("No matching premades found in your Tray library.", "err");
    }
    renderAll();
    closeModal();
    if (source !== "premade") toast("New overhaul project created", "ok");
    if (openSaves) openSavesModal();
  } catch (err) {
    toast(err.message, "err");
    if (button) { button.disabled = false; button.textContent = "Create project"; }
  }
}

/* ------------------------------------------------------------- likes & dislikes */
async function openPreferencesPicker(sim) {
  openModal("Likes & dislikes", `<div class="progress-wrap"><span class="spinner"></span> Loading preferences…</div>`, `<button class="btn primary" id="pref-done">Done</button>`, true);
  $("#pref-done").addEventListener("click", () => {
    closeModal();
    renderEditor();
    renderStage();
    renderSummary();
  });
  try {
    const data = await api("/api/catalog?kind=preferences&batuu=0&q=");
    const map = new Map();
    for (const item of data.items) {
      let label = item.label;
      let mode = null;
      if (label.startsWith("Likes ")) {
        mode = "like";
        label = label.slice(6);
      } else if (label.startsWith("Dislikes ")) {
        mode = "dislike";
        label = label.slice(9);
      } else {
        continue;
      }
      const parts = label.split(" ");
      const category = parts[0] || "Other";
      const name = parts.slice(1).join(" ") || label;
      const key = `${category}|${name}`;
      if (!map.has(key)) map.set(key, { category, name, likeId: null, dislikeId: null, likeLabel: "", dislikeLabel: "" });
      const row = map.get(key);
      if (mode === "like") {
        row.likeId = item.id;
        row.likeLabel = item.label;
      } else {
        row.dislikeId = item.id;
        row.dislikeLabel = item.label;
      }
    }
    state.prefPicker = { simKey: sim.key, map, query: "" };
    renderPreferencesBody();
  } catch (err) {
    $("#modal-body").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`;
  }
}

function prefState(sim, row) {
  const inLikes = (sim.likes || []).some((x) => x.label === row.likeLabel || x.id === row.likeId);
  const inDislikes = (sim.dislikes || []).some((x) => x.label === row.dislikeLabel || x.id === row.dislikeId);
  return { inLikes, inDislikes };
}

function renderPreferencesBody() {
  const picker = state.prefPicker;
  if (!picker) return;
  const sim = state.project.sims[picker.simKey];
  if (!sim) return;
  const query = (picker.query || "").toLowerCase();
  const groups = {};
  for (const row of picker.map.values()) {
    if (query && !`${row.category} ${row.name}`.toLowerCase().includes(query)) continue;
    (groups[row.category] ||= []).push(row);
  }
  const order = ["Activities", "Music", "Food", "Color", "Decor", "Fashion", "Communication", "Characteristic", "Weather"];
  const categories = Object.keys(groups).sort((a, b) => {
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi) || a.localeCompare(b);
  });
  const body = `
    <div class="catalog-toolbar">
      <input class="input" id="pref-search" placeholder="Search likes and dislikes…" value="${esc(picker.query)}" />
    </div>
    <div class="pref-current">
      <div class="pref-current-col">
        <h4>Current likes <span class="badge green">${(sim.likes || []).length}</span></h4>
        <div class="chips">${(sim.likes || []).map((l, i) => `<span class="chip">${esc(l.label.replace(/^Likes /, ""))}<button class="x" data-pref-remove="likes:${i}" title="Remove">✕</button></span>`).join("") || `<span class="chip-empty">No likes yet.</span>`}</div>
      </div>
      <div class="pref-current-col">
        <h4>Current dislikes <span class="badge">${(sim.dislikes || []).length}</span></h4>
        <div class="chips">${(sim.dislikes || []).map((l, i) => `<span class="chip" style="background:var(--gold-soft);border-color:#e3d49b;color:#6b5717">${esc(l.label.replace(/^Dislikes /, ""))}<button class="x" data-pref-remove="dislikes:${i}" title="Remove">✕</button></span>`).join("") || `<span class="chip-empty">No dislikes yet.</span>`}</div>
      </div>
    </div>
    <h4 style="margin:16px 0 8px;font-size:12px">Add a like or dislike</h4>
    <div class="pref-groups">
      ${categories
        .map(
          (cat) => `<div class="pref-group">
            <h4>${esc(cat)}</h4>
            ${groups[cat]
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((row) => {
                const st = prefState(sim, row);
                return `<div class="pref-row">
                  <span class="pref-name">${esc(row.name)}</span>
                  <button class="pref-toggle like ${st.inLikes ? "active" : ""}" data-pref-like="${esc(row.likeId)}" title="Like">Like</button>
                  <button class="pref-toggle dislike ${st.inDislikes ? "active" : ""}" data-pref-dislike="${esc(row.dislikeId)}" title="Dislike">Dislike</button>
                </div>`;
              })
              .join("")}
          </div>`
        )
        .join("") || `<div class="chip-empty">No preferences match.</div>`}
    </div>`;
  $("#modal-body").innerHTML = body;
  $("#pref-search").addEventListener("input", debounce((e) => {
    picker.query = e.target.value;
    renderPreferencesBody();
    const s = $("#pref-search");
    if (s) { s.focus(); s.setSelectionRange(s.value.length, s.value.length); }
  }, 250));
  $$("[data-pref-like]").forEach((btn) =>
    btn.addEventListener("click", () => togglePreference(sim, btn.dataset.prefLike, "like"))
  );
  $$("[data-pref-dislike]").forEach((btn) =>
    btn.addEventListener("click", () => togglePreference(sim, btn.dataset.prefDislike, "dislike"))
  );
  $$("[data-pref-remove]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const [field, index] = btn.dataset.prefRemove.split(":");
      sim[field] = (sim[field] || []).filter((_, i) => i !== Number(index));
      queueSave();
      renderPreferencesBody();
      renderStage();
    })
  );
}

function togglePreference(sim, idValue, mode) {
  if (!idValue) return;
  const picker = state.prefPicker;
  const row = [...picker.map.values()].find((r) => String(mode === "like" ? r.likeId : r.dislikeId) === String(idValue));
  if (!row) return;
  const target = mode === "like" ? "likes" : "dislikes";
  const other = mode === "like" ? "dislikes" : "likes";
  const base = row.name.toLowerCase();
  const isActive = (sim[target] || []).some((x) => x.label.toLowerCase().endsWith(base));
  sim[target] = (sim[target] || []).filter((x) => !x.label.toLowerCase().endsWith(base));
  sim[other] = (sim[other] || []).filter((x) => !x.label.toLowerCase().endsWith(base));
  if (!isActive) {
    const label = mode === "like" ? row.likeLabel : row.dislikeLabel;
    const id = mode === "like" ? row.likeId : row.dislikeId;
    if (label) sim[target].push({ id, label, modded: false });
  }
  queueSave();
  renderPreferencesBody();
  renderStage();
  renderSummary();
}

/* ------------------------------------------------------------------- saving */
function queueSave() {
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(async () => {
    try {
      await api("/api/project/save", { method: "POST", body: JSON.stringify({ project: state.project }) });
    } catch (err) {
      toast("Could not save project: " + err.message, "err");
    }
  }, 450);
}

/* -------------------------------------------------------------------- modal */
function openModal(title, bodyHtml, footHtml = "", narrow = false) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = bodyHtml;
  $("#modal-foot").innerHTML = footHtml;
  $("#modal-box").classList.toggle("narrow", narrow);
  $("#modal").classList.remove("hidden");
  state.modalPick = null;
  state.modalMulti = false;
  state.modalKind = null;
}

function closeModal() {
  $("#modal").classList.add("hidden");
  if (state.scanTimer) { clearInterval(state.scanTimer); state.scanTimer = null; }
}

/* ------------------------------------------------------------ replace from tray */
async function openTrayReplace(target) {
  if (!state.tray?.length) {
    try {
      state.tray = (await api("/api/tray")).households || [];
    } catch (err) {
      toast(err.message, "err");
      return;
    }
  }
  const body = `
    <p class="hint">Choose a Tray household, then a sim. Its traits, skills, career, aspiration, likes and portrait will be copied onto <strong>${esc(target.first)} ${esc(target.last)}</strong>. The premade name and household stay the same so the mod still targets the right sim.</p>
    <input class="input" id="replace-search" placeholder="Search Tray households or sims…" />
    <div class="list" id="replace-list" style="max-height:52vh;overflow:auto;margin-top:10px"></div>`;
  openModal("Replace from Tray", body, `<button class="btn" id="replace-cancel">Cancel</button>`, true);
  $("#replace-cancel").addEventListener("click", closeModal);

  const renderList = (query = "") => {
    const q = query.toLowerCase();
    const items = [...state.tray]
      .filter((h) => !q || `${h.household} ${h.sims.map((s) => `${s.first} ${s.last}`).join(" ")}`.toLowerCase().includes(q))
      .sort((a, b) => a.household.localeCompare(b.household))
      .slice(0, 200);
    $("#replace-list").innerHTML =
      items
        .map(
          (h) => `<div class="list-item" data-replace-hh="${esc(h.id)}">
            ${h.household_image ? `<img class="list-thumb" src="${esc(h.household_image)}" style="${maskStyle(h.household_image_mask)}" alt="" />` : ""}
            <div class="list-who"><strong>${esc(h.household)}</strong><span>${h.sims.length} sim${h.sims.length === 1 ? "" : "s"} · ${esc(h.modified_label)}</span></div>
          </div>`
        )
        .join("") || `<div class="chip-empty">No matching Tray households.</div>`;
    $$("[data-replace-hh]").forEach((el) =>
      el.addEventListener("click", () => loadReplaceHousehold(el.dataset.replaceHh))
    );
  };

  const loadReplaceHousehold = async (id) => {
    $("#replace-list").innerHTML = `<div class="progress-wrap"><span class="spinner"></span> Reading sim data…</div>`;
    try {
      const hh = await api(`/api/tray/household?id=${encodeURIComponent(id)}`);
      state._replaceHousehold = hh;
      $("#replace-list").innerHTML = hh.sims
        .map(
          (s, i) => `<div class="list-item">
            ${s.image ? `<img class="list-thumb" src="${esc(s.image)}" style="${maskStyle(s.image_mask)}" alt="" />` : ""}
            <div class="list-who"><strong>${esc(s.first)} ${esc(s.last)}</strong><span>${esc(s.age || "")} · ${esc(s.gender || "")} · ${(s.traits || []).length} traits · ${(s.skills || []).length} skills</span></div>
            <button class="btn sm primary" data-use-tray="${i}">Use data</button>
          </div>`
        )
        .join("");
      $$("[data-use-tray]").forEach((btn) =>
        btn.addEventListener("click", () => applyTrayReplacement(target, hh, Number(btn.dataset.useTray)))
      );
    } catch (err) {
      $("#replace-list").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`;
    }
  };

  $("#replace-search").addEventListener("input", (e) => renderList(e.target.value));
  renderList("");
}

function applyTrayReplacement(target, household, index) {
  const source = household.sims[index];
  if (!source) return;
  const nameMap = {};
  household.sims.forEach((s) => {
    nameMap[`${s.first}|${s.last}`] = s.key;
  });
  const projectByName = {};
  Object.values(state.project.sims || {}).forEach((s) => {
    projectByName[`${s.first}|${s.last}`] = s.key;
  });
  const projectKeyFor = (trayKey) => {
    const sourceSim = household.sims.find((s) => s.key === trayKey);
    if (!sourceSim) return null;
    return projectByName[`${sourceSim.first}|${sourceSim.last}`] || null;
  };

  for (const field of ["age", "gender", "species", "occult", "traits", "likes", "dislikes", "degrees", "skills", "career", "career_history", "aspiration", "milestones", "image"]) {
    if (field in source) target[field] = JSON.parse(JSON.stringify(source[field] ?? null));
  }
  target.relationships = (source.relationships || [])
    .map((rel) => ({ ...rel, target: projectKeyFor(rel.target) }))
    .filter((rel) => rel.target);
  target.family = (source.family || [])
    .map((fam) => ({ ...fam, target: projectKeyFor(fam.target) }))
    .filter((fam) => fam.target);
  target.data_quality = "tray_replace";
  target.data_source = "Tray library";
  queueSave();
  renderAll();
  closeModal();
  toast(`Replaced ${target.first} ${target.last} with Tray data`, "ok");
}

/* --------------------------------------------------------------- save browser */
async function openSavesModal() {
  openModal("Save Browser", `<div class="progress-wrap"><span class="spinner"></span> Loading saves…</div>`, "", true);
  try {
    const data = await api("/api/saves");
    state.saves = data.saves;
    const body = `
      <div class="browser-grid">
        <div class="browser-side">
          ${state.saves.map((s) => `<div class="list-item" data-save="${esc(s.file)}">
            <strong>${esc(s.slot)}</strong><span>${esc(s.modified_label)} · ${(s.size / 1024 / 1024).toFixed(1)} MB</span>
          </div>`).join("") || `<div class="chip-empty">No saves found.</div>`}
        </div>
        <div class="browser-main" id="save-main"><div class="empty-stage"><h2>Pick a save</h2><p>Your saves are opened read-only. Nothing is written back.</p></div></div>
      </div>`;
    openModal("Save Browser", body);
    $$("[data-save]").forEach((el) => el.addEventListener("click", () => loadSaveInModal(el.dataset.save, el)));
  } catch (err) {
    openModal("Save Browser", `<div class="chip-empty">${esc(err.message)}</div>`);
  }
}

async function loadSaveInModal(file, el) {
  $$("[data-save]").forEach((x) => x.classList.toggle("active", x === el));
  $("#save-main").innerHTML = `<div class="progress-wrap"><span class="spinner"></span> Reading ${esc(file)}… <span class="muted">(large saves take a few seconds)</span></div>`;
  try {
    const save = await api(`/api/save?file=${encodeURIComponent(file)}`);
    state.save = save;
    renderSaveMain(file);
  } catch (err) {
    $("#save-main").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`;
  }
}

function renderSaveMain(file) {
  const save = state.save;
  const sims = save.sims || [];
  const groups = {};
  sims.forEach((s) => (groups[s.household || s.last] ||= []).push(s));
  const grid = Object.keys(groups)
    .sort()
    .map(
      (g) => `<div class="hh-label">${groups[g][0]?.household_image ? `<img class="hh-img" src="${esc(groups[g][0].household_image)}" style="${maskStyle(groups[g][0].household_image_mask)}" alt="" />` : ""}${esc(g)} <button class="btn sm ghost" data-add-save-group="${esc(g)}">Add household</button></div>
      <div class="sim-grid">${groups[g]
        .map(
          (s) => `<div class="sim-card">
            <div class="mini-avatar ${s.image ? "has-photo" : ""}">${s.image ? `<img class="portrait-img" src="${esc(s.image)}" style="${maskStyle(s.image_mask)}" alt="" />` : esc(initials(s.first, s.last))}</div>
            <div class="who"><strong>${esc(s.first)} ${esc(s.last)}</strong><span>${esc(s.household)} · ${(s.traits || []).length} traits · ${(s.skills || []).length} skills</span></div>
            ${qualityBadge(s)}
            <button class="btn sm" data-add-save="${esc(s.key)}">Add</button>
          </div>`
        )
        .join("")}</div>`
    )
    .join("");

  $("#save-main").innerHTML = `
    ${save.thumbnail ? `<div class="save-hero" style="background-image:url('${save.thumbnail}')"></div>` : ""}
    <div class="catalog-toolbar">
      <strong>${sims.length} sims found</strong>
      <span class="muted" style="font-size:12px">${esc(file)}</span>
      <button class="btn sm primary" data-add-save-all>Add all sims</button>
    </div>
    ${grid || `<div class="chip-empty">No sims found in this save.</div>`}`;

  $$("[data-add-save]").forEach((btn) =>
    btn.addEventListener("click", () => addSimsToProject([simByKey(btn.dataset.addSave)].filter(Boolean), file))
  );
  $$("[data-add-save-group]").forEach((btn) =>
    btn.addEventListener("click", () => addSimsToProject(groups[btn.dataset.addSaveGroup], file))
  );
  $("[data-add-save-all]")?.addEventListener("click", () => addSimsToProject(sims, file));
}

/* --------------------------------------------------------------- tray browser */
async function openTrayModal() {
  openModal("Tray Library", `<div class="progress-wrap"><span class="spinner"></span> Reading your Tray…</div>`, "", true);
  try {
    const data = await api("/api/tray");
    state.tray = data.households;
    const body = `
      <div class="browser-grid">
        <div class="browser-side">
          <div class="search-wrap" style="margin:0 0 10px">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>
            <input id="tray-search" placeholder="Search households…" />
          </div>
          <div id="tray-list"></div>
        </div>
        <div class="browser-main" id="tray-main"><div class="empty-stage"><h2>Pick a Tray household</h2><p>Tray files are strictly read-only. Sims are added to the project as blueprints.</p></div></div>
      </div>`;
    openModal("Tray Library", body);
    renderTraySide("");
    $("#tray-search").addEventListener("input", (e) => renderTraySide(e.target.value));
  } catch (err) {
    openModal("Tray Library", `<div class="chip-empty">${esc(err.message)}</div>`);
  }
}

function renderTraySide(query) {
  const q = (query || "").toLowerCase();
  const items = [...state.tray]
    .filter((h) => !q || `${h.household} ${h.sims.map((s) => `${s.first} ${s.last}`).join(" ")}`.toLowerCase().includes(q))
    .sort((a, b) => a.household.localeCompare(b.household));
  $("#tray-list").innerHTML =
    items
      .map(
        (h) => `<div class="list-item" data-tray="${esc(h.id)}">
          ${h.household_image ? `<img class="list-thumb" src="${esc(h.household_image)}" style="${maskStyle(h.household_image_mask)}" alt="" />` : ""}
          <div class="list-who"><strong>${esc(h.household)}</strong>
          <span>${h.sims.length} sim${h.sims.length === 1 ? "" : "s"} · ${esc(h.modified_label)}</span></div>
        </div>`
      )
      .join("") || `<div class="chip-empty">No households match your search.</div>`;
  $$("[data-tray]").forEach((el) => el.addEventListener("click", () => renderTrayMain(el.dataset.tray, el)));
}

async function renderTrayMain(id, el) {
  $$("[data-tray]").forEach((x) => x.classList.toggle("active", x === el));
  $("#tray-main").innerHTML = `<div class="progress-wrap"><span class="spinner"></span> Reading sim data…</div>`;
  let household;
  try {
    household = await api(`/api/tray/household?id=${encodeURIComponent(id)}`);
  } catch (err) {
    $("#tray-main").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`;
    return;
  }
  state.trayRich = state.trayRich || {};
  state.trayRich[id] = household;
  const quality = household.quality === "full"
    ? `<span class="quality-badge full">Full game data</span>`
    : `<span class="quality-badge names">Name only</span>`;
  $("#tray-main").innerHTML = `
    ${household.household_image ? `<img class="tray-hero" src="${esc(household.household_image)}" style="${maskStyle(household.household_image_mask)}" alt="" />` : ""}
    <div class="catalog-toolbar"><strong>${esc(household.household)}</strong> ${quality}
      <button class="btn sm primary" data-add-tray-all>Add household to project</button></div>
    <div class="tray-rich">
      ${household.sims
        .map(
          (s) => `<div class="tray-sim-card">
            <div class="row">
              <div class="tray-who">
                <div class="mini-avatar ${s.image ? "has-photo" : ""}">${s.image ? `<img class="portrait-img" src="${esc(s.image)}" style="${maskStyle(s.image_mask)}" alt="" />` : esc(initials(s.first, s.last))}</div>
                <div>
                <h4>${esc(s.first)} ${esc(s.last)}</h4>
                <div class="meta">${esc(s.age || "Adult")} · ${esc(s.gender || "Female")} · ${esc(s.occult || "Human")}${s.career ? ` · ${esc(s.career.label)} Lv ${s.career.level}` : ""}</div>
                </div>
              </div>
              <button class="btn sm" data-add-tray="${esc(s.key)}">Add</button>
            </div>
            <div class="mini-chips">
              ${(s.traits || []).slice(0, 10).map((t) => `<span class="mini-chip2 ${t.modded ? "modded" : ""}">${esc(t.label)}</span>`).join("") || `<span class="mini-chip2">No traits read</span>`}
            </div>
            ${
              (s.skills || []).length
                ? `<div class="mini-chips">${s.skills.slice(0, 8).map((k) => `<span class="mini-chip2">${esc(k.label)} ${k.level}</span>`).join("")}</div>`
                : ""
            }
            ${
              (s.likes || []).length || (s.dislikes || []).length
                ? `<div class="meta" style="margin-top:6px">${s.likes.length} likes · ${s.dislikes.length} dislikes</div>`
                : ""
            }
          </div>`
        )
        .join("")}
    </div>
    <p class="muted" style="font-size:12px;margin-top:18px">Read from <code>${esc(id)}</code>. Tray files are never modified. To apply overhauls to these sims in a new save, place the household from the Gallery first — the exported mod matches them by name and household.</p>`;

  $$("[data-add-tray]").forEach((btn) =>
    btn.addEventListener("click", () =>
      addSimsToProject([household.sims.find((s) => s.key === btn.dataset.addTray)].filter(Boolean), id)
    )
  );
  $("[data-add-tray-all]")?.addEventListener("click", () => addSimsToProject(household.sims, id));
}

/* ------------------------------------------------------------------- catalog */
async function openCatalog(kind, onPick, multi, initialQuery = "") {
  const titles = {
    traits: "Trait Catalog",
    aspirations: "Aspiration Catalog",
    skills: "Skill Catalog",
    careers: "Career Catalog",
    degrees: "Degree Catalog",
    career_tracks: "Career Track Catalog",
    milestones: "Milestone Catalog",
    preferences: "Likes & Dislikes Catalog",
    relationship_bits: "Relationship Bits & Sentiments",
  };
  openModal(titles[kind] || "Catalog", `<div class="progress-wrap"><span class="spinner"></span> Loading catalog…</div>`, "", false);
  state.modalPick = onPick;
  state.modalMulti = multi;
  state.modalKind = kind;
  state.catalogFamily = kind === "career_tracks" ? initialQuery : "";
  state.sourceFilter = "all";
  state.includeBatuu = false;
  state.includeNpc = false;
  state.ageFilter = true;
  if (multi) {
    $("#modal-foot").innerHTML = `<button class="btn primary" id="cat-done">Done</button>`;
    $("#cat-done").addEventListener("click", closeModal);
  }
  await renderCatalog(kind, initialQuery);
}

function conditionGuideHtml(kind) {
  if (kind !== "traits") return "";
  const guide = state.gamedata?.condition_guide || [];
  if (!guide.length) return "";
  return `<details class="cond-guide">
    <summary>What the trait categories mean</summary>
    <div class="cond-guide-list">
      ${guide.map((g) => `<div class="cond-guide-row"><strong>${esc(g.label)}</strong><span>${esc(g.detail)}</span></div>`).join("")}
    </div>
  </details>`;
}

function catalogRow(item, kind) {
  const cond = item.condition;
  const condHtml = cond
    ? `<div class="cat-cond">${esc(cond.label)} · ${esc(cond.source)} — ${esc(cond.detail)}</div>`
    : "";
  return `<div class="cat-row">
    ${item.icon ? `<img class="cat-icon" src="${esc(item.icon)}" alt="" />` : `<span class="cat-icon cat-icon-empty"></span>`}
    <div class="label">${esc(item.label)} ${item.modded ? `<img class="mod-icon" src="/icons/x_mods.png" title="Modded content" alt="MOD" />` : ""}
      ${item.age_hint ? `<span class="mini-chip2">${esc(item.age_hint)}</span>` : ""}
      ${item.species_hint && item.species_hint !== "Human" ? `<span class="mini-chip2">${esc(item.species_hint)} only</span>` : ""}
      ${item.occult_hint ? `<span class="mini-chip2">${esc(item.occult_hint)} only</span>` : ""}
      <div class="cat-meta">${esc(itemMeta(item, kind))}</div>
      ${itemDescription(item) ? `<div class="cat-desc">${esc(itemDescription(item))}</div>` : ""}
      ${item.hint ? `<div class="cat-desc">${esc(item.hint)}</div>` : ""}
      ${condHtml}
      <div class="tuning">${esc(item.tuning)}</div>
    </div>
    <span class="pack">${esc(item.pack_label || item.pack || "")}</span>
    <button class="btn sm ${item.modded ? "" : "ghost"}" data-pick="${esc(JSON.stringify(item))}">Add</button>
  </div>`;
}

function groupCatalogItems(kind, items) {
  if (kind === "careers") {
    const defs = state.gamedata?.career_groups || [];
    const byId = Object.fromEntries(defs.map((d) => [d.id, d]));
    const order = defs.map((d) => d.id).concat(["other"]);
    const buckets = {};
    items.forEach((i) => (buckets[i.group || "other"] ||= []).push(i));
    return [...new Set(order)]
      .filter((id) => buckets[id]?.length)
      .map((id) => ({ label: byId[id]?.label || id, hint: byId[id]?.hint || "", items: buckets[id] }));
  }
  if (kind === "career_tracks") {
    const buckets = {};
    items.forEach((i) => (buckets[i.family || "Other"] ||= []).push(i));
    return Object.keys(buckets).sort().map((f) => ({ label: f, hint: "Branches of this career", items: buckets[f] }));
  }
  if (kind === "degrees") {
    const majors = state.gamedata?.majors || [];
    const order = majors.map((m) => m.id).concat(["Other"]);
    const buckets = {};
    items.forEach((i) => (buckets[i.major || "Other"] ||= []).push(i));
    return [...new Set(order)]
      .filter((id) => buckets[id]?.length)
      .map((id) => {
        const m = majors.find((x) => x.id === id);
        return { label: id, hint: m ? `${m.skill} · boosts ${m.careers.join(", ")}` : "", items: buckets[id] };
      });
  }
  return null;
}

async function renderCatalog(kind, query) {
  try {
    const sim = currentSim();
    const age = sim && state.ageFilter ? sim.age : "";
    const species = sim && kind === "traits" ? sim.species || "Human" : "";
    const occult = sim && kind === "traits" ? (sim.occult && sim.occult !== "Human" ? sim.occult : "Human") : "";
    const url =
      `/api/catalog?kind=${encodeURIComponent(kind)}` +
      `&source=${state.sourceFilter}` +
      `&q=${encodeURIComponent(query)}` +
      `&batuu=${state.includeBatuu ? 1 : 0}` +
      `&npc=${state.includeNpc ? 1 : 0}` +
      `&age=${encodeURIComponent(age || "")}` +
      `&species=${encodeURIComponent(species || "")}` +
      `&occult=${encodeURIComponent(occult || "")}`;
    const data = await api(url);
    state.catalogMeta = data.meta;
    let items = data.items.slice(0, 600);
    // The shared pre-branch track is not a specialisation, and a career's
    // branch picker only shows that career's own branches.
    if (kind === "career_tracks") {
      const family = state.catalogFamily || "";
      items = items.filter((i) => !isMainCareerTrack(i) && (!family || i.family === family));
    }
    const showAge = sim && ["traits", "aspirations", "skills", "careers", "milestones"].includes(kind);
    const groups = groupCatalogItems(kind, items);
    const listHtml = groups
      ? groups
          .map(
            (g) => `<div class="cat-group">
              <div class="cat-group-head"><strong>${esc(g.label)}</strong><span>${g.items.length}</span>${g.hint ? `<em>${esc(g.hint)}</em>` : ""}</div>
              ${g.items.map((item) => catalogRow(item, kind)).join("")}
            </div>`
          )
          .join("")
      : items.map((item) => catalogRow(item, kind)).join("");
    const body = `
      <div class="catalog-toolbar">
        <input class="input" id="cat-search" placeholder="Search ${esc(kind.replace(/_/g, " "))}…" value="${esc(query)}" />
        <div class="seg" id="cat-source">
          <button data-src="all" class="${state.sourceFilter === "all" ? "active" : ""}">All</button>
          <button data-src="ea" class="${state.sourceFilter === "ea" ? "active" : ""}">EA</button>
          <button data-src="mod" class="${state.sourceFilter === "mod" ? "active" : ""}">Mods only</button>
        </div>
      </div>
      <div class="catalog-toggles">
        <label class="toggle"><input type="checkbox" id="cat-batuu" ${state.includeBatuu ? "checked" : ""}/> Include Batuu (GP09)</label>
        <label class="toggle"><input type="checkbox" id="cat-npc" ${state.includeNpc ? "checked" : ""}/> Include NPC / service jobs</label>
        ${
          showAge
            ? `<label class="toggle"><input type="checkbox" id="cat-age" ${state.ageFilter ? "checked" : ""}/> Only compatible with ${esc(sim.age)}</label>`
            : ""
        }
      </div>
      ${conditionGuideHtml(kind)}
      ${kind === "aspirations" ? `<div class="catalog-note">Aspirations are shown once per aspiration. The game applies the later tiers automatically, so A2/A3/A4 are hidden.</div>` : ""}
      ${kind === "degrees" ? `<div class="catalog-note">Degrees are stored as traits by the game. Each major has a standard and an Honours BA/BS; a degree gives a head start in the listed careers.</div>` : ""}
      ${kind === "careers" ? `<div class="catalog-note">Grouped by career type. Switch on <em>Include NPC / service jobs</em> to see the roles the game assigns to townies.</div>` : ""}
      <div class="catalog-list">
        ${data.items.length > 600 ? `<div class="chip-empty" style="padding:0 0 8px">Showing the first 600 matches — refine your search to narrow the list.</div>` : ""}
        ${listHtml || `<div class="chip-empty">No matches. Try clearing the age filter, including Batuu, or rescanning content.</div>`}
      </div>`;
    $("#modal-body").innerHTML = body;

    $("#cat-search").addEventListener("input", debounce((e) => renderCatalog(kind, e.target.value), 300));
    if (query) {
      const search = $("#cat-search");
      if (search) {
        search.focus();
        search.setSelectionRange(search.value.length, search.value.length);
      }
    }
    $$("#cat-source button").forEach((btn) =>
      btn.addEventListener("click", () => {
        state.sourceFilter = btn.dataset.src;
        renderCatalog(kind, $("#cat-search")?.value || "");
      })
    );
    $("#cat-batuu")?.addEventListener("change", (e) => {
      state.includeBatuu = e.target.checked;
      renderCatalog(kind, $("#cat-search")?.value || "");
    });
    $("#cat-npc")?.addEventListener("change", (e) => {
      state.includeNpc = e.target.checked;
      renderCatalog(kind, $("#cat-search")?.value || "");
    });
    $("#cat-age")?.addEventListener("change", (e) => {
      state.ageFilter = e.target.checked;
      renderCatalog(kind, $("#cat-search")?.value || "");
    });
    $$("[data-pick]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const item = JSON.parse(btn.dataset.pick);
        if (state.modalPick) state.modalPick(item);
        toast(`Added ${item.label}`, "ok");
        if (!state.modalMulti) closeModal();
      })
    );
  } catch (err) {
    $("#modal-body").innerHTML = `<div class="chip-empty">${esc(err.message)}</div>`;
  }
}

function debounce(fn, wait) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function itemKindLabel(kind) {
  return {
    traits: "Personality trait",
    preferences: "Likes / dislikes",
    aspirations: "Aspiration",
    skills: "Skill",
    careers: "Career",
    degrees: "University degree",
    milestones: "Milestone",
    relationship_bits: "Relationship bit / sentiment",
    career_tracks: "Career track",
  }[kind] || "Content";
}

function itemMeta(item, kind) {
  const cond = item.condition;
  const bits = [cond?.label || item.icon_group || itemKindLabel(kind), item.pack_label || item.pack || "Base Game"];
  if (item.age_hint) bits.push(`${item.age_hint} only`);
  if (item.species_hint && item.species_hint !== "Human") bits.push(`${item.species_hint} only`);
  if (item.occult_hint) bits.push(`${item.occult_hint} only`);
  if (bits.length === 2) bits.push("Always assignable");
  return bits.join(" · ");
}

function itemDescription(item) {
  return ITEM_DESCRIPTIONS[item.label] || "";
}

/* -------------------------------------------------------------------- adding */
async function addSimsToProject(sims, sourceRef) {
  const payload = sims.map((s) => ({ ...s, household: s.household || s.last }));
  try {
    const data = await api("/api/project/add_sims", {
      method: "POST",
      body: JSON.stringify({ sims: payload, source_ref: sourceRef }),
    });
    state.project = data.project;
    state.selected = data.added[0]?.key || state.selected;
    renderAll();
    toast(`Added ${data.added.length} sim${data.added.length === 1 ? "" : "s"} to the project`, "ok");
  } catch (err) {
    toast(err.message, "err");
  }
}

/* ------------------------------------------------------------------- scanning */
function openScanModal(auto) {
  openModal(
    "Content Scanner",
    `<div class="progress-wrap">
      <div id="scan-status"><span class="spinner"></span> Preparing scan…</div>
      <div class="progress-bar"><span id="scan-bar"></span></div>
      <div class="progress-meta"><span id="scan-current"></span><span id="scan-total"></span></div>
      <p class="muted" style="font-size:12px;line-height:1.6">The scanner reads your installed packs and your Mods folder to build a local catalog of traits, skills, careers, aspirations, milestones and preferences. Nothing is written into your game folder.</p>
    </div>`,
    auto ? "" : `<button class="btn" id="rescan-btn">Rescan now</button>`,
    true
  );
  if (!auto) $("#rescan-btn")?.addEventListener("click", startScan);
  pollScan();
}

async function startScan() {
  try {
    await api("/api/catalog/scan", { method: "POST", body: "{}" });
    pollScan();
  } catch (err) {
    toast(err.message, "err");
  }
}

function pollScan() {
  clearInterval(state.scanTimer);
  state.scanTimer = setInterval(async () => {
    try {
      const s = await api("/api/catalog/status");
      updateScanUi(s);
      if (!s.running) {
        clearInterval(state.scanTimer);
        state.scanTimer = null;
        if (s.done) {
          state.catalogMeta = { counts: s.counts, seconds: s.seconds };
          state.catalog = {};
          $("#scan-status").innerHTML = `<span class="badge green">Scan complete</span> <span class="muted">${s.seconds}s</span>`;
          $("#scan-bar").style.width = "100%";
          const counts = s.counts || {};
          $("#scan-current").textContent = `${counts.traits || 0} traits · ${counts.skills || 0} skills · ${counts.careers || 0} careers`;
          $("#scan-total").textContent = `${counts.aspirations || 0} aspirations · ${counts.milestones || 0} milestones`;
          setBanner("");
        }
      }
    } catch (err) {
      clearInterval(state.scanTimer);
      state.scanTimer = null;
    }
  }, 700);
}

async function pollScanOnce() {
  try {
    const s = await api("/api/catalog/status");
    if (s.running) { setBanner(`Scanning game content… ${s.message}`); pollScan(); }
    else if (s.done) updateScanUi(s);
  } catch (err) { /* ignore */ }
}

function updateScanUi(s) {
  const status = $("#scan-status");
  if (!status) return;
  const pct = s.total ? Math.min(100, Math.round((s.current / s.total) * 100)) : 0;
  status.innerHTML = `${s.running ? `<span class="spinner"></span>` : ""} ${esc(s.message || "Working…")}`;
  const bar = $("#scan-bar");
  if (bar) bar.style.width = `${pct}%`;
  const cur = $("#scan-current");
  if (cur) cur.textContent = s.total ? `${s.current} / ${s.total}` : "";
  const total = $("#scan-total");
  if (total) total.textContent = `${pct}%`;
  if (s.running) setBanner(`Scanning game content… ${s.message} (${pct}%)`);
}

function setBanner(text) {
  const el = $("#banner");
  if (!text) { el.classList.add("hidden"); el.innerHTML = ""; return; }
  el.classList.remove("hidden");
  el.innerHTML = `<span class="spinner"></span><span>${esc(text)}</span>`;
}

/* -------------------------------------------------------------------- export */
async function doExport() {
  if (!Object.keys(state.project.sims || {}).length) {
    toast("Add at least one sim before exporting.", "err");
    return;
  }
  await api("/api/project/save", { method: "POST", body: JSON.stringify({ project: state.project }) });
  openModal("Exporting…", `<div class="progress-wrap"><span class="spinner"></span> Building .ts4script…</div>`, "", true);
  try {
    const data = await api("/api/export", { method: "POST", body: "{}" });
    const r = data.result;
    openModal(
      "Overhaul mod exported",
      `<div class="card">
        <h3>Ready to install</h3>
        <p class="hint">Copy the <code>.ts4script</code> into your Mods folder, then start a new save (or run <code>simoverhaul.apply</code> in the cheat console).</p>
        <div class="sum-item"><span>File</span><strong>${esc(r.ts4script.split(/[\\/]/).pop())}</strong></div>
        <div class="sum-item" style="margin-top:8px"><span>Sims</span><strong>${r.sims}</strong></div>
        <div class="field" style="margin-top:14px"><label>Export folder</label><input class="input" readonly value="${esc(r.folder)}" /></div>
      </div>`,
      `<button class="btn" id="copy-path">Copy folder path</button><button class="btn primary" id="close-export">Done</button>`,
      true
    );
    $("#close-export").addEventListener("click", closeModal);
    $("#copy-path").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(r.folder); toast("Path copied", "ok"); } catch { toast("Could not copy", "err"); }
    });
  } catch (err) {
    openModal("Export failed", `<div class="chip-empty">${esc(err.message)}</div>`, `<button class="btn" id="close-export">Close</button>`, true);
    $("#close-export").addEventListener("click", closeModal);
  }
}

boot();
