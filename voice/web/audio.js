// Microphone capture and translated-audio playback.

export async function startMic(onChunk, onLevel) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  const ctx = new AudioContext()
  await ctx.audioWorklet.addModule('/pcm-worklet.js')
  const source = ctx.createMediaStreamSource(stream)
  const node = new AudioWorkletNode(ctx, 'pcm-worklet')
  node.port.onmessage = (e) => {
    const buf = e.data
    if (onLevel) {
      const s = new Int16Array(buf)
      let sum = 0
      for (let i = 0; i < s.length; i += 8) sum += s[i] * s[i]
      onLevel(Math.min(1, Math.sqrt(sum / (s.length / 8)) / 8000))
    }
    onChunk(buf)
  }
  source.connect(node)
  // the worklet must be pulled by the graph; route through a muted gain so we never hear ourselves
  const mute = ctx.createGain()
  mute.gain.value = 0
  node.connect(mute).connect(ctx.destination)
  return () => {
    stream.getTracks().forEach((t) => t.stop())
    ctx.close()
  }
}

function b64ToBlob(b64, mime) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

const BCP47 = { en: 'en-US', hu: 'hu-HU', de: 'de-DE', fr: 'fr-FR', es: 'es-ES', it: 'it-IT', ro: 'ro-RO', uk: 'uk-UA', ar: 'ar-SA', zh: 'zh-CN' }

// One queue per participant screen: translations play in order, never on top of each other.
export class PlaybackQueue {
  constructor(onChange) {
    this.items = []
    this.playing = false
    this.current = null
    this.onChange = onChange || (() => {})
  }

  enqueue(item) {
    this.items.push(item)
    if (!this.playing) this._next()
  }

  stop() {
    this.items = []
    if (this.current) this.current.stop()
    window.speechSynthesis?.cancel()
    this._set(false, null)
  }

  _set(playing, item) {
    this.playing = playing
    this.onChange(playing, item)
  }

  _next() {
    const item = this.items.shift()
    if (!item) return this._set(false, null)
    this._set(true, item)
    const done = () => {
      this.current = null
      this._next()
    }
    if (item.audio_b64) {
      const url = URL.createObjectURL(b64ToBlob(item.audio_b64, item.mime || 'audio/mpeg'))
      const el = new Audio(url)
      el.onended = el.onerror = () => { URL.revokeObjectURL(url); done() }
      this.current = { stop: () => { el.pause(); URL.revokeObjectURL(url) } }
      el.play().catch(done)
    } else if (window.speechSynthesis) {
      // Mock mode: no ElevenLabs audio, so let the browser read the translation aloud.
      const u = new SpeechSynthesisUtterance(item.text)
      u.lang = BCP47[item.language] || item.language
      u.onend = u.onerror = done
      this.current = { stop: () => window.speechSynthesis.cancel() }
      window.speechSynthesis.speak(u)
    } else {
      done()
    }
  }
}
