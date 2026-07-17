/*
 * Church Live Studio — server
 * - Serves the control room, program output and stage display
 * - Holds the live production state and syncs it over WebSockets
 * - Relays WebRTC signaling (presenter camera -> program output)
 * - Media library (list/upload) and song library (persisted to data/songs.json)
 * - Translation proxy for live caption translation
 */
const express = require('express');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 3000;
const MEDIA_DIR = path.join(__dirname, 'media');
const DATA_DIR = path.join(__dirname, 'data');
const SONGS_FILE = path.join(DATA_DIR, 'songs.json');

fs.mkdirSync(MEDIA_DIR, { recursive: true });
fs.mkdirSync(DATA_DIR, { recursive: true });

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));
app.use('/media', express.static(MEDIA_DIR));

/* ------------------------------------------------------------------ */
/* Live production state (single source of truth)                      */
/* ------------------------------------------------------------------ */
let state = {
  program: {
    source: 'logo',            // logo | camera | remoteCamera | video | image | lyrics | scripture | black
    cameraDeviceId: null,
    videoFile: null,
    imageFile: null,
    transition: 'fade'
  },
  branding: {
    churchName: 'Grace Community Church',
    tagline: 'Welcome — we are glad you are here',
    logoText: '✝',
    accent: '#c9a227'
  },
  ticker: {
    visible: false,
    text: 'Welcome to our live service • Sunday service 9:00 AM • Prayer meeting Wednesday 6:00 PM',
    speed: 60,                 // px per second
    bg: '#111827',
    color: '#f9fafb'
  },
  lowerThird: {
    visible: false,
    title: '',
    subtitle: '',
    style: 'gold'              // gold | blue | red | clean
  },
  lyrics: {
    songId: null,
    songTitle: '',
    lines: [],                 // current block of lines being shown
    blockIndex: -1,
    theme: 'dark'
  },
  scripture: {
    reference: '',
    text: '',
    version: ''
  },
  captions: {
    visible: false,
    original: '',
    translated: '',
    showOriginal: true,
    showTranslated: true,
    sourceLang: 'en-US',
    targetLang: 'es'
  },
  music: {
    file: null,
    playing: false,
    volume: 0.8,
    loop: false
  },
  overlay: {
    clock: false,
    muteProgram: false
  },
  stageMessage: ''
};

/* Deep-merge a patch into state */
function merge(target, patch) {
  for (const key of Object.keys(patch)) {
    const val = patch[key];
    if (val && typeof val === 'object' && !Array.isArray(val) &&
        target[key] && typeof target[key] === 'object' && !Array.isArray(target[key])) {
      merge(target[key], val);
    } else {
      target[key] = val;
    }
  }
}

/* ------------------------------------------------------------------ */
/* WebSocket hub                                                       */
/* ------------------------------------------------------------------ */
const clients = new Set();

function broadcast(msg, except) {
  const data = JSON.stringify(msg);
  for (const ws of clients) {
    if (ws !== except && ws.readyState === 1) ws.send(data);
  }
}

wss.on('connection', (ws) => {
  clients.add(ws);
  ws.role = 'unknown';
  ws.send(JSON.stringify({ type: 'state', state }));

  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    switch (msg.type) {
      case 'hello':
        ws.role = msg.role || 'unknown';
        broadcast({ type: 'presence', roles: [...clients].map(c => c.role) });
        break;

      case 'update':                      // patch the shared state
        merge(state, msg.patch || {});
        broadcast({ type: 'state', state });
        break;

      case 'command':                     // transient commands (seek, flash, etc.)
        broadcast({ type: 'command', name: msg.name, payload: msg.payload }, ws);
        break;

      case 'caption':                     // live caption text (high frequency)
        state.captions.original = msg.original ?? state.captions.original;
        state.captions.translated = msg.translated ?? state.captions.translated;
        broadcast({ type: 'caption', original: state.captions.original, translated: state.captions.translated }, ws);
        break;

      case 'devices':                     // output reports its camera list
        broadcast({ type: 'devices', devices: msg.devices }, ws);
        break;

      /* WebRTC signaling relay: presenter camera (control) -> output */
      case 'rtc-offer':
      case 'rtc-answer':
      case 'rtc-ice':
      case 'rtc-stop':
        broadcast(msg, ws);
        break;
    }
  });

  ws.on('close', () => {
    clients.delete(ws);
    broadcast({ type: 'presence', roles: [...clients].map(c => c.role) });
  });
});

