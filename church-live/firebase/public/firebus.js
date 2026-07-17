/*
 * FireBus — drop-in replacement for the local WebSocket hub, powered by
 * Firebase Realtime Database. Exposes the same message protocol the pages
 * already speak: hello / update / command / caption / devices / rtc-*.
 */
/* global firebase */

const firebaseConfig = {
  apiKey: 'AIzaSyBMCsGZPcC13iaadwG6yQmZOKYs1kGRLaQ',
  authDomain: 'church-live-studio-png.firebaseapp.com',
  databaseURL: 'https://church-live-studio-png-default-rtdb.firebaseio.com',
  projectId: 'church-live-studio-png',
  storageBucket: 'church-live-studio-png.firebasestorage.app',
  messagingSenderId: '1063152167128',
  appId: '1:1063152167128:web:75398c042dc87d68b40fad'
};
firebase.initializeApp(firebaseConfig);
const fdb = firebase.database();

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

/* Fill in any keys RTDB dropped (empty arrays/strings/nulls) from defaults */
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

/* Flatten a nested patch into RTDB multi-path update entries (deep merge) */
function flatten(prefix, obj, out) {
  for (const k of Object.keys(obj)) {
    const v = obj[k];
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(prefix + k + '/', v, out);
    else out[prefix + k] = v === undefined ? null : v;
  }
  return out;
}

const FireBus = {
  connect(role, onMessage) {
    let serverOffset = 0;
    fdb.ref('.info/serverTimeOffset').on('value', s => { serverOffset = s.val() || 0; });
    const joinedAt = Date.now();
    const fresh = ts => (ts || 0) > joinedAt + serverOffset - 2000;

    /* presence */
    const me = fdb.ref('bus/presence').push();
    me.onDisconnect().remove();
    me.set({ role });
    fdb.ref('bus/presence').on('value', s => {
      const v = s.val() || {};
      onMessage({ type: 'presence', roles: Object.values(v).map(p => p.role) });
    });

    /* connection indicator */
    fdb.ref('.info/connected').on('value', s => {
      onMessage({ type: '_connected', connected: !!s.val() });
      if (s.val()) { me.onDisconnect().remove(); me.set({ role }); }
    });

    /* control seeds the state on first ever run */
    if (role === 'control') {
      fdb.ref('state').transaction(cur => (cur === null ? clone(DEFAULT_STATE) : undefined));
    }

    /* shared state */
    fdb.ref('state').on('value', s => {
      onMessage({ type: 'state', state: withDefaults(DEFAULT_STATE, s.val()) });
    });

    /* live captions (high frequency, separate channel) */
    fdb.ref('bus/caption').on('value', s => {
      const v = s.val() || {};
      onMessage({ type: 'caption', original: v.original || '', translated: v.translated || '' });
    });

    /* transient commands */
    fdb.ref('bus/commands').limitToLast(3).on('child_added', s => {
      const v = s.val() || {};
      if (fresh(v.ts)) onMessage({ type: 'command', name: v.name, payload: v.payload });
    });

    /* camera device reports from outputs */
    fdb.ref('bus/devices').on('value', s => {
      const v = s.val();
      if (v) onMessage({ type: 'devices', devices: v });
    });

    /* WebRTC signaling relay */
    fdb.ref('bus/rtc').limitToLast(20).on('child_added', s => {
      const v = s.val() || {};
      if (fresh(v.ts) && v.m && v.m.from !== role) onMessage(v.m);
    });

    const TS = firebase.database.ServerValue.TIMESTAMP;
    return {
      send(msg) {
        msg = clone(msg);            // normalizes RTCIceCandidate etc. via toJSON
        switch (msg.type) {
          case 'hello': break;       // presence already handled
          case 'update': fdb.ref().update(flatten('state/', msg.patch || {}, {})); break;
          case 'command': fdb.ref('bus/commands').push({ name: msg.name, payload: msg.payload ?? null, ts: TS }); break;
          case 'caption': {
            const patch = { ts: TS };
            if ('original' in msg) patch.original = msg.original ?? '';
            if ('translated' in msg) patch.translated = msg.translated ?? '';
            fdb.ref('bus/caption').update(patch); break;
          }
          case 'devices': fdb.ref('bus/devices').set(msg.devices || []); break;
          case 'rtc-offer': case 'rtc-answer': case 'rtc-ice': case 'rtc-stop':
            msg.from = role;
            fdb.ref('bus/rtc').push({ m: msg, ts: TS }); break;
        }
      }
    };
  },

  /* -------- song library -------- */
  async listSongs() {
    const s = await fdb.ref('songs').get();
    const v = s.val() || {};
    return Object.entries(v).map(([id, song]) => ({ ...song, id }));
  },
  async saveSong(song) {
    const id = song.id || fdb.ref('songs').push().key;
    const data = { title: song.title, text: song.text || '' };
    await fdb.ref('songs/' + id).set(data);
    return { ...data, id };
  },
  async deleteSong(id) { await fdb.ref('songs/' + id).remove(); },

  /* -------- media links library -------- */
  async listMedia() {
    let bundled = [];
    try { bundled = await (await fetch('media-manifest.json')).json(); } catch {}
    const s = await fdb.ref('mediaLinks').get();
    const v = s.val() || {};
    const linked = Object.entries(v).map(([id, m]) => ({ ...m, id }));
    return [...bundled, ...linked];
  },
  async addMedia(item) { await fdb.ref('mediaLinks').push(item); },
  async deleteMedia(id) { await fdb.ref('mediaLinks/' + id).remove(); }
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
