/* Church Live Studio — Control Room logic (Firebase edition) */
const $ = id => document.getElementById(id);
let state = null;

/* ---------------- FireBus (Firebase Realtime Database) ---------------- */
const bus = FireBus.connect('control', msg => {
  if (msg.type === '_connected') $('connDot').classList.toggle('on', msg.connected);
  if (msg.type === 'state') { state = msg.state; renderFromState(); }
  if (msg.type === 'devices') fillCameraSelect(msg.devices);
  if (msg.type === 'presence') {
    const outs = msg.roles.filter(r => r === 'output').length;
    $('presence').textContent = outs ? `● ${outs} output connected` : '○ no output connected';
  }
  if (msg.type === 'rtc-answer' && presenterPC) presenterPC.setRemoteDescription(msg.answer).catch(()=>{});
  if (msg.type === 'rtc-ice' && presenterPC && msg.to === 'control')
    presenterPC.addIceCandidate(msg.candidate).catch(()=>{});
});
const ws = { send: s => bus.send(JSON.parse(s)) };   // keep existing call sites working

function update(patch) { ws.send(JSON.stringify({ type: 'update', patch })); }
function command(name, payload) { ws.send(JSON.stringify({ type: 'command', name, payload })); }

/* ---------------- Reflect server state into UI ---------------- */
let editingGuard = false;
function renderFromState() {
  if (!state) return;
  document.querySelectorAll('.srcBtn').forEach(b =>
    b.classList.toggle('active', b.dataset.src === state.program.source));
  $('programTag').textContent = state.program.source.toUpperCase();

  $('musicTag').textContent = state.music.playing ? '▶ ' + (state.music.file || '') : 'stopped';
  $('musicTag').className = 'tag ' + (state.music.playing ? 'on' : 'off');
  $('ltTag').textContent = state.lowerThird.visible ? 'LIVE' : 'hidden';
  $('ltTag').className = 'tag ' + (state.lowerThird.visible ? 'on' : 'off');
  $('tickerTag').textContent = state.ticker.visible ? 'LIVE' : 'hidden';
  $('tickerTag').className = 'tag ' + (state.ticker.visible ? 'on' : 'off');
  $('capTag').textContent = state.captions.visible ? 'LIVE' : 'off';
  $('capTag').className = 'tag ' + (state.captions.visible ? 'on' : 'off');

  if (!editingGuard) {
    $('tickerText').value = state.ticker.text || '';
    $('ltTitle').value = state.lowerThird.title || '';
    $('ltSub').value = state.lowerThird.subtitle || '';
    $('brandName').value = state.branding.churchName || '';
    $('brandTag').value = state.branding.tagline || '';
    $('brandLogo').value = state.branding.logoText || '';
    editingGuard = true;   // only prefill once so typing isn't clobbered
  }
  $('chkMute').checked = !!state.overlay.muteProgram;
  $('chkClock').checked = !!state.overlay.clock;
  $('chkLoop').checked = !!state.music.loop;
}

/* ---------------- Program switcher ---------------- */
document.querySelectorAll('.srcBtn').forEach(b => b.onclick = () => {
  update({ program: { source: b.dataset.src } });
});
$('btnBlack').onclick = () => update({ program: { source: 'black' } });
$('btnLogo').onclick = () => update({ program: { source: 'logo' } });
$('btnVideoRestart').onclick = () => command('video-restart');
$('chkMute').onchange = e => update({ overlay: { muteProgram: e.target.checked } });
$('chkClock').onchange = e => update({ overlay: { clock: e.target.checked } });

function fillCameraSelect(devices) {
  const sel = $('cameraSelect');
  sel.innerHTML = '<option value="">— default camera on output machine —</option>' +
    devices.map(d => `<option value="${d.deviceId}">${d.label}</option>`).join('');
}
$('cameraSelect').onchange = e =>
  update({ program: { cameraDeviceId: e.target.value || null, source: 'camera' } });
$('btnRefreshCams').onclick = () => command('reload');

