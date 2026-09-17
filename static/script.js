/* AI Story Voice Studio – Single Voice Frontend */

const MAX_CHARS = 50000;
const POLL_INTERVAL = 900;

const $ = (id) => document.getElementById(id);

const PRESETS = {
  male: [
    { key: "male_normal", label: "Male Normal" },
    { key: "male_soft", label: "Male Soft" },
    { key: "male_deep", label: "Male Deep" },
    { key: "male_mature", label: "Male Mature" },
  ],
  female: [
    { key: "female_normal", label: "Female Normal" },
    { key: "female_soft", label: "Female Soft" },
    { key: "female_sweet", label: "Female Sweet" },
    { key: "female_mature", label: "Female Mature" },
  ],
};

const els = {
  textInput: $("textInput"),
  charCount: $("charCount"),
  maxChars: $("maxChars"),
  draftStatus: $("draftStatus"),
  modeTabs: document.querySelectorAll(".mode-tab"),
  voiceGender: $("voiceGender"),
  voicePreset: $("voicePreset"),
  pitchSlider: $("pitchSlider"),
  pitchVal: $("pitchVal"),
  globalEmotion: $("globalEmotion"),
  emotionIntensity: $("emotionIntensity"),
  autoEmotion: $("autoEmotion"),
  qualitySelect: $("qualitySelect"),
  speedMode: $("speedMode"),
  hinglishMode: $("hinglishMode"),
  previewBtn: $("previewBtn"),
  analyzeBtn: $("analyzeBtn"),
  generateBtn: $("generateBtn"),
  cancelBtn: $("cancelBtn"),
  btnLoader: $("btnLoader"),
  progressFill: $("progressFill"),
  progressPct: $("progressPct"),
  progressStage: $("progressStage"),
  progressDetail: $("progressDetail"),
  etaText: $("etaText"),
  statChars: $("statChars"),
  statWords: $("statWords"),
  statDuration: $("statDuration"),
  statMode: $("statMode"),
  statVoice: $("statVoice"),
  statQuality: $("statQuality"),
  audioSection: $("audioSection"),
  audioPlayer: $("audioPlayer"),
  downloadBtn: $("downloadBtn"),
  newBtn: $("newBtn"),
  analysisCard: $("analysisCard"),
  analysisContent: $("analysisContent"),
  messageContainer: $("messageContainer"),
  themeToggle: $("themeToggle"),
  sidebar: $("sidebar"),
  sidebarToggle: $("sidebarToggle"),
};

let currentMode = "normal";
let currentJobId = null;
let pollTimer = null;
let draftTimer = null;
const STORAGE_KEY = "story_voice_studio_v2";

function applyTheme(theme) {
  if (theme === "system") {
    theme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("svs_theme", theme);
}
els.themeToggle.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(cur === "dark" ? "light" : "dark");
});
applyTheme(localStorage.getItem("svs_theme") || "dark");

els.sidebarToggle.addEventListener("click", () => {
  els.sidebar.classList.toggle("open");
});

els.modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    els.modeTabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentMode = tab.dataset.mode;
    updateStats();
    scheduleDraft();
  });
});

function fillPresets(gender) {
  const list = PRESETS[gender] || PRESETS.female;
  els.voicePreset.innerHTML = list
    .map((p) => `<option value="${p.key}">${p.label}</option>`)
    .join("");
}

els.voiceGender.addEventListener("change", () => {
  fillPresets(els.voiceGender.value);
  updateStats();
  scheduleDraft();
});
els.voicePreset.addEventListener("change", () => {
  updateStats();
  scheduleDraft();
});

els.pitchSlider.addEventListener("input", () => {
  els.pitchVal.textContent = Number(els.pitchSlider.value).toFixed(1);
  scheduleDraft();
});

function updateCharCount() {
  const n = els.textInput.value.length;
  els.charCount.textContent = n.toLocaleString();
  const bar = els.charCount.parentElement;
  if (n > MAX_CHARS * 0.9) bar.style.color = "var(--danger)";
  else if (n > MAX_CHARS * 0.7) bar.style.color = "var(--warning)";
  else bar.style.color = "var(--text-muted)";
  updateStats();
}

