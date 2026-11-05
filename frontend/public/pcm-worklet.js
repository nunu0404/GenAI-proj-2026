/*
 * pcm-capture: 마이크 입력(Float32, AudioContext 의 실제 sampleRate) → 24kHz mono PCM16 LE, 100ms 청크.
 * 다운샘플링 시 윈도우드-싱크 FIR 저역통과 필터로 앨리어싱을 줄인 뒤 선형 보간으로 리샘플링한다.
 */
class PcmCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.target = opts.targetRate || 24000;
    this.chunk = Math.round(this.target * ((opts.chunkMs || 100) / 1000));
    this.ratio = sampleRate / this.target; // 입력 샘플 / 출력 샘플
    this.taps = this.ratio > 1.0001 ? PcmCapture.lowpass(0.45 / this.ratio, 63) : null;
    this.hist = this.taps ? new Float32Array(this.taps.length) : null;
    this.hi = 0;
    this.buf = new Float32Array(4096);
    this.len = 0;
    this.pos = 0;
    this.out = new Int16Array(this.chunk);
    this.outLen = 0;
    this.port.postMessage({ type: "info", inputRate: sampleRate, targetRate: this.target });
  }

  static lowpass(fc, n) {
    const h = new Float32Array(n);
    const m = (n - 1) / 2;
    let sum = 0;
    for (let i = 0; i < n; i++) {
      const x = i - m;
      const sinc = x === 0 ? 2 * fc : Math.sin(2 * Math.PI * fc * x) / (Math.PI * x);
      const w = 0.42 - 0.5 * Math.cos((2 * Math.PI * i) / (n - 1)) + 0.08 * Math.cos((4 * Math.PI * i) / (n - 1));
      h[i] = sinc * w;
      sum += h[i];
    }
    for (let i = 0; i < n; i++) h[i] /= sum;
    return h;
  }

  filter(x) {
    if (!this.taps) return x;
    const n = this.taps.length;
    this.hist[this.hi] = x;
    let acc = 0;
    let idx = this.hi;
    for (let k = 0; k < n; k++) {
      acc += this.taps[k] * this.hist[idx];
      idx = idx === 0 ? n - 1 : idx - 1;
    }
    this.hi = (this.hi + 1) % n;
    return acc;
  }

  push(y) {
    const s = Math.max(-1, Math.min(1, y));
    this.out[this.outLen++] = s < 0 ? s * 0x8000 : s * 0x7fff;
    if (this.outLen === this.chunk) {
      const b = this.out.buffer;
      this.port.postMessage({ type: "pcm", buffer: b }, [b]);
      this.out = new Int16Array(this.chunk);
      this.outLen = 0;
    }
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) return true;
    const ch = input[0];
    if (this.len + ch.length > this.buf.length) {
      const nb = new Float32Array((this.len + ch.length) * 2);
      nb.set(this.buf.subarray(0, this.len));
      this.buf = nb;
    }
    for (let i = 0; i < ch.length; i++) this.buf[this.len++] = this.filter(ch[i]);
    while (this.pos + 1 < this.len) {
      const i = Math.floor(this.pos);
      const f = this.pos - i;
      this.push(this.buf[i] * (1 - f) + this.buf[i + 1] * f);
      this.pos += this.ratio;
    }
    const consumed = Math.floor(this.pos);
    if (consumed > 0) {
      this.buf.copyWithin(0, consumed, this.len);
      this.len -= consumed;
      this.pos -= consumed;
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
