# ✝ Church Live Studio

A professional live-production web app for church services — run your whole broadcast from a browser:

- 🎬 **Program switcher** — holding screen, cameras, videos, images, lyrics, scripture, black
- 📷 **Camera angles** — switch between webcams on the output machine, **plus** stream any phone/laptop
  camera on your Wi-Fi to the program output over WebRTC ("Presenter Cam")
- 🎵 **Song lyrics projection** — song library with verse-by-verse projection (arrow-key advance)
- 📖 **Scripture display** — beautiful full-screen verse slides
- 🎧 **Music player** — worship audio with volume, loop and fade-out (audio plays through the output so OBS captures it)
- 📰 **Headline ticker** — scrolling announcements bar at the bottom of the screen
- 🪪 **Lower thirds** — speaker name/title straps in four styles
- 🌍 **Live translation captions** — browser speech recognition transcribes the sermon and auto-translates
  it into a second language, shown as broadcast subtitles
- 🖥️ **Stage display** — confidence monitor with current lyrics, clock, and messages to the stage
- 📡 **Stream-ready output** — clean 1920×1080 program feed for OBS → YouTube, Facebook, etc.

## Run it

```bash
cd church-live
npm install
npm start
```

Then open:

| Page | URL | Who uses it |
|---|---|---|
| Home & streaming guide | http://localhost:3000/ | everyone |
| **Control Room** | http://localhost:3000/control.html | the operator |
| **Program Output** | http://localhost:3000/output.html | projector / OBS browser source |
| Stage Display | http://localhost:3000/stage.html | worship team monitor |

Other devices on the same network can join via your computer's IP, e.g.
`http://192.168.1.20:3000/control.html`.

## Go live on YouTube / Facebook

1. Install [OBS Studio](https://obsproject.com) (free).
2. Add a **Browser** source: `http://localhost:3000/output.html`, 1920×1080, ✔ *Control audio via OBS*.
3. Get your **Stream key** from YouTube Studio (*Create → Go live*) or Facebook Live Producer
   (*Live video → Streaming software*).
4. OBS → *Settings → Stream* → choose the service, paste the key, **Start Streaming**.
5. Stream to both at once with OBS multi-output or a restream service (Restream.io, Castr).

The full illustrated guide is on the app's home page.

## Media

Upload videos/images/music from the Control Room, or just drop files into the `media/` folder.
Songs are saved to `data/songs.json`.

## Notes

- Live captions use the browser's Web Speech API — best in **Chrome or Edge**, requires internet.
- Translation uses a free public endpoint; for mission-critical use plug an API key of your choice
  into `/api/translate` in `server.js`.
- Camera/microphone access requires `localhost` or HTTPS (browser security rule). On the local network,
  Chrome flag `unsafely-treat-insecure-origin-as-secure` or a reverse proxy with TLS enables phone cameras.