/* ---------------- Presenter camera (WebRTC out) ---------------- */
let presenterPC = null, presenterStream = null;
$('btnStartPresenter').onclick = async () => {
  try {
    presenterStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
    presenterPC = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    presenterStream.getTracks().forEach(t => presenterPC.addTrack(t, presenterStream));
    presenterPC.onicecandidate = ev => {
      if (ev.candidate) ws.send(JSON.stringify({ type: 'rtc-ice', to: 'output', candidate: ev.candidate }));
    };
    const offer = await presenterPC.createOffer();
    await presenterPC.setLocalDescription(offer);
    ws.send(JSON.stringify({ type: 'rtc-offer', offer }));
    update({ program: { source: 'remoteCamera' } });
  } catch (e) { alert('Could not access camera: ' + e.message); }
};
$('btnStopPresenter').onclick = () => {
  if (presenterStream) presenterStream.getTracks().forEach(t => t.stop());
  if (presenterPC) presenterPC.close();
  presenterPC = presenterStream = null;
  ws.send(JSON.stringify({ type: 'rtc-stop' }));
};

/* ---------------- Media library (links) ---------------- */
async function loadMedia() {
  const files = await FireBus.listMedia();
  const icons = { audio: '🎧', video: '🎞️', image: '🖼️', other: '📄' };
  $('mediaList').innerHTML = files.map(f => `
    <li><span>${icons[f.kind] || '📄'}</span><span class="name" title="${f.url}">${f.name}</span>
      <span class="kind">${f.kind}</span>
      <button class="sm" data-act="use" data-kind="${f.kind}" data-url="${f.url}" data-name="${f.name}">▶</button>
      ${f.id ? `<button class="sm" data-act="del" data-id="${f.id}" data-name="${f.name}">✕</button>` : ''}</li>`).join('') ||
    '<li><span class="hint">No media yet — add a link below.</span></li>';

  const audio = files.filter(f => f.kind === 'audio');
  $('musicSelect').innerHTML = '<option value="">— choose a track —</option>' +
    audio.map(f => `<option value="${f.url}">${f.name}</option>`).join('');
  if (state && state.music.file) $('musicSelect').value = state.music.file;
}
loadMedia();

$('mediaList').onclick = async e => {
  const btn = e.target.closest('button'); if (!btn) return;
  const { act, kind, url, id, name } = btn.dataset;
  if (act === 'del') {
    if (!confirm('Delete ' + name + '?')) return;
    await FireBus.deleteMedia(id);
    loadMedia();
  } else if (act === 'use') {
    if (kind === 'video') update({ program: { source: 'video', videoFile: url } });
    else if (kind === 'image') update({ program: { source: 'image', imageFile: url } });
    else if (kind === 'audio') { $('musicSelect').value = url; update({ music: { file: url, playing: true } }); }
  }
};

const EXT_KIND = { mp3:'audio', wav:'audio', ogg:'audio', m4a:'audio', aac:'audio', flac:'audio',
  mp4:'video', webm:'video', mov:'video', m4v:'video', mkv:'video',
  jpg:'image', jpeg:'image', png:'image', gif:'image', webp:'image', svg:'image' };

$('btnAddMedia').onclick = async () => {
  const url = $('mediaUrl').value.trim();
  if (!url) return alert('Paste a direct link to an audio/video/image file first.');
  const name = $('mediaName').value.trim() || decodeURIComponent(url.split('/').pop().split('?')[0]) || 'media';
  const ext = (url.split('?')[0].split('.').pop() || '').toLowerCase();
  const kind = $('mediaKind').value === 'auto' ? (EXT_KIND[ext] || 'audio') : $('mediaKind').value;
  await FireBus.addMedia({ name, url, kind });
  $('mediaUrl').value = ''; $('mediaName').value = '';
  loadMedia();
};

