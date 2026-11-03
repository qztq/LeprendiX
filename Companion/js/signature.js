/**
 * signature.js - Performantes, berührungsempfindliches Unterschriftenfeld
 * Speziell abgestimmt auf günstige Tablets mit Touch/Stylus.
 * Nutzt quadratische Bézier-Kurven für butterweiche Strichführung.
 */

class SignaturePad {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext('2d', { alpha: true });
    this.options = Object.assign({
      strokeStyle: '#0f172a',
      lineWidth: 3,
      onBegin: null,
      onEnd: null
    }, options);

    this.isDrawing = false;
    this.points = [];
    this.hasDrawn = false;

    this.initCanvas();
    this.bindEvents();
  }

  initCanvas() {
    this.resizeCanvas();
  }

  resizeCanvas() {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const rect = this.canvas.getBoundingClientRect();
    
    // Aktuelle Unterschrift sichern falls vorhanden
    let dataBackup = null;
    if (this.hasDrawn) {
      try {
        dataBackup = this.canvas.toDataURL();
      } catch (e) {
        dataBackup = null;
      }
    }

    const displayWidth = Math.floor(rect.width || 400);
    const displayHeight = Math.floor(rect.height || 180);

    this.canvas.width = displayWidth * ratio;
    this.canvas.height = displayHeight * ratio;
    this.ctx.scale(ratio, ratio);

    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
    this.ctx.strokeStyle = this.options.strokeStyle;
    this.ctx.lineWidth = this.options.lineWidth;

    if (dataBackup) {
      const img = new Image();
      img.onload = () => {
        this.ctx.drawImage(img, 0, 0, displayWidth, displayHeight);
      };
      img.src = dataBackup;
    }
  }

  getCanvasPoint(e) {
    const rect = this.canvas.getBoundingClientRect();
    const clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
    const clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
    return {
      x: clientX - rect.left,
      y: clientY - rect.top
    };
  }

  bindEvents() {
    // Touch Events
    this.canvas.addEventListener('touchstart', (e) => this.handlePointerStart(e), { passive: false });
    this.canvas.addEventListener('touchmove', (e) => this.handlePointerMove(e), { passive: false });
    window.addEventListener('touchend', (e) => this.handlePointerEnd(e), { passive: false });

    // Mouse / Pointer Events
    this.canvas.addEventListener('pointerdown', (e) => this.handlePointerStart(e));
    this.canvas.addEventListener('pointermove', (e) => this.handlePointerMove(e));
    window.addEventListener('pointerup', (e) => this.handlePointerEnd(e));

    // Resize-Listener
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => this.resizeCanvas(), 150);
    });
  }

  handlePointerStart(e) {
    // Falls Event vom Canvas kommt
    if (e.target !== this.canvas) return;
    if (e.cancelable) e.preventDefault();

    this.isDrawing = true;
    const pt = this.getCanvasPoint(e);
    this.points = [pt];

    this.ctx.beginPath();
    this.ctx.arc(pt.x, pt.y, this.options.lineWidth / 2, 0, Math.PI * 2, true);
    this.ctx.fillStyle = this.options.strokeStyle;
    this.ctx.fill();

    if (typeof this.options.onBegin === 'function') {
      this.options.onBegin();
    }
  }

  handlePointerMove(e) {
    if (!this.isDrawing) return;
    if (e.cancelable) e.preventDefault();

    const pt = this.getCanvasPoint(e);
    this.points.push(pt);
    this.hasDrawn = true;

    if (this.points.length >= 3) {
      const len = this.points.length;
      const p1 = this.points[len - 2];
      const p2 = this.points[len - 1];
      const midPoint = {
        x: (p1.x + p2.x) / 2,
        y: (p1.y + p2.y) / 2
      };

      this.ctx.beginPath();
      this.ctx.moveTo(p1.x, p1.y);
      this.ctx.quadraticCurveTo(p1.x, p1.y, midPoint.x, midPoint.y);
      this.ctx.stroke();
    } else if (this.points.length === 2) {
      const p0 = this.points[0];
      const p1 = this.points[1];
      this.ctx.beginPath();
      this.ctx.moveTo(p0.x, p0.y);
      this.ctx.lineTo(p1.x, p1.y);
      this.ctx.stroke();
    }
  }

  handlePointerEnd(e) {
    if (!this.isDrawing) return;
    this.isDrawing = false;
    this.points = [];

    if (typeof this.options.onEnd === 'function') {
      this.options.onEnd();
    }
  }

  clear() {
    const rect = this.canvas.getBoundingClientRect();
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.hasDrawn = false;
    this.points = [];
  }

  isEmpty() {
    return !this.hasDrawn;
  }

  toDataURL(type = 'image/png') {
    if (this.isEmpty()) return null;
    return this.canvas.toDataURL(type);
  }
}

