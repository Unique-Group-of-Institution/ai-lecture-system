(() => {
  "use strict";
  const node = document.getElementById("recording-data");
  if (!node) return;
  let data = JSON.parse(node.textContent);
  const warning = document.getElementById("browser-warning");
  const globalMessage = document.getElementById("global-message");
  const pending = new Map();
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  let active = null;

  function message(element, text, danger = false) {
    element.textContent = text;
    element.hidden = !text;
    element.classList.toggle("danger", danger);
  }
  function stale(text) {
    message(globalMessage, `${text} Reload this page to review the current approved slide.`, true);
    document.querySelectorAll("button").forEach((button) => { if (!button.closest("form")) button.disabled = true; });
  }
  async function jsonFetch(url, body) {
    const response = await fetch(url, {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json","X-CSRFToken":csrf}, body:JSON.stringify(body)});
    const payload = await response.json().catch(() => ({error:"The local server returned an invalid response."}));
    if (!response.ok) { const error = new Error(payload.error || "The request could not be completed."); error.status = response.status; throw error; }
    return payload;
  }
  function mimeChoice() {
    const choices = [
      ["audio/webm;codecs=opus","webm"], ["audio/ogg;codecs=opus","ogg"],
      ["audio/mp4","m4a"], ["audio/webm","webm"]
    ];
    return choices.find(([mime]) => MediaRecorder.isTypeSupported(mime)) || null;
  }
  const supported = window.isSecureContext && navigator.mediaDevices?.getUserMedia && window.MediaRecorder && mimeChoice();
  if (!supported && data.can_record) {
    warning.hidden = false;
    warning.textContent = window.isSecureContext ? "This browser cannot record supported audio. Use a current version of Edge, Chrome, Firefox, or Safari." : "Microphone recording requires a secure local context (HTTPS or localhost).";
    document.querySelectorAll("[data-record]").forEach((button) => button.disabled = true);
  }
  function duration(ms) { const total = Math.floor(ms / 1000); return `${String(Math.floor(total/60)).padStart(2,"0")}:${String(total%60).padStart(2,"0")}`; }
  function cardFor(slideId) { return document.querySelector(`[data-slide-id="${slideId}"]`); }
  async function upload(slide, card, item) {
    const form = new FormData();
    form.append("expected_revision_id", String(slide.approved_revision_id));
    form.append("duration_ms", String(item.durationMs));
    form.append("audio", item.blob, `slide-${slide.position}-take.${item.extension}`);
    const status = card.querySelector("[data-message]");
    const retry = card.querySelector("[data-retry]");
    status.textContent = "Uploading to local storage…";
    retry.hidden = true;
    try {
      const response = await fetch(`/api/recordings/${data.id}/slides/${slide.id}/takes/`, {method:"POST", credentials:"same-origin", headers:{"X-CSRFToken":csrf}, body:form});
      const payload = await response.json().catch(() => ({error:"The local server returned an invalid response."}));
      if (!response.ok) { const error = new Error(payload.error || "Upload failed."); error.status = response.status; throw error; }
      pending.delete(slide.id);
      status.textContent = `Take ${payload.take_number} saved locally and selected.`;
      const empty = card.querySelector("[data-empty]"); if (empty) empty.remove();
      card.querySelectorAll("[data-select]").forEach((button) => { button.disabled = false; button.textContent = "Use this take"; });
      const row = document.createElement("div"); row.className = "take-row"; row.dataset.takeId = payload.id;
      const info = document.createElement("div"); const strong = document.createElement("strong"); strong.textContent = `Take ${payload.take_number}`; const detail = document.createElement("span"); detail.textContent = `${payload.duration_ms} ms · ${payload.media_type}`; info.append(strong,detail);
      const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none"; audio.src = payload.media_url;
      const select = document.createElement("button"); select.type = "button"; select.className = "select-take secondary"; select.dataset.select = payload.id; select.disabled = true; select.textContent = "Selected";
      row.append(info,audio,select); card.querySelector("[data-takes]").append(row);
      card.querySelector("[data-status]").textContent = "Take selected"; card.querySelector("[data-status]").classList.add("ready");
    } catch (error) {
      if (error.status === 409) return stale(error.message);
      status.textContent = `${error.message} The captured take remains in this browser tab; retry the local upload.`;
      retry.hidden = false;
    }
  }
  async function start(slide, card) {
    if (active) return;
    const status = card.querySelector("[data-message]");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
      const [mime, extension] = mimeChoice();
      const chunks = []; const recorder = new MediaRecorder(stream,{mimeType:mime}); const started = Date.now();
      const record = card.querySelector("[data-record]"); const stop = card.querySelector("[data-stop]"); const timer = card.querySelector("[data-timer]");
      record.disabled = true; record.classList.add("recording"); record.textContent = "Recording…"; stop.disabled = false; status.textContent = "Speak the approved narration. Your raw take is not uploaded until you stop.";
      const interval = window.setInterval(() => { timer.textContent = duration(Date.now()-started); },250);
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => { status.textContent = "Recording was interrupted. No partial take was accepted by the server."; };
      recorder.onstop = async () => {
        window.clearInterval(interval); stream.getTracks().forEach((track) => track.stop()); active = null; record.disabled = false; record.classList.remove("recording"); record.textContent = "Record retake"; stop.disabled = true;
        const durationMs = Date.now()-started; const blob = new Blob(chunks,{type:mime});
        if (!blob.size) { status.textContent = "Recording was interrupted before audio was captured."; return; }
        const item = {blob,durationMs,extension}; pending.set(slide.id,item); await upload(slide,card,item);
      };
      recorder.start(1000); active = {recorder,card};
    } catch (error) {
      if (error.name === "NotAllowedError" || error.name === "SecurityError") status.textContent = "Microphone permission was denied. Allow microphone access for this local site and try again.";
      else if (error.name === "NotFoundError") status.textContent = "No microphone was found. Connect one and try again.";
      else status.textContent = "The microphone could not start. Check the browser and device, then try again.";
    }
  }
  document.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-slide-id]");
    if (event.target.matches("[data-record]") && card) { const slide = data.slides.find((item) => item.id === Number(card.dataset.slideId)); await start(slide,card); }
    if (event.target.matches("[data-stop]") && active?.card === card && active.recorder.state === "recording") active.recorder.stop();
    if (event.target.matches("[data-retry]") && card) { const slide = data.slides.find((item) => item.id === Number(card.dataset.slideId)); const item = pending.get(slide.id); if (item) await upload(slide,card,item); }
    if (event.target.matches("[data-select]") && card) {
      const slide = data.slides.find((item) => item.id === Number(card.dataset.slideId));
      try { await jsonFetch(`/api/recordings/${data.id}/slides/${slide.id}/select/`,{take_id:Number(event.target.dataset.select),expected_revision_id:slide.approved_revision_id}); card.querySelectorAll("[data-select]").forEach((button) => { button.disabled=false; button.textContent="Use this take"; }); event.target.disabled=true; event.target.textContent="Selected"; card.querySelector("[data-status]").textContent="Take selected"; card.querySelector("[data-status]").classList.add("ready"); }
      catch(error) { if(error.status===409) stale(error.message); else card.querySelector("[data-message]").textContent=error.message; }
    }
  });
  document.getElementById("open-recording")?.addEventListener("click", async () => { try { await jsonFetch(`/api/recordings/${data.id}/open/`,{expected_version:data.version}); window.location.reload(); } catch(error) { if(error.status===409) stale(error.message); else message(globalMessage,error.message,true); } });
  document.getElementById("complete-recording")?.addEventListener("click", async () => { if(active) return message(globalMessage,"Stop the active recording before completing.",true); try { await jsonFetch(`/api/recordings/${data.id}/complete/`,{expected_version:data.version,expected_revision_ids:data.slides.map((slide)=>slide.approved_revision_id)}); window.location.reload(); } catch(error) { if(error.status===409) stale(error.message); else message(globalMessage,error.message,true); } });
})();