/* ---------------- Music ---------------- */
$('btnMusicPlay').onclick = () => {
  const f = $('musicSelect').value;
  if (!f) return alert('Choose a track first.');
  update({ music: { file: f, playing: true, volume: parseFloat($('musicVol').value) } });
};
$('btnMusicPause').onclick = () => update({ music: { playing: false } });
$('btnMusicRestart').onclick = () => command('music-restart');
$('chkLoop').onchange = e => update({ music: { loop: e.target.checked } });
$('musicVol').oninput = e => update({ music: { volume: parseFloat(e.target.value) } });
$('btnFadeOut').onclick = () => {
  let v = parseFloat($('musicVol').value);
  const iv = setInterval(() => {
    v = Math.max(0, v - 0.06);
    $('musicVol').value = v;
    update({ music: { volume: v } });
    if (v <= 0) { clearInterval(iv); update({ music: { playing: false } }); }
  }, 180);
};

/* ---------------- Songs / lyrics ---------------- */
let songs = [], currentSong = null;
async function loadSongs() {
  songs = await FireBus.listSongs();
  $('songList').innerHTML = songs.map(s =>
    `<li data-id="${s.id}" class="${currentSong && currentSong.id === s.id ? 'selected' : ''}">
       <span>🎵</span><span class="name">${s.title}</span></li>`).join('') ||
    '<li><span class="hint">No songs saved yet.</span></li>';
}
loadSongs();

$('songList').onclick = e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  currentSong = songs.find(s => s.id === li.dataset.id);
  $('songTitle').value = currentSong.title;
  $('songText').value = currentSong.text;
  renderBlocks();
  loadSongs();
};
$('btnNewSong').onclick = () => {
  currentSong = null; $('songTitle').value = ''; $('songText').value = ''; renderBlocks(); loadSongs();
};
$('btnSaveSong').onclick = async () => {
  const song = { id: currentSong?.id, title: $('songTitle').value.trim() || 'Untitled', text: $('songText').value };
  currentSong = await FireBus.saveSong(song);
  loadSongs();
};
$('btnDeleteSong').onclick = async () => {
  if (!currentSong) return;
  if (!confirm('Delete "' + currentSong.title + '"?')) return;
  await FireBus.deleteSong(currentSong.id);
  currentSong = null; $('songTitle').value = ''; $('songText').value = '';
  renderBlocks(); loadSongs();
};
$('songText').oninput = renderBlocks;

function getBlocks() {
  return $('songText').value.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);
}
let blockIndex = -1;
function renderBlocks() {
  const blocks = getBlocks();
  $('blockButtons').innerHTML = blocks.map((b, i) =>
    `<button class="blockBtn ${i === blockIndex ? 'active' : ''}" data-i="${i}">${b.split('\n').slice(0, 2).join('\n')}${b.split('\n').length > 2 ? '…' : ''}</button>`).join('');
}
$('blockButtons').onclick = e => {
  const btn = e.target.closest('.blockBtn'); if (!btn) return;
  projectBlock(parseInt(btn.dataset.i, 10));
};
function projectBlock(i) {
  const blocks = getBlocks();
  if (i < 0 || i >= blocks.length) return;
  blockIndex = i;
  update({
    program: { source: 'lyrics' },
    lyrics: { songTitle: $('songTitle').value, lines: blocks[i].split('\n'), blockIndex: i,
              theme: $('chkLightTheme').checked ? 'light' : 'dark' }
  });
  renderBlocks();
}
$('btnPrevBlock').onclick = () => projectBlock(blockIndex - 1);
$('btnNextBlock').onclick = () => projectBlock(blockIndex + 1);
$('chkLightTheme').onchange = e => update({ lyrics: { theme: e.target.checked ? 'light' : 'dark' } });
document.addEventListener('keydown', e => {
  if (e.target.matches('input,textarea,select')) return;
  if (e.key === 'ArrowRight' || e.key === 'PageDown') projectBlock(blockIndex + 1);
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') projectBlock(blockIndex - 1);
});

/* ---------------- Scripture ---------------- */
$('btnShowScripture').onclick = () => update({
  program: { source: 'scripture' },
  scripture: { reference: $('scRef').value, text: $('scText').value, version: $('scVer').value }
});

