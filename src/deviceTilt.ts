type Quaternion = { x: number; y: number; z: number; w: number };
type SensorStatus = 'idle' | 'requesting' | 'enabled' | 'denied' | 'unavailable';
type OrientationConstructor = typeof DeviceOrientationEvent & {
  requestPermission?: () => Promise<'granted' | 'denied'>;
};

const radians = Math.PI / 180;
const SETTLE_RANGE_DEGREES = 5;
const SETTLE_DELAY_MS = 1000;
const RECENTER_TIME_MS = 1500;
const clamp = (value: number, min = -1, max = 1) => Math.max(min, Math.min(max, value));
function multiply(a: Quaternion, b: Quaternion): Quaternion {
  return {
    x: a.w*b.x + a.x*b.w + a.y*b.z - a.z*b.y,
    y: a.w*b.y - a.x*b.z + a.y*b.w + a.z*b.x,
    z: a.w*b.z + a.x*b.y - a.y*b.x + a.z*b.w,
    w: a.w*b.w - a.x*b.x - a.y*b.y - a.z*b.z,
  };
}
function orientation(alpha: number, beta: number, gamma: number): Quaternion {
  // DeviceOrientation uses intrinsic Z–X′–Y″ rotations (W3C).
  const z = alpha*radians/2, x = beta*radians/2, y = gamma*radians/2;
  return multiply(multiply({ x: 0, y: 0, z: Math.sin(z), w: Math.cos(z) },
    { x: Math.sin(x), y: 0, z: 0, w: Math.cos(x) }),
    { x: 0, y: Math.sin(y), z: 0, w: Math.cos(y) });
}
const dot = (a: Quaternion, b: Quaternion) => a.x*b.x + a.y*b.y + a.z*b.z + a.w*b.w;
function interpolate(a: Quaternion, b: Quaternion, amount: number): Quaternion {
  let cosine = dot(a, b);
  if (cosine < 0) { b = { x: -b.x, y: -b.y, z: -b.z, w: -b.w }; cosine = -cosine; }
  const angle = Math.acos(clamp(cosine));
  const denominator = Math.sin(angle);
  const first = denominator > .001 ? Math.sin((1-amount)*angle)/denominator : 1-amount;
  const second = denominator > .001 ? Math.sin(amount*angle)/denominator : amount;
  const q = { x: a.x*first+b.x*second, y: a.y*first+b.y*second,
    z: a.z*first+b.z*second, w: a.w*first+b.w*second };
  const length = Math.hypot(q.x, q.y, q.z, q.w);
  return { x: q.x/length, y: q.y/length, z: q.z/length, w: q.w/length };
}

class DeviceTilt {
  private listeners = new Set<() => void>();
  private state = { status: 'idle' as SensorStatus, mobile: false, supported: false, error: '' };
  private viewing = false;
  private listening = false;
  private generation = 0;
  private current?: Quaternion;
  private center?: Quaternion;
  private motionAnchor?: Quaternion;
  private lastMotion = 0;
  private lastRead = 0;

