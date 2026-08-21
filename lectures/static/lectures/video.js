(() => {
  const body = document.body;
  const workflowId = body.dataset.workflowId;
  const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
  const status = document.querySelector('#status-message');
  const send = async (url, payload = {}) => {
    const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The local video operation failed safely.');
    return result;
  };
  const run = async (operation) => { try { status.innerHTML = '<strong>Working locally…</strong><p>Please wait.</p>'; await operation(); location.reload(); } catch (error) { status.innerHTML = `<strong>Operation stopped safely</strong><p>${String(error.message).replace(/[<>&]/g, '')}</p>`; } };
  document.querySelector('#request-render')?.addEventListener('click', () => run(() => send(`/api/video/workflows/${workflowId}/renders/`)));
  document.querySelectorAll('.submit-review').forEach((button) => button.addEventListener('click', () => run(() => send(`/api/video/workflows/${workflowId}/renders/${button.dataset.renderId}/submit-review/`))));
  document.querySelectorAll('.admin-final').forEach((button) => button.addEventListener('click', () => run(() => send(`/api/video/workflows/${workflowId}/renders/${button.dataset.renderId}/admin-final/`))));
  document.querySelectorAll('.request-export').forEach((button) => button.addEventListener('click', () => run(() => send(`/api/video/workflows/${workflowId}/renders/${button.dataset.renderId}/export/`))));
  document.querySelectorAll('.approve-spoken').forEach((button) => button.addEventListener('click', () => run(() => send(`/api/video/edits/${button.dataset.decisionId}/teacher-approve/`))));
  document.querySelectorAll('.teacher-review').forEach((form) => form.addEventListener('click', (event) => { const button = event.target.closest('button[name=decision]'); if (!button) return; event.preventDefault(); run(() => send(`/api/video/workflows/${workflowId}/renders/${form.dataset.renderId}/teacher-review/`, {decision: button.value, notes: form.querySelector('textarea').value})); }));
  const type = document.querySelector('#decision-type');
  const fields = document.querySelector('#edit-fields');
  const renderFields = () => {
    if (!type || !fields) return;
    const controls = {
      BRANDING: '<div><label>Accent color<input name="accent_color" value="#0057B8" pattern="#[0-9A-Fa-f]{6}" required></label></div><div><label>Institution name<input name="institution_name" maxlength="120" value="Unique Group of Institutions" required></label></div>',
      CAPTION_LAYOUT: '<div><label>Caption position<select name="position"><option value="bottom">Bottom</option><option value="top">Top</option></select></label></div><div><label>Font scale %<input name="font_scale" type="number" min="80" max="130" value="100" required></label></div>',
      TRANSITION_TIMING: '<div><label>Transition ms<input name="transition_ms" type="number" min="0" max="1000" value="300" required></label></div><div><label>Hold after slide ms<input name="hold_after_ms" type="number" min="0" max="5000" value="0" required></label></div>',
      SPOKEN_CONTENT_REMOVAL: '<div><label>Slide position<input name="slide_position" type="number" min="1" max="100" required></label></div><div><label>Start ms<input name="start_ms" type="number" min="0" required></label></div><div><label>End ms<input name="end_ms" type="number" min="1" required></label></div><div><label>Canonical narration SHA-256<input name="narration_sha256" pattern="[0-9a-f]{64}" required></label></div><div><label>Exact transcript excerpt<textarea name="transcript_excerpt" maxlength="500" required></textarea></label></div><div><label>Reason<textarea name="reason" maxlength="300" required></textarea></label></div>'
    };
    fields.innerHTML = controls[type.value];
  };
  type?.addEventListener('change', renderFields); renderFields();
  document.querySelector('#edit-form')?.addEventListener('submit', (event) => { event.preventDefault(); const form = event.currentTarget; const data = Object.fromEntries(new FormData(form)); for (const key of ['font_scale','transition_ms','hold_after_ms','slide_position','start_ms','end_ms']) if (key in data) data[key] = Number(data[key]); run(() => send(`/api/video/workflows/${workflowId}/edits/`, {base_render_id: Number(document.querySelector('#base-render').value), decision_type: type.value, payload: data})); });
})();