/* ---------------- Lower third ---------------- */
$('btnLtShow').onclick = () => update({ lowerThird: {
  visible: true, title: $('ltTitle').value, subtitle: $('ltSub').value, style: $('ltStyle').value } });
$('btnLtHide').onclick = () => update({ lowerThird: { visible: false } });

/* ---------------- Ticker ---------------- */
function tickerPatch(visible) {
  return { ticker: { visible, text: $('tickerText').value,
    speed: parseInt($('tickerSpeed').value, 10),
    bg: $('tickerBg').value, color: $('tickerColor').value } };
}
$('btnTickerShow').onclick = () => update(tickerPatch(true));
$('btnTickerHide').onclick = () => update({ ticker: { visible: false } });
$('btnTickerApply').onclick = () => update(tickerPatch(state ? state.ticker.visible : false));
$('tickerSpeed').oninput = e => update({ ticker: { speed: parseInt(e.target.value, 10) } });

/* ---------------- Live captions & translation ---------------- */
let recog = null, capRunning = false, translateTimer = null, lastFinal = '';
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

$('btnCapStart').onclick = () => {
  if (!SR) return alert('Speech recognition is not supported in this browser. Use Chrome or Edge.');
  if (capRunning) return;
  capRunning = true;
  update({ captions: { visible: true,
    showOriginal: $('chkCapOrig').checked, showTranslated: $('chkCapTrans').checked,
    sourceLang: $('srcLang').value, targetLang: $('tgtLang').value } });
  startRecognition();
};
$('btnCapStop').onclick = () => {
  capRunning = false;
  if (recog) recog.stop();
  update({ captions: { visible: false } });
  ws.send(JSON.stringify({ type: 'caption', original: '', translated: '' }));
  $('capPreview').innerHTML = '<span class="hint">Captions preview…</span>';
};
$('chkCapOrig').onchange = e => update({ captions: { showOriginal: e.target.checked } });
$('chkCapTrans').onchange = e => update({ captions: { showTranslated: e.target.checked } });

function startRecognition() {
  recog = new SR();
  recog.lang = $('srcLang').value;
  recog.continuous = true;
  recog.interimResults = true;

  recog.onresult = ev => {
    let interim = '', final = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const r = ev.results[i];
      if (r.isFinal) final += r[0].transcript;
      else interim += r[0].transcript;
    }
    const text = (final || interim).trim();
    if (!text) return;
    sendCaption(text, null);
    if (final.trim()) { lastFinal = final.trim(); translateNow(lastFinal); }
    else {
      clearTimeout(translateTimer);
      translateTimer = setTimeout(() => translateNow(text), 700);
    }
  };
  recog.onend = () => { if (capRunning) try { recog.start(); } catch {} };
  recog.onerror = e => { if (e.error === 'not-allowed') { capRunning = false; alert('Microphone access denied.'); } };
  try { recog.start(); } catch {}
}

async function translateNow(text) {
  if (!$('chkCapTrans').checked) return;
  const out = await fireTranslate(text, $('srcLang').value.split('-')[0], $('tgtLang').value);
  if (out) sendCaption(text, out);
}

function sendCaption(original, translated) {
  const msg = { type: 'caption', original };
  if (translated !== null) msg.translated = translated;
  ws.send(JSON.stringify(msg));
  $('capPreview').innerHTML = escapeHtml(original) +
    (translated ? '<br><span class="tr">' + escapeHtml(translated) + '</span>' : '');
}

/* ---------------- Branding & stage ---------------- */
$('btnBrandApply').onclick = () => update({ branding: {
  churchName: $('brandName').value, tagline: $('brandTag').value,
  logoText: $('brandLogo').value || '✝', accent: $('brandAccent').value } });
$('btnStageSend').onclick = () => update({ stageMessage: $('stageMsg').value });
$('btnStageClear').onclick = () => { $('stageMsg').value = ''; update({ stageMessage: '' }); };

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
