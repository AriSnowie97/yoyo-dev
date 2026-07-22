/**
 * YoYo Dev v2 🪀 — Interactive game engine
 * Spring physics yo-yo + combo tricks + agent notifications
 */

// ═══════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════
const CANVAS_W = 420;
const CANVAS_H = 540;
const HAND_X   = CANVAS_W / 2;
const HAND_Y   = 72;
const MAX_STR  = CANVAS_H - 100;   // max string length px
const MIN_STR  = 20;
const GRAVITY  = 900;              // px/s²
const SPRING_K = 18;               // spring constant
const DAMPING  = 0.88;             // velocity damping on bounce

// Tricks catalog
const TRICKS = {
  sleeper:  { name: 'SLEEPER',       pts: 5,  minHold: 1.2, color: '#00ff41' },
  walkdog:  { name: 'WALK THE DOG',  pts: 10, minHold: 0.8, color: '#00d4ff' },
  rockbaby: { name: 'ROCK THE BABY', pts: 15, minHold: 1.0, color: '#cc44ff' },
  loop:     { name: 'LOOP THE LOOP', pts: 30, minHold: 0.0, color: '#ffe600' },
  around:   { name: 'AROUND THE WORLD', pts: 25, minHold: 1.5, color: '#ff8800' },
  eiffel:   { name: 'EIFFEL TOWER',  pts: 35, minHold: 1.8, color: '#ff00aa' },
  atom:     { name: 'ATOM SMASHER',  pts: 45, minHold: 1.9, color: '#00ffcc' },
  string:   { name: 'STRING BURN',   pts: 50, minHold: 2.0, color: '#ff2244' },
};

// ═══════════════════════════════════════════════════
// GAME STATE
// ═══════════════════════════════════════════════════
class YoYoGame {
  constructor() {
    this.canvas  = document.getElementById('game-canvas');
    this.ctx     = this.canvas.getContext('2d');

    // Yo-yo physics
    this.strLen  = 30;           // current string length
    this.strVel  = 0;            // string velocity (positive = extending)
    this.swingX  = HAND_X;      // yo-yo X (swinging)
    this.swingVX = 0;
    this.spin    = 0;
    this.spinRate = 0;

    // State machine
    // 'ready' | 'falling' | 'bottom' | 'rising' | 'trick'
    this.phase   = 'ready';
    this.holdTimer = 0;          // seconds held at bottom
    this.pendingTrick = null;    // trick requested by player

    // Scoring
    this.score   = 0;
    this.combo   = 1;
    this.comboTimer = 0;         // resets combo if no trick
    this.tricksCount = 0;
    this.agentBonus = 0;

    // Input
    this.inputDown   = false;
    this.lastTapTime = 0;
    this.mouseX      = HAND_X;

    // Visual
    this.t       = 0;            // time counter
    this.particles = [];

    // Bind events
    this._bindInput();
    this._loop();
  }