function updateStats() {
  const text = els.textInput.value;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  els.statChars.textContent = text.length.toLocaleString() + " / " + MAX_CHARS.toLocaleString();
  els.statWords.textContent = words.toLocaleString();
  const mins = words ? Math.max(1, Math.round(words / 130)) : 0;
  els.statDuration.textContent = mins ? "~" + mins + " min" : "—";
  els.statMode.textContent = currentMode.charAt(0).toUpperCase() + currentMode.slice(1);
  const opt = els.voicePreset.options[els.voicePreset.selectedIndex];
  els.statVoice.textContent = opt ? opt.text : "—";
  els.statQuality.textContent = els.qualitySelect.value;
}

els.textInput.addEventListener("input", () => {
  updateCharCount();
  scheduleDraft();
});

function showMessage(msg, type) {
  type = type || "info";
  const div = document.createElement("div");
  div.className = "message " + type;
  div.textContent = msg;
  els.messageContainer.innerHTML = "";
  els.messageContainer.appendChild(div);
  if (type !== "info") setTimeout(() => div.remove(), 6000);
}
function clearMessages() {
  els.messageContainer.innerHTML = "";
}

function scheduleDraft() {
  els.draftStatus.textContent = "Saving…";
  clearTimeout(draftTimer);
  draftTimer = setTimeout(saveDraft, 600);
}

function saveDraft() {
  const data = {
    text: els.textInput.value,
    mode: currentMode,
    voiceGender: els.voiceGender.value,
    voicePreset: els.voicePreset.value,
    pitch: els.pitchSlider.value,
    globalEmotion: els.globalEmotion.value,
    emotionIntensity: els.emotionIntensity.value,
    autoEmotion: els.autoEmotion.checked,
    quality: els.qualitySelect.value,
    speedMode: els.speedMode.value,
    hinglish: els.hinglishMode.checked,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    els.draftStatus.textContent = "Saved";
    setTimeout(() => {
      if (els.draftStatus.textContent === "Saved") els.draftStatus.textContent = "";
    }, 2000);
  } catch (e) {
    els.draftStatus.textContent = "";
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const d = JSON.parse(raw);
    if (d.text) els.textInput.value = d.text;
    if (d.mode) {
      currentMode = d.mode;
      els.modeTabs.forEach((t) => t.classList.toggle("active", t.dataset.mode === d.mode));
    }
    if (d.voiceGender) {
      els.voiceGender.value = d.voiceGender;
      fillPresets(d.voiceGender);
    }
    if (d.voicePreset) els.voicePreset.value = d.voicePreset;
    if (d.pitch != null) {
      els.pitchSlider.value = d.pitch;
      els.pitchVal.textContent = Number(d.pitch).toFixed(1);
    }
    if (d.globalEmotion) els.globalEmotion.value = d.globalEmotion;
    if (d.emotionIntensity) els.emotionIntensity.value = d.emotionIntensity;
    if (d.autoEmotion != null) els.autoEmotion.checked = d.autoEmotion;
    if (d.quality) els.qualitySelect.value = d.quality;
    if (d.speedMode) els.speedMode.value = d.speedMode;
    if (d.hinglish != null) els.hinglishMode.checked = d.hinglish;
  } catch (e) {}
}

function buildJobPayload() {
  return {
    text: els.textInput.value,
    mode: currentMode,
    voice_gender: els.voiceGender.value,
    voice_preset: els.voicePreset.value,
    pitch: parseFloat(els.pitchSlider.value) || 0,
    global_emotion: els.globalEmotion.value,
    emotion_intensity: els.emotionIntensity.value,
    auto_emotion: els.autoEmotion.checked,
    quality: els.qualitySelect.value,
    speed_mode: els.speedMode.value,
    hinglish: els.hinglishMode.checked,
  };
}

function validate() {
  const t = els.textInput.value.trim();
  if (!t) {
    showMessage("कृपया कुछ पाठ दर्ज करें", "error");
    return false;
  }
  if (t.length > MAX_CHARS) {
    showMessage("पाठ " + MAX_CHARS.toLocaleString() + " वर्णों से अधिक नहीं हो सकता", "error");
    return false;
  }
  return true;
}

