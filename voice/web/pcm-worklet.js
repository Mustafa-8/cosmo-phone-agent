// Captures mic audio, downsamples to 16 kHz mono PCM16, posts 100 ms chunks to the main thread.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / 16000
    this.pos = 0
    this.out = new Int16Array(1600)
    this.n = 0
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch) return true
    // simple decimation with averaging; good enough for speech recognition
    while (this.pos < ch.length) {
      const start = Math.floor(this.pos)
      const end = Math.min(ch.length, Math.floor(this.pos + this.ratio))
      let sum = 0
      for (let i = start; i < Math.max(end, start + 1); i++) sum += ch[i]
      const v = sum / Math.max(1, end - start)
      this.out[this.n++] = Math.max(-32768, Math.min(32767, Math.round(v * 32767)))
      if (this.n === this.out.length) {
        this.port.postMessage(this.out.buffer.slice(0))
        this.n = 0
      }
      this.pos += this.ratio
    }
    this.pos -= ch.length
    return true
  }
}
registerProcessor('pcm-worklet', PcmWorklet)