/* ------------------------------------------------------------------ */
/* Media library                                                       */
/* ------------------------------------------------------------------ */
const AUDIO_EXT = ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'];
const VIDEO_EXT = ['.mp4', '.webm', '.mov', '.mkv', '.m4v'];
const IMAGE_EXT = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'];

app.get('/api/media', (req, res) => {
  const files = fs.readdirSync(MEDIA_DIR).filter(f => !f.startsWith('.'));
  const typed = files.map(f => {
    const ext = path.extname(f).toLowerCase();
    let kind = 'other';
    if (AUDIO_EXT.includes(ext)) kind = 'audio';
    else if (VIDEO_EXT.includes(ext)) kind = 'video';
    else if (IMAGE_EXT.includes(ext)) kind = 'image';
    return { name: f, kind, url: '/media/' + encodeURIComponent(f) };
  });
  res.json(typed);
});

/* Simple raw-body upload:  PUT /api/upload?name=song.mp3  */
app.put('/api/upload', express.raw({ type: '*/*', limit: '500mb' }), (req, res) => {
  const name = path.basename(String(req.query.name || ''));
  if (!name) return res.status(400).json({ error: 'name query parameter required' });
  fs.writeFileSync(path.join(MEDIA_DIR, name), req.body);
  res.json({ ok: true, name });
});

app.delete('/api/media/:name', (req, res) => {
  const file = path.join(MEDIA_DIR, path.basename(req.params.name));
  if (fs.existsSync(file)) fs.unlinkSync(file);
  res.json({ ok: true });
});

/* ------------------------------------------------------------------ */
/* Song library (lyrics)                                               */
/* ------------------------------------------------------------------ */
function loadSongs() {
  try { return JSON.parse(fs.readFileSync(SONGS_FILE, 'utf8')); } catch { return []; }
}
function saveSongs(songs) {
  fs.writeFileSync(SONGS_FILE, JSON.stringify(songs, null, 2));
}

app.get('/api/songs', (req, res) => res.json(loadSongs()));

app.post('/api/songs', (req, res) => {
  const songs = loadSongs();
  const song = req.body;
  if (!song || !song.title) return res.status(400).json({ error: 'title required' });
  if (song.id) {
    const i = songs.findIndex(s => s.id === song.id);
    if (i >= 0) songs[i] = song; else songs.push(song);
  } else {
    song.id = Date.now().toString(36);
    songs.push(song);
  }
  saveSongs(songs);
  res.json(song);
});

app.delete('/api/songs/:id', (req, res) => {
  saveSongs(loadSongs().filter(s => s.id !== req.params.id));
  res.json({ ok: true });
});

/* ------------------------------------------------------------------ */
/* Translation proxy (for live caption translation)                    */
/* Uses the public Google Translate web endpoint — no API key needed.  */
/* ------------------------------------------------------------------ */
app.get('/api/translate', async (req, res) => {
  const { q, target, source } = req.query;
  if (!q || !target) return res.status(400).json({ error: 'q and target required' });
  try {
    const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=' +
      encodeURIComponent(source || 'auto') + '&tl=' + encodeURIComponent(target) +
      '&dt=t&q=' + encodeURIComponent(q);
    const r = await fetch(url);
    const j = await r.json();
    const text = (j[0] || []).map(part => part[0]).join('');
    res.json({ text });
  } catch (e) {
    res.status(502).json({ error: 'translation unavailable', detail: String(e) });
  }
});

server.listen(PORT, () => {
  console.log('');
  console.log('  ✝  Church Live Studio is running');
  console.log('  ──────────────────────────────────────────────');
  console.log(`  Control room:   http://localhost:${PORT}/control.html`);
  console.log(`  Program output: http://localhost:${PORT}/output.html   (add as OBS browser source, 1920x1080)`);
  console.log(`  Stage display:  http://localhost:${PORT}/stage.html`);
  console.log(`  Home / guide:   http://localhost:${PORT}/`);
  console.log('');
});