  // ─── Input ────────────────────────────────────────
  _bindInput() {
    const canvas = this.canvas;

    // Keyboard
    document.addEventListener('keydown', e => {
      if (e.code === 'Space') { e.preventDefault(); this._press(); }
    });
    document.addEventListener('keyup', e => {
      if (e.code === 'Space') this._release();
    });

    // Mouse
    canvas.addEventListener('mousedown', e => {
      this.mouseX = e.offsetX * (CANVAS_W / canvas.getBoundingClientRect().width);
      this._press();
    });
    canvas.addEventListener('mouseup',   () => this._release());
    canvas.addEventListener('mousemove', e => {
      this.mouseX = e.offsetX * (CANVAS_W / canvas.getBoundingClientRect().width);
    });

    // Touch
    canvas.addEventListener('touchstart', e => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      this.mouseX = (e.touches[0].clientX - r.left) * (CANVAS_W / r.width);
      this._press();
    });
    canvas.addEventListener('touchend', () => this._release());
  }

  _press() {
    if (!this.inputDown) {
      this.inputDown = true;
      const now = performance.now();

      // Double-tap detection → Loop the Loop
      if (now - this.lastTapTime < 350 && this.phase === 'ready') {
        this.pendingTrick = 'loop';
      }
      this.lastTapTime = now;

      // Throw on press if ready
      if (this.phase === 'ready') {
        this._throw();
      }
    }
  }

  _release() {
    if (this.inputDown) {
      this.inputDown = false;

      // If held at bottom → trigger sleeper/trick on release
      if (this.phase === 'bottom' && this.holdTimer > 0.3) {
        this._triggerHoldTrick();
      } else if (this.phase === 'bottom') {
        // Just release — come back
        this.phase = 'rising';
        this.strVel = -380;
      }
    }
  }

  _throw() {
    if (this.phase !== 'ready') return;
    this.phase   = 'falling';
    this.strVel  = 320;
    // Swing toward mouse X
    const dX     = this.mouseX - HAND_X;
    this.swingVX = dX * 0.6;
    addLog('⬇ Throw!', 'log-system');
  }

  // ─── Trick API (also called from sidebar buttons) ─
  requestTrick(id) {
    if (this.phase === 'bottom') {
      this.pendingTrick = id;
      this._triggerHoldTrick();
    } else if (this.phase === 'ready' && id === 'loop') {
      this.pendingTrick = 'loop';
      this._throw();
    } else {
      // Queue it for next bottom
      this.pendingTrick = id;
      if (this.phase === 'ready') this._throw();
    }
  }

  _triggerHoldTrick() {
    const id = this.pendingTrick || this._pickTrickByHold();
    this.pendingTrick = null;
    const trick = TRICKS[id];
    if (!trick) { this.phase = 'rising'; this.strVel = -380; return; }

    // Flash trick name
    this._doTrick(id, trick);

    // Return after trick
    setTimeout(() => {
      if (this.phase === 'trick') {
        this.phase = 'rising';
        this.strVel = -380;
      }
    }, 600);
  }

  _pickTrickByHold() {
    if (this.holdTimer >= 2.0) return 'string';
    if (this.holdTimer >= 1.5) return 'around';
    if (this.holdTimer >= 1.0) return 'rockbaby';
    if (this.holdTimer >= 0.8) return 'walkdog';
    return 'sleeper';
  }

  _doTrick(id, trick) {
    this.phase = 'trick';
    const pts = trick.pts * this.combo;
    this.score += pts;
    this.tricksCount++;

    // Combo
    this.combo = Math.min(this.combo + 1, 8);
    this.comboTimer = 4.0;
    this._burstParticles(this.swingX, HAND_Y + this.strLen, trick.color);

    // Highlight trick in sidebar
    const el = document.getElementById(`t-${id}`);
    if (el) { el.classList.add('active'); setTimeout(() => el.classList.remove('active'), 600); }

    // Flash text on canvas
    showTrickFlash(`★ ${trick.name} ★\n+${pts} PTS`);

    // Score pop at canvas center
    spawnScorePop(`+${pts}`, trick.color);

    // Log
    addLog(`⚡ ${trick.name} +${pts}pts`, 'log-trick');

    // Update HUD
    updateHUD(this);
  }

  // ─── Physics Update ────────────────────────────────
  update(dt) {
    this.t += dt;

    // Combo decay
    if (this.comboTimer > 0) {
      this.comboTimer -= dt;
      if (this.comboTimer <= 0) {
        this.combo = 1;
        updateHUD(this);
      }
    }

    switch (this.phase) {

      case 'ready': {
        // Gentle idle sway
        this.strLen  = MIN_STR + Math.sin(this.t * 1.2) * 6;
        this.swingX  = HAND_X + Math.sin(this.t * 0.9) * 12;
        this.spinRate = 2;
        break;
      }

      case 'falling': {
        this.strVel += GRAVITY * dt;
        this.strLen += this.strVel * dt;
        // Swing follow mouse
        const targetX = this.inputDown ? this.mouseX : HAND_X;
        this.swingVX += (targetX - this.swingX) * 4 * dt;
        this.swingVX *= 0.92;
        this.swingX  += this.swingVX * dt;
        this.spinRate = 15 + this.strVel * 0.02;

        if (this.strLen >= MAX_STR) {
          this.strLen = MAX_STR;
          if (this.inputDown) {
            // Player holding — go to bottom
            this.phase   = 'bottom';
            this.strVel  = 0;
            this.holdTimer = 0;
          } else {
            // Natural bounce
            this.strVel *= -DAMPING;
            this.phase   = 'rising';
          }
        }
        break;
      }

      case 'bottom': {
        this.holdTimer += dt;
        this.strLen = MAX_STR + Math.sin(this.t * 25) * 2; // spin shimmy
        this.swingX += (HAND_X - this.swingX) * 3 * dt;
        this.spinRate = 22;

        // Auto-trigger trick if held long enough and player not still holding
        if (!this.inputDown) {
          this._triggerHoldTrick();
        }
        break;
      }

      case 'trick': {
        // Yo-yo does trick animation
        this.strLen = MAX_STR - 20 + Math.sin(this.t * 30) * 20;
        this.swingX = HAND_X + Math.cos(this.t * 12) * 40;
        this.spinRate = 30;
        break;
      }

      case 'rising': {
        this.strVel -= GRAVITY * 0.3 * dt; // gentler decel
        this.strLen += this.strVel * dt;
        this.swingX += (HAND_X - this.swingX) * 5 * dt;
        this.spinRate = Math.abs(this.strVel) * 0.05;

        if (this.strLen <= MIN_STR) {
          this.strLen  = MIN_STR;
          this.strVel  = 0;
          this.swingX  = HAND_X;
          this.phase   = 'ready';
          this.holdTimer = 0;

          // Pending trick (e.g. loop requested while airborne)
          if (this.pendingTrick === 'loop') {
            this.pendingTrick = null;
            setTimeout(() => this._throw(), 80);
          }
        }
        break;
      }
    }

    this.spin += this.spinRate * dt;

    // Update particles
    this.particles.forEach(p => {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 200 * dt;
      p.life -= dt;
    });
    this.particles = this.particles.filter(p => p.life > 0);
  }

  _burstParticles(cx, cy, color) {
    for (let i = 0; i < 18; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = 60 + Math.random() * 120;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(a) * s,
        vy: Math.sin(a) * s - 80,
        life: 0.6 + Math.random() * 0.4,
        size: 5 + Math.random() * 6,
        color,
      });
    }
  }

  // ─── Render ────────────────────────────────────────
  render() {
    const ctx = this.ctx;
    const cx  = this.swingX;
    const cy  = HAND_Y + this.strLen;

    // BG
    ctx.fillStyle = '#030a04';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    // Grid
    ctx.strokeStyle = 'rgba(0,255,65,0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x < CANVAS_W; x += 20) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CANVAS_H); ctx.stroke();
    }
    for (let y = 0; y < CANVAS_H; y += 20) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(CANVAS_W, y); ctx.stroke();
    }

    // Shadow under yo-yo
    const alpha = 0.15 + 0.25 * ((this.strLen - MIN_STR) / (MAX_STR - MIN_STR));
    ctx.beginPath();
    ctx.ellipse(cx, CANVAS_H - 18, 28, 6, 0, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(0,255,65,${alpha})`;
    ctx.fill();

    // String (curved)
    const midX = (HAND_X + cx) / 2 + (cx - HAND_X) * 0.1;
    const midY = (HAND_Y + cy) / 2;
    ctx.beginPath();
    ctx.moveTo(HAND_X, HAND_Y + 14);
    ctx.quadraticCurveTo(midX, midY, cx, cy - 26);
    ctx.strokeStyle = this._stringColor();
    ctx.lineWidth = 2;
    ctx.setLineDash([]);
    ctx.stroke();

    // Yo-yo disc (pixel art)
    this._drawDisc(ctx, cx, cy, 28);

    // Hand
    this._drawHand(ctx, HAND_X, HAND_Y);

    // Hold meter (shown at bottom)
    if (this.phase === 'bottom' || this.phase === 'trick') {
      const pct = Math.min(this.holdTimer / 2.0, 1.0);
      const bw = 80; const bh = 6;
      const bx = cx - bw/2; const by = cy + 36;
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(bx - 1, by - 1, bw + 2, bh + 2);
      const holdColor = pct > 0.8 ? '#ff2244' : pct > 0.5 ? '#ffe600' : '#00d4ff';
      ctx.fillStyle = holdColor;
      ctx.fillRect(bx, by, bw * pct, bh);
      if (pct > 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '5px "Press Start 2P"';
        ctx.textAlign = 'center';
        ctx.fillText('HOLD', cx, by - 4);
        ctx.textAlign = 'left';
      }
    }

    // Phase indicator (top left)
    const phaseGlyph = { ready:'●', falling:'↓', bottom:'◉', rising:'↑', trick:'★' }[this.phase] || '';
    ctx.font = '8px "Press Start 2P"';
    ctx.fillStyle = 'rgba(0,255,65,0.3)';
    ctx.fillText(phaseGlyph, 8, 20);

    // Particles
    this.particles.forEach(p => {
      ctx.globalAlpha = p.life;
      ctx.fillStyle = p.color;
      ctx.fillRect(Math.round(p.x - p.size/2), Math.round(p.y - p.size/2), Math.round(p.size), Math.round(p.size));
    });
    ctx.globalAlpha = 1;

    // Scanlines
    for (let y = 0; y < CANVAS_H; y += 4) {
      ctx.fillStyle = 'rgba(0,0,0,0.05)';
      ctx.fillRect(0, y, CANVAS_W, 2);
    }
  }

  _stringColor() {
    const c = { ready:'#004411', falling:'#005511', bottom:'#0066aa', trick:'#886600', rising:'#004411' };
    return c[this.phase] || '#004411';
  }

  _drawDisc(ctx, cx, cy, r) {
    const colors = {
      ready:   { outer: '#00aa2a', inner: '#00ff41' },
      falling: { outer: '#0088bb', inner: '#00d4ff' },
      bottom:  { outer: '#007acc', inner: '#33ddff' },
      trick:   { outer: '#cc8800', inner: '#ffe600' },
      rising:  { outer: '#00aa2a', inner: '#00ff41' },
    };
    const col = colors[this.phase] || colors.ready;
    const px = 4;

    // Outer disc (blocky circles)
    ctx.fillStyle = col.outer;
    for (let dx = -r; dx <= r; dx += px) {
      for (let dy = -r; dy <= r; dy += px) {
        if (dx*dx + dy*dy <= r*r) {
          ctx.fillRect(Math.round(cx+dx-px/2), Math.round(cy+dy-px/2), px, px);
        }
      }
    }

    // Spin highlight
    const hx = Math.cos(this.spin) * r * 0.45;
    const hy = Math.sin(this.spin) * r * 0.45;
    const hr = Math.max(3, r * 0.28);
    ctx.fillStyle = col.inner;
    for (let dx = -hr; dx <= hr; dx += px) {
      for (let dy = -hr; dy <= hr; dy += px) {
        if (dx*dx + dy*dy <= hr*hr) {
          ctx.fillRect(Math.round(cx+hx+dx-px/2), Math.round(cy+hy+dy-px/2), px, px);
        }
      }
    }

    // Center axle
    ctx.fillStyle = '#111';
    for (let dx = -px; dx <= px; dx += px) {
      for (let dy = -px; dy <= px; dy += px) {
        ctx.fillRect(Math.round(cx+dx-px/2), Math.round(cy+dy-px/2), px, px);
      }
    }

    // Glow
    if (this.phase === 'trick' || this.phase === 'bottom') {
      ctx.globalAlpha = 0.18;
      ctx.beginPath();
      ctx.arc(cx, cy, r + 8, 0, Math.PI * 2);
      ctx.fillStyle = col.inner;
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  _drawHand(ctx, x, y) {
    const blocks = [[x-10,y-4,20,12],[x-8,y+8,5,10],[x-2,y+8,5,10],[x+4,y+8,5,8]];
    ctx.fillStyle = '#225533';
    blocks.forEach(([bx,by,bw,bh]) => ctx.fillRect(bx,by,bw,bh));
    ctx.fillStyle = '#33664a';
    ctx.fillRect(x-9,y-3,18,4);
  }

  // ─── Main loop ─────────────────────────────────────
  _lastTime = 0;
  _loop(ts = 0) {
    const dt = Math.min((ts - this._lastTime) / 1000, 0.05);
    this._lastTime = ts;
    this.update(dt);
    this.render();
    updateHUD(this);
    requestAnimationFrame(t => this._loop(t));
  }

  addAgentBonus(pts) {
    this.agentBonus += pts;
    this.score += pts;
    updateHUD(this);
  }
}

// ═══════════════════════════════════════════════════
// HUD UPDATE
// ═══════════════════════════════════════════════════
function updateHUD(g) {
  setVal('score-val',  g.score);
  setVal('tricks-val', g.tricksCount);
  setVal('bonus-val',  `+${g.agentBonus}`);

  const comboEl = document.getElementById('combo-val');
  const newCombo = `x${g.combo}`;
  if (comboEl.textContent !== newCombo) {
    comboEl.textContent = newCombo;
    document.getElementById('hud-combo').classList.remove('active');
    void document.getElementById('hud-combo').offsetWidth;
    document.getElementById('hud-combo').classList.add('active');
  }
}

function setVal(id, v) {
  const el = document.getElementById(id);
  if (el && el.textContent !== String(v)) el.textContent = v;
}

// ═══════════════════════════════════════════════════
// TRICK FLASH
// ═══════════════════════════════════════════════════
let flashTimeout = null;
function showTrickFlash(text) {
  const el = document.getElementById('trick-flash');
  el.style.whiteSpace = 'pre';
  el.textContent = text;
  el.classList.remove('show');
  void el.offsetWidth;
  el.classList.add('show');
  clearTimeout(flashTimeout);
  flashTimeout = setTimeout(() => el.classList.remove('show'), 1400);
}

// ═══════════════════════════════════════════════════
// SCORE POP
// ═══════════════════════════════════════════════════
function spawnScorePop(text, color = '#ffe600') {
  const el = document.createElement('div');
  el.className = 'score-pop';
  el.textContent = text;
  el.style.color = color;
  el.style.textShadow = `0 0 10px ${color}`;
  // Random x near center
  el.style.left = (window.innerWidth * 0.5 - 150 + Math.random() * 300) + 'px';
  el.style.top  = (window.innerHeight * 0.5 + Math.random() * 60) + 'px';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1300);
}

// ═══════════════════════════════════════════════════
// LOG
// ═══════════════════════════════════════════════════
const MAX_LOG = 40;
function addLog(text, cls = 'log-system') {
  const feed = document.getElementById('log-feed');
  const ts   = new Date().toLocaleTimeString('en-GB', { hour12: false });
  const entry = document.createElement('div');
  entry.className = `log-entry ${cls}`;
  entry.textContent = `[${ts}] ${text}`;
  feed.prepend(entry);
  while (feed.children.length > MAX_LOG) feed.lastChild.remove();
}

// ═══════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════
const MAX_TOASTS = 5;

function showToast({ title, message, bonus_pts, level, duration }) {
  const container = document.getElementById('toast-container');

  // Cap toasts
  while (container.children.length >= MAX_TOASTS) {
    removeToast(container.lastChild);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${level || 'success'}`;

  const bonusLine = bonus_pts > 0
    ? `<div class="toast-bonus">+${bonus_pts} BONUS PTS 🎁</div>`
    : '';

  const durText = duration ? `${Math.round(duration)}s` : '';

  toast.innerHTML = `
    <div class="toast-header">
      <span class="toast-icon">✅</span>
      <span class="toast-title">${escHtml(title)}</span>
      ${durText ? `<span style="font-size:6px;color:rgba(0,255,65,0.4)">${durText}</span>` : ''}
      <span class="toast-close" onclick="removeToast(this.closest('.toast'))">✕</span>
    </div>
    <div class="toast-body">
      <div class="toast-msg">${escHtml(message)}</div>
      ${bonusLine}
    </div>
    <div class="toast-timer"></div>
  `;

  // Customize icon by level
  const icons = { success: '✅', info: 'ℹ️', warning: '⚠️', error: '❌' };
  toast.querySelector('.toast-icon').textContent = icons[level] || '✅';

  container.prepend(toast);
  toast.onclick = () => removeToast(toast);

  // Auto-remove after 6s
  setTimeout(() => removeToast(toast), 6000);
}

