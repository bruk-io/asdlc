    /* ---- music: a cosy loop made in the browser, original and never quite the same twice. Off until the Music button is pressed. ----
       Four bars of slow chords (C, A minor, F, G) under a plucked, kalimba-like melody that wanders a five-note scale.
       It follows the village: more notes and a soft shaker when more agents are awake; slower, lower and darker at night, with the odd bell. */
    let busyNow = 0, audio = null;
    function startMusic() {
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return null;
      const ctx = new AC(), master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination);
      const tone = ctx.createBiquadFilter(); tone.type = 'lowpass'; tone.frequency.value = 5200; tone.connect(master);
      const echo = ctx.createDelay(1), back = ctx.createGain(), wet = ctx.createGain(); echo.delayTime.value = 0.36; back.gain.value = 0.3; wet.gain.value = 0.26; tone.connect(echo); echo.connect(back); back.connect(echo); echo.connect(wet); wet.connect(master);
      const hiss = ctx.createBuffer(1, ctx.sampleRate * 0.2, ctx.sampleRate); { const d = hiss.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; }
      const freq = (m) => 440 * Math.pow(2, (m - 69) / 12);
      // One note: a wave that swells quickly and dies away.
      const note = (m, at, dur, vol, type, attack) => { const o = ctx.createOscillator(), g = ctx.createGain(); o.type = type || 'sine'; o.frequency.value = freq(m);
        g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(vol, at + (attack || 0.008)); g.gain.exponentialRampToValueAtTime(0.0001, at + dur); o.connect(g); g.connect(tone); o.start(at); o.stop(at + dur + 0.05); };
      const pluck = (m, at, vol) => { note(m, at, 0.9, vol, 'sine'); note(m + 12, at, 0.45, vol * 0.3, 'triangle'); note(m + 19, at, 0.22, vol * 0.2, 'sine'); };
      const shaker = (at, vol) => { const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain(); s.buffer = hiss; f.type = 'highpass'; f.frequency.value = 6000; g.gain.setValueAtTime(vol, at); g.gain.exponentialRampToValueAtTime(0.0001, at + 0.07); s.connect(f); f.connect(g); g.connect(master); s.start(at); s.stop(at + 0.1); };
      const CHORDS = [[48, [60, 64, 67, 72]], [45, [60, 64, 69, 72]], [41, [60, 65, 69, 72]], [43, [59, 62, 67, 71]]], SCALE = [60, 62, 64, 67, 69, 72, 74, 76, 79];
      let step = 0, next = ctx.currentTime + 0.1, walk = 4, failed = false;
      const tick = () => {
        if (next < ctx.currentTime) next = ctx.currentTime + 0.05;
        while (next < ctx.currentTime + 0.25) {
          const dark = night, busy = Math.min(1, busyNow / 5), pos = step % 8, chord = CHORDS[Math.floor(step / 8) % 4], root = chord[0], tones = chord[1], eighth = 60 / (86 - 20 * dark) / 2;
          tone.frequency.setTargetAtTime(5200 - 3000 * dark, next, 0.5);
          if (pos === 0) { note(root, next, eighth * 7, 0.16, 'triangle', 0.02); tones.slice(0, 3).forEach((m, i) => note(m - 12, next + i * 0.012, eighth * 8, 0.035, 'triangle', 0.25)); }
          if (pos === 4) note(root + 7, next, eighth * 3.5, 0.11, 'triangle', 0.02);
          const chance = (pos % 2 === 0 ? 0.5 + busy * 0.4 : 0.12 + busy * 0.45) * (1 - 0.45 * dark);
          if (Math.random() < chance) { walk = Math.max(0, Math.min(SCALE.length - 1, walk + Math.round((Math.random() - 0.5) * 4))); const m = pos === 0 ? tones[Math.floor(Math.random() * tones.length)] : SCALE[walk]; pluck(m - (dark > 0.6 ? 12 : 0), next, 0.13 + busy * 0.05); }
          if (busy > 0.5 && pos % 2 === 1 && dark < 0.5) shaker(next, 0.02);
          if (dark > 0.6 && pos === 6 && Math.random() < 0.35) note(tones[2] + 12, next, 2.2, 0.04, 'sine', 0.05);
          next += eighth; step++;
        }
      };
      const timer = setInterval(() => { try { tick(); } catch (e) { if (!failed) { failed = true; $('#music').textContent = 'Music Unavailable'; } } }, 60);
      master.gain.setTargetAtTime(0.5, ctx.currentTime, 0.4); if (ctx.state === 'suspended') ctx.resume();
      return { stop() { clearInterval(timer); master.gain.setTargetAtTime(0, ctx.currentTime, 0.12); setTimeout(() => ctx.close(), 700); },
        // A rising four-note chime, for a merge.
        chime() { [72, 76, 79, 84].forEach((m, i) => pluck(m, ctx.currentTime + 0.02 + i * 0.09, 0.2)); } };
    }
    { const btn = $('#music'), set = (on) => { if (on && !audio) audio = startMusic(); else if (!on && audio) { audio.stop(); audio = null; } btn.setAttribute('aria-pressed', !!audio); btn.textContent = audio ? 'Music On' : 'Music Off'; };
      btn.addEventListener('click', () => set(!audio)); if (/[#&]music\b/.test(location.hash)) set(true); }