  constructor() {
    const mobile = matchMedia('(pointer: coarse)');
    const updateDevice = () => this.update({ mobile: mobile.matches || navigator.maxTouchPoints > 0,
      supported: typeof window.DeviceOrientationEvent !== 'undefined' });
    updateDevice();
    mobile.addEventListener('change', updateDevice);
    document.addEventListener('visibilitychange', this.syncListening);
    window.addEventListener('pagehide', () => this.stopListening());
    window.addEventListener('pageshow', this.syncListening);
    screen.orientation?.addEventListener('change', this.reset);
    window.addEventListener('orientationchange', this.reset);
  }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  snapshot = () => this.state;
  private update(patch: Partial<typeof this.state>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach(listener => listener());
  }
  private reset = () => {
    this.current = this.center = this.motionAnchor = undefined;
    this.lastMotion = this.lastRead = 0;
  };
  setViewing(viewing: boolean) {
    this.viewing = viewing;
    this.syncListening();
  }
  async enable() {
    if (this.state.status === 'requesting' || this.state.status === 'enabled') return;
    if (!window.isSecureContext || !this.state.supported) {
      this.update({ status: 'unavailable', error: window.isSecureContext ? '此设备不支持方向感应' : '请通过 HTTPS 开启重力感应' });
      return;
    }
    const generation = ++this.generation;
    this.update({ status: 'requesting', error: '' });
    try {
      const api = window.DeviceOrientationEvent as OrientationConstructor;
      // Call directly from the button's gesture, before any unrelated await.
      const permission = api.requestPermission ? await api.requestPermission() : 'granted';
      if (generation !== this.generation) return;
      if (permission !== 'granted') {
        this.update({ status: 'denied', error: '未获传感器权限，可在浏览器设置中允许后重试' });
        return;
      }
      this.reset();
      this.update({ status: 'enabled', error: '' });
      this.syncListening();
    } catch {
      if (generation === this.generation) this.update({ status: 'denied', error: '传感器暂不可用，请检查浏览器权限后重试' });
    }
  }
  disable() {
    ++this.generation;
    this.stopListening();
    this.update({ status: 'idle', error: '' });
  }
  private syncListening = () => {
    if (this.state.status !== 'enabled' || !this.viewing || document.visibilityState === 'hidden') {
      this.stopListening(); return;
    }
    if (!this.listening) {
      this.reset();
      window.addEventListener('deviceorientation', this.sample, { passive: true });
      this.listening = true;
    }
  };
  private stopListening() {
    if (this.listening) window.removeEventListener('deviceorientation', this.sample);
    this.listening = false;
    this.reset();
  }
  private sample = (event: DeviceOrientationEvent) => {
    if (typeof event.beta !== 'number' || typeof event.gamma !== 'number' ||
        !Number.isFinite(event.beta) || !Number.isFinite(event.gamma)) return;
    const now = performance.now();
    const q = orientation(Number.isFinite(event.alpha) ? event.alpha! : 0, event.beta, event.gamma);
    if (!this.center) {
      this.center = this.motionAnchor = q;
      this.lastMotion = this.lastRead = now;
    } else if (this.motionAnchor && 2*Math.acos(clamp(Math.abs(dot(q, this.motionAnchor))))/radians >= SETTLE_RANGE_DEGREES) {
      // Ignore small hand tremors, while deliberate movement still accumulates against an anchor.
      this.motionAnchor = q;
      this.lastMotion = now;
    }
    this.current = q;
  };
  read(now: number) {
    if (!this.listening || !this.current || !this.center) return { x: 0, y: 0, active: this.state.status === 'enabled' };
    const elapsed = Math.min(Math.max(now-this.lastRead, 0), 100);
    this.lastRead = now;
    if (now-this.lastMotion > SETTLE_DELAY_MS) {
      // Adopt the settled holding angle as neutral over a 1.5 second time scale.
      this.center = interpolate(this.center, this.current, 1-Math.exp(-elapsed/RECENTER_TIME_MS));
    }
    const relative = multiply({ x: -this.center.x, y: -this.center.y, z: -this.center.z, w: this.center.w }, this.current);
    const forward = { x: 2*(relative.x*relative.z + relative.w*relative.y),
      y: 2*(relative.y*relative.z-relative.w*relative.x), z: 1-2*(relative.x**2+relative.y**2) };
    const yaw = Math.atan2(forward.x, forward.z)/radians;
    const pitch = Math.atan2(-forward.y, Math.hypot(forward.x, forward.z))/radians;
    const angle = (screen.orientation?.angle ?? (window as Window & { orientation?: number }).orientation ?? 0)*radians;
    return { x: clamp((yaw*Math.cos(angle)+pitch*Math.sin(angle))/20),
      y: clamp((pitch*Math.cos(angle)-yaw*Math.sin(angle))/20), active: true };
  }
}

export const deviceTilt = new DeviceTilt();
