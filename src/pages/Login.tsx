import { useState, useEffect } from "react";
import { supabase } from '../lib/supabase'

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogin = async () => {
    if (!email || !password) {
      setError("Please enter your credentials.");
      return;
    }
    setLoading(true);
    setError("");
    const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
    if (authError) {
      setError(authError.message || "Login failed. Please try again.");
    } else {
      window.location.href = "/dashboard";
    }
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleLogin();
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Exo+2:wght@300;400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          background: #020810;
          font-family: 'Exo 2', sans-serif;
          overflow: hidden;
        }

        .scene {
          width: 100vw;
          height: 100vh;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          perspective: 1200px;
          background: radial-gradient(ellipse 80% 60% at 50% 40%, #0a1628 0%, #020810 70%);
        }

        /* Animated grid floor */
        .grid-floor {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(0, 120, 255, 0.07) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 120, 255, 0.07) 1px, transparent 1px);
          background-size: 60px 60px;
          transform: perspective(800px) rotateX(60deg) translateY(30%) scaleX(2.5);
          transform-origin: center bottom;
          mask-image: linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.5) 30%, black 60%, transparent 100%);
          animation: gridScroll 8s linear infinite;
        }

        @keyframes gridScroll {
          0% { background-position: 0 0; }
          100% { background-position: 0 60px; }
        }

        /* Floating orbs */
        .orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          animation: orbFloat 10s ease-in-out infinite;
          pointer-events: none;
        }
        .orb-1 {
          width: 500px; height: 500px;
          background: radial-gradient(circle, rgba(0, 80, 255, 0.15) 0%, transparent 70%);
          top: -100px; left: -100px;
          animation-delay: 0s;
        }
        .orb-2 {
          width: 400px; height: 400px;
          background: radial-gradient(circle, rgba(0, 200, 255, 0.1) 0%, transparent 70%);
          bottom: -80px; right: -80px;
          animation-delay: -5s;
        }
        .orb-3 {
          width: 300px; height: 300px;
          background: radial-gradient(circle, rgba(100, 0, 255, 0.08) 0%, transparent 70%);
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          animation-delay: -3s;
        }

        @keyframes orbFloat {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(20px, -20px) scale(1.05); }
          66% { transform: translate(-15px, 15px) scale(0.97); }
        }

        /* Scan lines */
        .scanlines {
          position: absolute;
          inset: 0;
          background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 0, 0, 0.03) 2px,
            rgba(0, 0, 0, 0.03) 4px
          );
          pointer-events: none;
          z-index: 100;
        }

        /* Corner decorations */
        .corner {
          position: absolute;
          width: 20px; height: 20px;
          border-color: rgba(0, 140, 255, 0.6);
          border-style: solid;
        }
        .corner-tl { top: 12px; left: 12px; border-width: 2px 0 0 2px; }
        .corner-tr { top: 12px; right: 12px; border-width: 2px 2px 0 0; }
        .corner-bl { bottom: 12px; left: 12px; border-width: 0 0 2px 2px; }
        .corner-br { bottom: 12px; right: 12px; border-width: 0 2px 2px 0; }

        /* Main card */
        .card-wrap {
          position: relative;
          z-index: 10;
          transform-style: preserve-3d;
          animation: cardEntrance 0.9s cubic-bezier(0.22, 1, 0.36, 1) forwards;
          opacity: 0;
        }

        @keyframes cardEntrance {
          0% { opacity: 0; transform: translateY(60px) rotateX(20deg) scale(0.92); }
          100% { opacity: 1; transform: translateY(0) rotateX(0deg) scale(1); }
        }

        .card {
          width: 460px;
          background: linear-gradient(145deg, rgba(12, 24, 50, 0.95) 0%, rgba(6, 14, 32, 0.98) 100%);
          border: 1px solid rgba(0, 120, 255, 0.25);
          border-radius: 20px;
          padding: 44px 44px 40px;
          position: relative;
          box-shadow:
            0 0 0 1px rgba(0, 80, 255, 0.08),
            0 40px 80px rgba(0, 0, 0, 0.6),
            0 0 60px rgba(0, 80, 255, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.06),
            inset 0 0 80px rgba(0, 40, 120, 0.05);
          backdrop-filter: blur(20px);
        }

        /* Top glint line */
        .card::before {
          content: '';
          position: absolute;
          top: 0; left: 20%; right: 20%;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(100, 180, 255, 0.6), transparent);
          border-radius: 50%;
        }

        /* Animated top accent line */
        .card-accent {
          position: absolute;
          top: -1px; left: 30%; right: 30%;
          height: 2px;
          background: linear-gradient(90deg, transparent, #0078ff, #00d4ff, #0078ff, transparent);
          border-radius: 2px;
          animation: accentPulse 3s ease-in-out infinite;
        }

        @keyframes accentPulse {
          0%, 100% { opacity: 0.7; transform: scaleX(1); }
          50% { opacity: 1; transform: scaleX(1.2); }
        }

        /* Logo section */
        .logo-section {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-bottom: 32px;
          gap: 14px;
        }

        .logo-container {
          position: relative;
          width: 72px; height: 72px;
          display: flex; align-items: center; justify-content: center;
        }

        .logo-ring {
          position: absolute;
          inset: -8px;
          border-radius: 50%;
          border: 1px solid rgba(0, 120, 255, 0.3);
          animation: ringRotate 8s linear infinite;
        }

        .logo-ring::before {
          content: '';
          position: absolute;
          top: -2px; left: 50%;
          width: 4px; height: 4px;
          background: #0078ff;
          border-radius: 50%;
          transform: translateX(-50%);
          box-shadow: 0 0 8px #0078ff;
        }

        @keyframes ringRotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .logo-img {
          width: 60px; height: 60px;
          border-radius: 14px;
          object-fit: contain;
          background: white;
          padding: 6px;
          box-shadow: 0 0 20px rgba(0, 120, 255, 0.25), 0 8px 24px rgba(0,0,0,0.4);
        }

        .logo-placeholder {
          width: 60px; height: 60px;
          border-radius: 14px;
          background: linear-gradient(135deg, #0050cc, #0090ff);
          display: flex; align-items: center; justify-content: center;
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 22px;
          color: white;
          letter-spacing: 1px;
          box-shadow: 0 0 20px rgba(0, 120, 255, 0.4), 0 8px 24px rgba(0,0,0,0.4);
        }

        .card-title {
          font-family: 'Rajdhani', sans-serif;
          font-size: 20px;
          font-weight: 700;
          color: #e8f0ff;
          letter-spacing: 2px;
          text-transform: uppercase;
          text-align: center;
          line-height: 1.3;
        }

        .card-title span {
          display: block;
          font-size: 11px;
          font-weight: 500;
          color: rgba(100, 160, 255, 0.7);
          letter-spacing: 3px;
          margin-top: 4px;
        }

        /* Divider */
        .divider {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 28px;
        }
        .divider-line {
          flex: 1;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(0, 100, 255, 0.3), transparent);
        }
        .divider-dot {
          width: 4px; height: 4px;
          border-radius: 50%;
          background: rgba(0, 120, 255, 0.5);
        }

        /* Input fields */
        .field {
          margin-bottom: 18px;
          position: relative;
        }

        .field label {
          display: block;
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: rgba(100, 160, 255, 0.7);
          margin-bottom: 8px;
          font-family: 'Rajdhani', sans-serif;
        }

        .input-wrap {
          position: relative;
        }

        .input-icon {
          position: absolute;
          left: 14px; top: 50%;
          transform: translateY(-50%);
          color: rgba(0, 120, 255, 0.5);
          pointer-events: none;
        }

        .input-field {
          width: 100%;
          background: rgba(0, 20, 60, 0.6);
          border: 1px solid rgba(0, 80, 200, 0.25);
          border-radius: 10px;
          padding: 13px 14px 13px 42px;
          color: #d0e4ff;
          font-family: 'Exo 2', sans-serif;
          font-size: 14px;
          outline: none;
          transition: all 0.25s ease;
          box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3), 0 0 0 0 transparent;
        }

        .input-field::placeholder {
          color: rgba(80, 120, 200, 0.35);
        }

        .input-field:focus {
          border-color: rgba(0, 140, 255, 0.6);
          background: rgba(0, 25, 70, 0.8);
          box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3), 0 0 0 3px rgba(0, 100, 255, 0.1), 0 0 20px rgba(0, 100, 255, 0.08);
          color: #e8f4ff;
        }

        .toggle-pass {
          position: absolute;
          right: 14px; top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          color: rgba(0, 120, 255, 0.4);
          cursor: pointer;
          padding: 2px;
          transition: color 0.2s;
          display: flex; align-items: center;
        }
        .toggle-pass:hover { color: rgba(0, 160, 255, 0.8); }

        /* Error */
        .error-msg {
          background: rgba(255, 40, 40, 0.08);
          border: 1px solid rgba(255, 60, 60, 0.25);
          border-radius: 8px;
          padding: 10px 14px;
          font-size: 12px;
          color: #ff8080;
          margin-bottom: 18px;
          display: flex;
          align-items: center;
          gap: 8px;
          animation: errorShake 0.3s ease;
        }

        @keyframes errorShake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          75% { transform: translateX(6px); }
        }

        /* Login button */
        .login-btn {
          width: 100%;
          padding: 15px;
          background: linear-gradient(135deg, #0050cc 0%, #0078ff 50%, #00aaff 100%);
          border: none;
          border-radius: 10px;
          color: white;
          font-family: 'Rajdhani', sans-serif;
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 3px;
          text-transform: uppercase;
          cursor: pointer;
          position: relative;
          overflow: hidden;
          transition: all 0.3s ease;
          box-shadow: 0 4px 20px rgba(0, 100, 255, 0.35), 0 1px 0 rgba(255,255,255,0.1) inset;
        }

        .login-btn::before {
          content: '';
          position: absolute;
          top: 0; left: -100%;
          width: 100%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
          transition: left 0.5s ease;
        }

        .login-btn:hover::before { left: 100%; }

        .login-btn:hover {
          box-shadow: 0 6px 30px rgba(0, 120, 255, 0.5), 0 1px 0 rgba(255,255,255,0.1) inset;
          transform: translateY(-1px);
        }

        .login-btn:active { transform: translateY(1px); }

        .login-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
          transform: none;
        }

        .btn-loader {
          display: inline-flex;
          align-items: center;
          gap: 10px;
        }

        .spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Footer */
        .card-footer {
          margin-top: 24px;
          text-align: center;
          font-size: 11px;
          color: rgba(60, 100, 180, 0.5);
          letter-spacing: 1px;
          font-family: 'Rajdhani', sans-serif;
          font-weight: 500;
        }

        .card-footer strong {
          color: rgba(0, 120, 255, 0.6);
        }

        /* HUD elements */
        .hud-top {
          position: absolute;
          top: 24px; left: 50%; transform: translateX(-50%);
          display: flex; align-items: center; gap: 8px;
          font-family: 'Rajdhani', sans-serif;
          font-size: 10px;
          letter-spacing: 3px;
          color: rgba(0, 120, 255, 0.35);
          text-transform: uppercase;
          white-space: nowrap;
        }

        .hud-dot {
          width: 5px; height: 5px; border-radius: 50%;
          background: rgba(0, 180, 80, 0.7);
          box-shadow: 0 0 6px rgba(0, 200, 80, 0.5);
          animation: blink 2s ease-in-out infinite;
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        .hud-bottom {
          position: absolute;
          bottom: 24px; left: 50%; transform: translateX(-50%);
          font-family: 'Rajdhani', sans-serif;
          font-size: 9px;
          letter-spacing: 4px;
          color: rgba(0, 80, 180, 0.3);
          text-transform: uppercase;
          white-space: nowrap;
        }

        /* Particle dots */
        .particles {
          position: absolute;
          inset: 0;
          pointer-events: none;
          overflow: hidden;
        }

        .particle {
          position: absolute;
          width: 2px; height: 2px;
          background: rgba(0, 140, 255, 0.5);
          border-radius: 50%;
          animation: particleRise linear infinite;
        }

        @keyframes particleRise {
          0% { transform: translateY(100vh) translateX(0); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(-10vh) translateX(var(--drift)); opacity: 0; }
        }
      `}</style>

      <div className="scene">
        <div className="grid-floor" />
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
        <div className="scanlines" />

        {/* Particles */}
        <div className="particles">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="particle"
              style={{
                left: `${Math.random() * 100}%`,
                animationDuration: `${6 + Math.random() * 10}s`,
                animationDelay: `${Math.random() * 10}s`,
                ["--drift" as string]: `${(Math.random() - 0.5) * 100}px`,
                width: Math.random() > 0.7 ? "3px" : "2px",
                height: Math.random() > 0.7 ? "3px" : "2px",
              }}
            />
          ))}
        </div>

        {/* Corner decorations */}
        <div className="corner corner-tl" />
        <div className="corner corner-tr" />
        <div className="corner corner-bl" />
        <div className="corner corner-br" />

        {/* HUD */}
        <div className="hud-top">
          <div className="hud-dot" />
          Secure Access Portal · v2.4
        </div>
        <div className="hud-bottom">
          Absstem Technologies · Tender Intelligence Platform
        </div>

        {mounted && (
          <div className="card-wrap">
            <div className="card">
              <div className="card-accent" />

              <div className="logo-section">
                <div className="logo-container">
                  <div className="logo-ring" />
                  <img
                    src="https://absstem.com/wp-content/uploads/2022/05/Absstem_logo-1.png"
                    alt="Absstem"
                    className="logo-img"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                      const el = document.createElement("div");
                      el.className = "logo-placeholder";
                      el.textContent = "AB";
                      (e.target as HTMLImageElement).parentNode?.appendChild(el);
                    }}
                  />
                </div>
                <div className="card-title">
                  Absstem Tender Monitoring System
                  <span>Authorized Access Only</span>
                </div>
              </div>

              <div className="divider">
                <div className="divider-line" />
                <div className="divider-dot" />
                <div className="divider-line" />
              </div>

              <div className="field">
                <label>Email Address</label>
                <div className="input-wrap">
                  <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="2" y="4" width="20" height="16" rx="2" />
                    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                  </svg>
                  <input
                    type="email"
                    className="input-field"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="email"
                  />
                </div>
              </div>

              <div className="field">
                <label>Password</label>
                <div className="input-wrap">
                  <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <input
                    type={showPass ? "text" : "password"}
                    className="input-field"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="current-password"
                  />
                  <button className="toggle-pass" onClick={() => setShowPass(!showPass)} type="button">
                    {showPass ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {error && (
                <div className="error-msg">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  {error}
                </div>
              )}

              <button className="login-btn" onClick={handleLogin} disabled={loading}>
                {loading ? (
                  <span className="btn-loader">
                    <span className="spinner" />
                    Authenticating...
                  </span>
                ) : (
                  "Sign In"
                )}
              </button>

              <div className="card-footer">
                Access restricted to <strong>authorized personnel</strong> only
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}