function setProgress(job) {
  const pct = Math.min(100, Math.round(job.progress || 0));
  els.progressFill.style.width = pct + "%";
  els.progressPct.textContent = pct + "%";
  els.progressStage.textContent = job.stage || job.status || "";
  let detail = job.message || "";
  if (job.total_chunks) {
    detail += " · Chunk " + (job.current_chunk || 0) + " / " + job.total_chunks;
  }
  els.progressDetail.textContent = detail;
  if (job.eta_seconds != null && job.eta_seconds > 0 && job.status !== "COMPLETED") {
    const s = Math.round(job.eta_seconds);
    const m = Math.floor(s / 60);
    const r = s % 60;
    els.etaText.textContent =
      m > 0
        ? "Estimated time remaining: " + m + " min " + r + " sec"
        : "Estimated time remaining: " + r + " sec";
  } else if (job.status === "PROCESSING" || job.status === "GENERATING_CHUNKS") {
    els.etaText.textContent = "Estimated time remaining: Calculating…";
  } else if (job.status === "COMPLETED") {
    els.etaText.textContent = "Completed";
  } else {
    els.etaText.textContent = "Estimated time: —";
  }
}

function setGenerating(on) {
  els.generateBtn.disabled = on;
  els.previewBtn.disabled = on;
  els.analyzeBtn.disabled = on;
  els.cancelBtn.classList.toggle("hidden", !on);
  els.btnLoader.classList.toggle("hidden", !on);
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const res = await fetch("/api/jobs/" + currentJobId);
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Job not found");
    const job = data.job;
    setProgress(job);
    if (job.status === "COMPLETED") {
      stopPoll();
      setGenerating(false);
      els.audioPlayer.src = job.download_url;
      els.audioSection.classList.remove("hidden");
      els.downloadBtn.onclick = function () {
        const a = document.createElement("a");
        a.href = job.download_url;
        a.download = job.output_filename || "story.mp3";
        a.click();
      };
      showMessage(job.message || "Audio ready!", "success");
      currentJobId = null;
      els.audioSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else if (job.status === "FAILED" || job.status === "CANCELLED") {
      stopPoll();
      setGenerating(false);
      showMessage(job.error || job.message || "Job failed", "error");
      currentJobId = null;
    }
  } catch (e) {
    console.error(e);
    stopPoll();
    setGenerating(false);
    showMessage(e.message || "Status check failed", "error");
    currentJobId = null;
  }
}

async function generateAudio() {
  if (!validate()) return;
  clearMessages();
  els.audioSection.classList.add("hidden");
  setGenerating(true);
  setProgress({ progress: 2, stage: "Preparing Text", message: "Submitting job…", status: "PENDING" });
  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildJobPayload()),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Failed to start job");
    currentJobId = data.job_id;
    showMessage("Generation started…", "info");
    pollTimer = setInterval(pollJob, POLL_INTERVAL);
    pollJob();
  } catch (e) {
    setGenerating(false);
    showMessage(e.message || "Failed to start", "error");
  }
}

async function cancelJob() {
  if (!currentJobId) return;
  try {
    await fetch("/api/jobs/" + currentJobId + "/cancel", { method: "POST" });
    showMessage("Cancel requested…", "info");
  } catch (e) {
    showMessage("Cancel failed", "error");
  }
}

async function previewVoice() {
  clearMessages();
  setGenerating(true);
  try {
    const res = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: "",
        voice_gender: els.voiceGender.value,
        voice_preset: els.voicePreset.value,
        pitch: parseFloat(els.pitchSlider.value) || 0,
        preview: true,
        quality: els.qualitySelect.value,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Preview failed");
    els.audioPlayer.src = data.download_url;
    els.audioSection.classList.remove("hidden");
    els.downloadBtn.onclick = function () {
      const a = document.createElement("a");
      a.href = data.download_url;
      a.download = data.filename;
      a.click();
    };
    showMessage(data.message || "Preview ready", "success");
  } catch (e) {
    showMessage(e.message, "error");
  } finally {
    setGenerating(false);
  }
}

