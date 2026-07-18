/*
 * FireBus — drop-in replacement for the local WebSocket hub, powered by
 * Cloud Firestore realtime listeners. Exposes the same message protocol
 * the pages already speak: hello / update / command / caption / devices / rtc-*.
 */
/* global firebase */

const firebaseConfig = {
  apiKey: 'AIzaSyBMCsGZPcC13iaadwG6yQmZOKYs1kGRLaQ',
  authDomain: 'church-live-studio-png.firebaseapp.com',
  projectId: 'church-live-studio-png',
  storageBucket: 'church-live-studio-png.firebasestorage.app',
  messagingSenderId: '1063152167128',
  appId: '1:1063152167128:web:75398c042dc87d68b40fad'
};
firebase.initializeApp(firebaseConfig);
const fdb = firebase.firestore();
/* networks that break streaming (some proxies/firewalls) can force long-polling
   by setting window.__forceLongPoll = true before this script loads */
if (self.__forceLongPoll) fdb.settings({ experimentalForceLongPolling: true, experimentalAutoDetectLongPolling: false, merge: true });
const STS = () => firebase.firestore.FieldValue.serverTimestamp();
const appDoc = name => fdb.collection('app').doc(name);

const DEFAULT_STATE = {
  program: { source: 'logo', cameraDeviceId: null, videoFile: null, imageFile: null, transition: 'fade' },
  branding: { churchName: 'Grace Community Church', tagline: 'Welcome — we are glad you are here',
    logoText: '✝', accent: '#c9a227' },
  ticker: { visible: false,
    text: 'Welcome to our live service • Sunday service 9:00 AM • Prayer meeting Wednesday 6:00 PM',
    speed: 60, bg: '#111827', color: '#f9fafb' },
  lowerThird: { visible: false, title: '', subtitle: '', style: 'gold' },
  lyrics: { songId: null, songTitle: '', lines: [], blockIndex: -1, theme: 'dark' },
  scripture: { reference: '', text: '', version: '' },
  captions: { visible: false, original: '', translated: '', showOriginal: true, showTranslated: true,
    sourceLang: 'en-US', targetLang: 'es' },
  music: { file: null, playing: false, volume: 0.8, loop: false },
  overlay: { clock: false, muteProgram: false },
  stageMessage: ''
};

function clone(o) { return JSON.parse(JSON.stringify(o)); }

/* Fill in any keys the stored copy is missing, from defaults */
function withDefaults(def, val) {
  if (val === null || val === undefined) return clone(def);
  if (def && typeof def === 'object' && !Array.isArray(def)) {
    const out = {};
    for (const k of Object.keys(def)) out[k] = withDefaults(def[k], val[k]);
    for (const k of Object.keys(val)) if (!(k in out)) out[k] = val[k];
    return out;
  }
  return val;
}