function removeToast(el) {
  if (!el || !el.parentNode) return;
  el.classList.add('toast-remove');
  setTimeout(() => el.remove(), 320);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ═══════════════════════════════════════════════════
// AGENT STATUS (side panel)
// ═══════════════════════════════════════════════════
function updateAgentUI(data) {
  const statusEl = document.getElementById('agent-status-text');
  const taskEl   = document.getElementById('agent-task');
  const dotEl    = document.getElementById('agent-dot');
  const progEl   = document.getElementById('progress-bar');
  const iconEl   = document.getElementById('agent-icon');

  statusEl.textContent = data.status || 'IDLE';
  statusEl.className   = 'agent-status ' + (data.status || 'idle').toLowerCase();
  dotEl.className      = 'agent-status-dot ' + (data.status || 'idle').toLowerCase();

  if (data.status === 'WORKING') {
    taskEl.textContent = `${data.current_task_emoji || '⚙'} ${data.current_task || ''}`;
    progEl.style.width = Math.round((data.progress || 0) * 100) + '%';
    iconEl.textContent = data.current_task_emoji || '🤖';
    document.getElementById('progress-wrap').style.display = '';
  } else {
    taskEl.textContent = data.status === 'DONE' ? 'Task complete! 🎉' : 'Waiting for work...';
    progEl.style.width = data.status === 'DONE' ? '100%' : '0%';
    iconEl.textContent = data.status === 'DONE' ? '✅' : '🤖';
    document.getElementById('progress-wrap').style.display =
      data.status === 'DONE' ? '' : 'none';
  }
}

// ═══════════════════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════════════════
let ws = null;

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    setConn('online', 'ONLINE');
    setInterval(() => ws.readyState === 1 && ws.send('ping'), 15000);
  };

  ws.onmessage = ({ data }) => {
    if (data === 'pong') return;
    let msg;
    try { msg = JSON.parse(data); } catch { return; }

    if (msg.type === 'agent_state') {
      updateAgentUI(msg);
      if (msg.status === 'WORKING') {
        addLog(`⚙ Agent: ${msg.current_task_emoji || ''} ${msg.current_task}`, 'log-agent');
      }
    }

    if (msg.type === 'notification') {
      showToast(msg);
      addLog(`🔔 ${msg.title} — ${msg.message}`, 'log-notif');
      // Grant bonus pts to player
      if (msg.bonus_pts > 0) {
        game.addAgentBonus(msg.bonus_pts);
        spawnScorePop(`🎁 +${msg.bonus_pts}`, '#00ff41');
      }
    }

    if (msg.type === 'do_trick') {
      game.requestTrick(msg.trick_id);
    }
  };

  ws.onclose = () => {
    setConn('offline', 'OFFLINE');
    setTimeout(connectWS, 3000);
  };
  ws.onerror = () => ws.close();
}

function setConn(cls, label) {
  document.getElementById('conn-dot').className = 'conn-dot ' + cls;
  document.getElementById('conn-label').textContent = label;
}

// ═══════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════
const game = new YoYoGame();
connectWS();

// Initial log
addLog('🪀 YoYo Dev ready! Press SPACE or click to play.', 'log-system');
addLog('🤖 AI agent starting up...', 'log-agent');