async function analyzeStory() {
  if (!validate()) return;
  clearMessages();
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: els.textInput.value,
        voice_gender: els.voiceGender.value,
        voice_preset: els.voicePreset.value,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Analysis failed");
    els.analysisCard.classList.remove("hidden");
    const e = data.emotion || {};
    const s = data.stats || {};
    const v = data.voice || {};
    els.analysisContent.innerHTML =
      "<p><strong>Emotion:</strong> " +
      (e.detected || "—") +
      " (" +
      (e.confidence || 0) +
      ")</p>" +
      "<p><strong>Voice:</strong> " +
      (v.label || v.preset || "—") +
      " · " +
      (v.provider_voice || "") +
      "</p>" +
      "<p><strong>Words:</strong> " +
      (s.words || 0) +
      " · <strong>Chunks:</strong> ~" +
      (s.estimated_chunks || 0) +
      " · <strong>Duration:</strong> ~" +
      (s.estimated_duration_min || 0) +
      " min</p>";
    if (s.words) els.statWords.textContent = s.words.toLocaleString();
    if (s.estimated_duration_min) els.statDuration.textContent = "~" + s.estimated_duration_min + " min";
    showMessage("Analysis complete", "success");
  } catch (e) {
    showMessage(e.message, "error");
  }
}

els.generateBtn.addEventListener("click", generateAudio);
els.cancelBtn.addEventListener("click", cancelJob);
els.previewBtn.addEventListener("click", previewVoice);
els.analyzeBtn.addEventListener("click", analyzeStory);
els.newBtn.addEventListener("click", function () {
  els.textInput.value = "";
  updateCharCount();
  els.audioSection.classList.add("hidden");
  els.analysisCard.classList.add("hidden");
  clearMessages();
  setProgress({ progress: 0, stage: "Idle", message: "Ready" });
  saveDraft();
});

els.textInput.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") generateAudio();
});

els.textInput.addEventListener("paste", function (e) {
  const pasted = (e.clipboardData || window.clipboardData).getData("text");
  const start = els.textInput.selectionStart;
  const end = els.textInput.selectionEnd;
  const next = els.textInput.value.slice(0, start) + pasted + els.textInput.value.slice(end);
  if (next.length > MAX_CHARS) {
    e.preventDefault();
    showMessage("Paste too large. Max " + MAX_CHARS.toLocaleString() + " characters.", "error");
  }
});