const FireBus = {
  connect(role, onMessage) {
    const joinedAt = Date.now();
    const fresh = ts => ts && ts.toMillis && ts.toMillis() > joinedAt - 2000;
    let announcedConn = false;

    /* presence via heartbeats (Firestore has no onDisconnect) */
    const myRef = fdb.collection('presence').doc(role + '-' + Math.random().toString(36).slice(2, 9));
    const beat = () => myRef.set({ role, ts: STS() }).catch(() => {});
    beat();
    setInterval(beat, 25000);
    addEventListener('pagehide', () => { myRef.delete().catch(() => {}); });
    fdb.collection('presence').onSnapshot(s => {
      const now = Date.now();
      const roles = s.docs.map(d => d.data())
        .filter(p => p.ts && now - p.ts.toMillis() < 80000).map(p => p.role);
      onMessage({ type: 'presence', roles });
    }, () => {});

    /* control seeds the state on first ever run */
    if (role === 'control') {
      appDoc('state').get().then(s => { if (!s.exists) appDoc('state').set(clone(DEFAULT_STATE)); })
        .catch(() => {});
    }

    /* shared production state */
    appDoc('state').onSnapshot(s => {
      if (!announcedConn) { announcedConn = true; onMessage({ type: '_connected', connected: true }); }
      onMessage({ type: 'state', state: withDefaults(DEFAULT_STATE, s.data()) });
    }, () => onMessage({ type: '_connected', connected: false }));

    /* live captions (separate high-frequency channel) */
    appDoc('caption').onSnapshot(s => {
      const v = s.data() || {};
      onMessage({ type: 'caption', original: v.original || '', translated: v.translated || '' });
    }, () => {});

    /* transient commands */
    fdb.collection('commands').orderBy('ts', 'desc').limit(1).onSnapshot(s => {
      s.docChanges().forEach(c => {
        if (c.type !== 'added') return;
        const v = c.doc.data();
        if (fresh(v.ts)) onMessage({ type: 'command', name: v.name, payload: v.payload });
      });
    }, () => {});

    /* camera device reports from outputs */
    appDoc('devices').onSnapshot(s => {
      const v = s.data();
      if (v && v.list) onMessage({ type: 'devices', devices: v.list });
    }, () => {});

    /* WebRTC signaling relay */
    fdb.collection('rtc').orderBy('ts', 'desc').limit(20).onSnapshot(s => {
      s.docChanges().filter(c => c.type === 'added').reverse().forEach(c => {
        const v = c.doc.data();
        if (fresh(v.ts) && v.m && v.m.from !== role) onMessage(v.m);
      });
    }, () => {});

    /* caption writes are throttled: at most ~3 per second */
    let capPending = null, capTimer = null;
    function flushCaption() {
      capTimer = null;
      if (!capPending) return;
      const patch = { ts: STS() };
      if ('original' in capPending) patch.original = capPending.original ?? '';
      if ('translated' in capPending) patch.translated = capPending.translated ?? '';
      capPending = null;
      appDoc('caption').set(patch, { merge: true }).catch(() => {});
    }

    return {
      send(msg) {
        msg = clone(msg);            // normalizes RTCIceCandidate etc. via toJSON
        switch (msg.type) {
          case 'hello': break;       // presence already handled
          case 'update': appDoc('state').set(msg.patch || {}, { merge: true }).catch(() => {}); break;
          case 'command': fdb.collection('commands').add({ name: msg.name, payload: msg.payload ?? null, ts: STS() }); break;
          case 'caption':
            capPending = Object.assign(capPending || {}, msg);
            if (!capTimer) capTimer = setTimeout(flushCaption, 300);
            break;
          case 'devices': appDoc('devices').set({ list: msg.devices || [] }); break;
          case 'rtc-offer': case 'rtc-answer': case 'rtc-ice': case 'rtc-stop':
            msg.from = role;
            fdb.collection('rtc').add({ m: msg, ts: STS() });
            break;
        }
      }
    };
  },

  /* -------- song library -------- */
  async listSongs() {
    const s = await fdb.collection('songs').get();
    return s.docs.map(d => ({ ...d.data(), id: d.id }));
  },
  async saveSong(song) {
    const data = { title: song.title, text: song.text || '' };
    const ref = song.id ? fdb.collection('songs').doc(song.id) : fdb.collection('songs').doc();
    await ref.set(data);
    return { ...data, id: ref.id };
  },
  async deleteSong(id) { await fdb.collection('songs').doc(id).delete(); },

  /* -------- media links library -------- */
  async listMedia() {
    let bundled = [];
    try { bundled = await (await fetch('media-manifest.json')).json(); } catch {}
    const s = await fdb.collection('mediaLinks').get();
    const linked = s.docs.map(d => ({ ...d.data(), id: d.id }));
    return [...bundled, ...linked];
  },
  async addMedia(item) { await fdb.collection('mediaLinks').add(item); },
  async deleteMedia(id) { await fdb.collection('mediaLinks').doc(id).delete(); }
};

/* -------- translation (direct from browser; no server needed) -------- */
async function fireTranslate(text, source, target) {
  try {
    const r = await fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=' +
      encodeURIComponent(source || 'auto') + '&tl=' + encodeURIComponent(target) +
      '&dt=t&q=' + encodeURIComponent(text));
    const j = await r.json();
    const out = (j[0] || []).map(p => p[0]).join('');
    if (out) return out;
    throw new Error('empty');
  } catch {
    try {
      const r = await fetch('https://api.mymemory.translated.net/get?q=' + encodeURIComponent(text) +
        '&langpair=' + encodeURIComponent((source || 'en') + '|' + target));
      const j = await r.json();
      return j.responseData && j.responseData.translatedText;
    } catch { return null; }
  }
}
