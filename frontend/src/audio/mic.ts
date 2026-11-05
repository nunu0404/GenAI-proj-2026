// 마이크 캡처: getUserMedia → AudioWorklet(pcm-capture) → 24kHz PCM16 LE mono 100ms 청크

export const TARGET_RATE = 24000;

export interface MicHandle {
  stop: () => void;
  inputRate: number;
}

export class MicError extends Error {
  constructor(public code: "permission" | "no_device" | "busy" | "insecure" | "unsupported" | "unknown", message: string) {
    super(message);
  }
}

function explain(e: unknown): MicError {
  const name = (e as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return new MicError("permission", "마이크 권한이 거부되었습니다. 브라우저 주소창의 권한 설정에서 마이크를 허용해 주세요.");
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return new MicError("no_device", "사용할 수 있는 마이크 장치를 찾을 수 없습니다.");
  if (name === "NotReadableError" || name === "AbortError")
    return new MicError("busy", "마이크를 열 수 없습니다. 다른 프로그램이 사용 중인지 확인해 주세요.");
  return new MicError("unknown", `마이크 시작 실패: ${name || String(e)}`);
}

export async function startMic(
  onChunk: (pcm: ArrayBuffer) => void,
  onEnded: (msg: string) => void,
): Promise<MicHandle> {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
    throw new MicError("insecure", "마이크는 HTTPS 또는 localhost 에서만 사용할 수 있습니다.");
  if (typeof AudioWorkletNode === "undefined")
    throw new MicError("unsupported", "이 브라우저는 AudioWorklet 을 지원하지 않습니다. 최신 Chrome/Edge/Firefox 를 사용해 주세요.");

  let stream: MediaStream;
  try {
    const gum = navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    let timer: number | undefined;
    try {
      stream = await Promise.race([
        gum,
        new Promise<never>((_, rej) => {
          timer = window.setTimeout(() => {
            // 시간 초과 후 늦게 허용되더라도 장치를 잡고 있지 않도록 정리
            gum.then((st) => st.getTracks().forEach((t) => t.stop())).catch(() => undefined);
            rej(new MicError("busy", "마이크 응답이 없습니다. 브라우저/운영체제의 마이크 권한 대화상자를 확인해 주세요."));
          }, 20000);
        }),
      ]);
    } finally {
      window.clearTimeout(timer);
    }
  } catch (e) {
    throw e instanceof MicError ? e : explain(e);
  }
  const ctx = new AudioContext(); // 장치 기본 샘플레이트 사용 → 워클릿에서 24kHz 로 리샘플링
  try {
    await ctx.audioWorklet.addModule("/pcm-worklet.js");
  } catch (e) {
    stream.getTracks().forEach((t) => t.stop());
    await ctx.close();
    throw new MicError("unsupported", "오디오 처리 모듈을 불러오지 못했습니다.");
  }
  const src = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "pcm-capture", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    channelCount: 1,
    channelCountMode: "explicit",
    channelInterpretation: "speakers",
    processorOptions: { targetRate: TARGET_RATE, chunkMs: 100 },
  });
  node.port.onmessage = (ev) => {
    if (ev.data?.type === "pcm") onChunk(ev.data.buffer as ArrayBuffer);
  };
  const mute = ctx.createGain();
  mute.gain.value = 0;
  src.connect(node).connect(mute).connect(ctx.destination);
  if (ctx.state === "suspended") await ctx.resume();

  let stopped = false;
  const track = stream.getAudioTracks()[0];
  track.addEventListener("ended", () => {
    if (!stopped) onEnded("마이크 장치 연결이 끊어졌습니다.");
  });

  return {
    inputRate: ctx.sampleRate,
    stop: () => {
      stopped = true;
      node.port.onmessage = null;
      try {
        src.disconnect();
        node.disconnect();
      } catch {
        /* noop */
      }
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
    },
  };
}