document.addEventListener("DOMContentLoaded", function () {
  els.maxChars.textContent = MAX_CHARS.toLocaleString();
  fillPresets(els.voiceGender.value);
  loadDraft();
  updateCharCount();
  showMessage("Paste a story, select Male or Female voice, and generate.", "info");

  // --- TEXT TO VIDEO STUDIO JS LOGIC ---
  const videoEls = {
    textInput: $("videoTextInput"),
    charCount: $("videoCharCount"),
    syncBtn: $("syncTtsTextBtn"),
    titleInput: $("videoTitleInput"),
    aspectRatio: $("videoAspectRatio"),
    themeSelect: $("videoThemeSelect"),
    voiceGender: $("videoVoiceGender"),
    voicePreset: $("videoVoicePreset"),
    speed: $("videoSpeed"),
    generateBtn: $("generateVideoBtn"),
    btnLoader: $("videoBtnLoader"),
    progressCard: $("videoProgressCard"),
    progressFill: $("videoProgressFill"),
    progressPct: $("videoProgressPct"),
    progressStage: $("videoProgressStage"),
    progressDetail: $("videoProgressDetail"),
    resultSection: $("videoResultSection"),
    videoPlayer: $("videoPlayer"),
    metaInfo: $("videoMetaInfo"),
    downloadBtn: $("downloadVideoBtn"),
  };

  // Nav Item Panel Switcher
  const navItems = document.querySelectorAll(".sidebar-nav .nav-item");
  const audioWorkspace = $("audioWorkspace");
  const videoWorkspace = $("videoWorkspace");

  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      navItems.forEach((n) => n.classList.remove("active"));
      item.classList.add("active");
      const panel = item.dataset.panel;

      if (panel === "video-studio") {
        audioWorkspace.classList.add("hidden");
        videoWorkspace.classList.remove("hidden");
      } else if (panel === "studio") {
        videoWorkspace.classList.add("hidden");
        audioWorkspace.classList.remove("hidden");
      }
    });
  });

  // Video Voice Preset Populate
  function fillVideoPresets(gender) {
    if (!videoEls.voicePreset) return;
    videoEls.voicePreset.innerHTML = "";
    (PRESETS[gender] || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.key;
      opt.textContent = p.label;
      videoEls.voicePreset.appendChild(opt);
    });
  }

  if (videoEls.voiceGender) {
    fillVideoPresets(videoEls.voiceGender.value);
    videoEls.voiceGender.addEventListener("change", (e) => fillVideoPresets(e.target.value));
  }

  // Video text counter & sync
  if (videoEls.textInput) {
    videoEls.textInput.addEventListener("input", () => {
      videoEls.charCount.textContent = videoEls.textInput.value.length.toLocaleString();
    });
  }

  if (videoEls.syncBtn) {
    videoEls.syncBtn.addEventListener("click", () => {
      if (els.textInput && videoEls.textInput) {
        videoEls.textInput.value = els.textInput.value;
        videoEls.charCount.textContent = videoEls.textInput.value.length.toLocaleString();
        showMessage("Text synced from Audio Studio!", "success");
      }
    });
  }

  let videoPollTimer = null;

  function setVideoProgress(pct, stage, detail) {
    if (videoEls.progressFill) videoEls.progressFill.style.width = pct + "%";
    if (videoEls.progressPct) videoEls.progressPct.textContent = pct + "%";
    if (videoEls.progressStage) videoEls.progressStage.textContent = stage;
    if (videoEls.progressDetail) videoEls.progressDetail.textContent = detail;
  }

  async function generateVideo() {
    const text = (videoEls.textInput.value || "").trim();
    if (!text) {
      alert("कृपया वीडियो के लिए कहानी या टेक्स्ट दर्ज करें।");
      return;
    }

    videoEls.generateBtn.disabled = true;
    if (videoEls.btnLoader) videoEls.btnLoader.classList.remove("hidden");
    videoEls.resultSection.classList.add("hidden");
    setVideoProgress(5, "Processing", "Starting Text to Video engine...");

    try {
      const res = await fetch("/api/video/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          title: videoEls.titleInput ? videoEls.titleInput.value : "मेरी हिंदी कहानी",
          aspect_ratio: videoEls.aspectRatio.value,
          theme: videoEls.themeSelect.value,
          voice_gender: videoEls.voiceGender.value,
          voice_preset: videoEls.voicePreset.value,
          speed: videoEls.speed.value,
        }),
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Video request failed");

      const jobId = data.job_id;
      pollVideoJob(jobId);
    } catch (err) {
      videoEls.generateBtn.disabled = false;
      if (videoEls.btnLoader) videoEls.btnLoader.classList.add("hidden");
      setVideoProgress(0, "Failed", err.message);
      alert("Error: " + err.message);
    }
  }

  function pollVideoJob(jobId) {
    if (videoPollTimer) clearInterval(videoPollTimer);
    videoPollTimer = setInterval(async () => {
      try {
        const res = await fetch("/api/video/jobs/" + jobId);
        const data = await res.json();
        if (!data.success) return;

        const job = data.job;
        setVideoProgress(job.progress || 0, job.status, job.stage || "");

        if (job.status === "COMPLETED") {
          clearInterval(videoPollTimer);
          videoEls.generateBtn.disabled = false;
          if (videoEls.btnLoader) videoEls.btnLoader.classList.add("hidden");

          const resData = job.result;
          videoEls.videoPlayer.src = resData.download_url;
          videoEls.resultSection.classList.remove("hidden");

          videoEls.metaInfo.innerHTML =
            `<span class="meta-chip">🎬 Aspect: ${resData.aspect_ratio}</span>` +
            `<span class="meta-chip">🎨 Theme: ${resData.theme}</span>` +
            `<span class="meta-chip">⏱️ Duration: ${resData.duration_seconds}s</span>` +
            `<span class="meta-chip">📁 Size: ${resData.file_size_mb} MB</span>`;

          videoEls.downloadBtn.onclick = () => {
            window.location.href = resData.download_url;
          };

          videoEls.videoPlayer.scrollIntoView({ behavior: "smooth" });
        } else if (job.status === "FAILED") {
          clearInterval(videoPollTimer);
          videoEls.generateBtn.disabled = false;
          if (videoEls.btnLoader) videoEls.btnLoader.classList.add("hidden");
          alert("Video generation failed: " + (job.error || "Unknown error"));
        }
      }, 1500);
  }

  if (videoEls.generateBtn) {
    videoEls.generateBtn.addEventListener("click", generateVideo);
  }
});

