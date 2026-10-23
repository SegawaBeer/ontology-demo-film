type Nodes = {
  master: GainNode;
  air: AudioBufferSourceNode;
  airFilter: BiquadFilterNode;
  airGain: GainNode;
  whine: OscillatorNode;
  whineGain: GainNode;
  rumble: AudioBufferSourceNode;
  rumbleFilter: BiquadFilterNode;
  rumbleGain: GainNode;
};

export class EngineAudio {
  private context: AudioContext | null = null;
  private nodes: Nodes | null = null;
  private enabled = false;
  private running = false;
  private volume = 0.3;

  get isOn() { return this.enabled; }

  private noise(seconds: number) {
    const context = this.context!;
    const buffer = context.createBuffer(1, context.sampleRate * seconds, context.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < data.length; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * 3.2;
    }
    return buffer;
  }

  private build() {
    const context = this.context!;
    const master = context.createGain();
    master.gain.value = 0;
    master.connect(context.destination);

    const air = context.createBufferSource();
    air.buffer = this.noise(2);
    air.loop = true;
    const airFilter = context.createBiquadFilter();
    airFilter.type = 'bandpass';
    airFilter.frequency.value = 1400;
    airFilter.Q.value = 0.7;
    const airGain = context.createGain();
    airGain.gain.value = 0.25;
    air.connect(airFilter).connect(airGain).connect(master);

    const whine = context.createOscillator();
    whine.type = 'sine';
    whine.frequency.value = 1180;
    const whineGain = context.createGain();
    whineGain.gain.value = 0;
    whine.connect(whineGain).connect(master);

    const rumble = context.createBufferSource();
    rumble.buffer = this.noise(2);
    rumble.loop = true;
    const rumbleFilter = context.createBiquadFilter();
    rumbleFilter.type = 'lowpass';
    rumbleFilter.frequency.value = 180;
    const rumbleGain = context.createGain();
    rumbleGain.gain.value = 0;
    rumble.connect(rumbleFilter).connect(rumbleGain).connect(master);

    air.start(); whine.start(); rumble.start();
    this.nodes = { master, air, airFilter, airGain, whine, whineGain, rumble, rumbleFilter, rumbleGain };
  }

  private apply() {
    if (!this.context || !this.nodes) return;
    const now = this.context.currentTime;
    const audible = this.enabled && this.running;
    this.nodes.master.gain.setTargetAtTime(audible ? this.volume : 0, now, 0.15);
    this.nodes.rumbleGain.gain.setTargetAtTime(audible ? 0.35 : 0, now, 0.3);
    this.nodes.whineGain.gain.setTargetAtTime(audible ? 0.06 : 0, now, 0.2);
  }

  async toggle() {
    if (!this.context) {
      this.context = new AudioContext();
      this.build();
    }
    if (this.context.state === 'suspended') await this.context.resume();
    this.enabled = !this.enabled;
    this.apply();
    return this.enabled;
  }

  setRunning(running: boolean) {
    this.running = running;
    this.apply();
  }

  setVolume(value: number) {
    this.volume = Math.max(0, Math.min(1, value));
    this.apply();
  }
}
