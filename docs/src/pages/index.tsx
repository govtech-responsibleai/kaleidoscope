import {useEffect, useRef} from 'react';
import Head from '@docusaurus/Head';
import useBaseUrl from '@docusaurus/useBaseUrl';
import '../css/landing.css';

const FULL_TEXT = 'The chatbot should only provide accurate information.';
const TYPE_SPEED = 42;
const HOLD = 5450;

export default function Home() {
  const logoSrc = useBaseUrl('/img/kaleidoscope-logo-text-2.png');
  const docsUrl = useBaseUrl('/docs/getting-started/quickstart');

  const typeTextRef = useRef<HTMLSpanElement>(null);
  const criteriaCardRef = useRef<HTMLDivElement>(null);
  const c1InnerRef = useRef<HTMLDivElement>(null);
  const testCardRef = useRef<HTMLDivElement>(null);
  const c2SplitRef = useRef<HTMLDivElement>(null);
  const scoreCardRef = useRef<HTMLDivElement>(null);
  const c3InnerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const observers: ResizeObserver[] = [];

    // Typewriter
    const el = typeTextRef.current;
    if (el) {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        el.textContent = FULL_TEXT;
      } else {
        function type(i: number) {
          if (!el) return;
          el.textContent = FULL_TEXT.slice(0, i);
          if (i < FULL_TEXT.length) {
            timeouts.push(setTimeout(() => type(i + 1), TYPE_SPEED));
          } else {
            timeouts.push(setTimeout(() => {
              el.textContent = '';
              timeouts.push(setTimeout(() => type(1), 240));
            }, HOLD));
          }
        }
        type(1);
      }
    }

    // Card 1 scaling
    const card1 = criteriaCardRef.current;
    const inner1 = c1InnerRef.current;
    if (card1 && inner1) {
      let naturalH = 0;
      function scale1() {
        if (!naturalH) naturalH = inner1!.scrollHeight;
        const available = card1!.getBoundingClientRect().height - 36;
        const s = Math.min(1, available / naturalH);
        inner1!.style.transform = 'scale(' + s.toFixed(3) + ')';
      }
      const ro1 = new ResizeObserver(scale1);
      ro1.observe(card1);
      observers.push(ro1);
      scale1();
    }

    // Card 2 scaling
    const card2 = testCardRef.current;
    const inner2 = c2SplitRef.current;
    if (card2 && inner2) {
      const REF_H = 180;
      function scale2() {
        const h = card2!.getBoundingClientRect().height;
        const s = Math.min(1, h / REF_H);
        if (s < 1) {
          inner2!.style.transform = 'scale(' + s.toFixed(3) + ')';
          inner2!.style.width = (100 / s).toFixed(1) + '%';
          inner2!.style.height = (100 / s).toFixed(1) + '%';
        } else {
          inner2!.style.transform = '';
          inner2!.style.width = '100%';
          inner2!.style.height = '100%';
        }
      }
      const ro2 = new ResizeObserver(scale2);
      ro2.observe(card2);
      observers.push(ro2);
      scale2();
    }

    // Card 3 scaling
    const card3 = scoreCardRef.current;
    const inner3 = c3InnerRef.current;
    if (card3 && inner3) {
      let naturalH = 0;
      function scale3() {
        if (!naturalH) naturalH = inner3!.scrollHeight;
        const available = card3!.getBoundingClientRect().height - 36;
        const s = Math.min(1, available / naturalH);
        const offsetY = Math.max(0, (available - naturalH * s) / 2);
        inner3!.style.transform = 'translateY(' + offsetY.toFixed(1) + 'px) scale(' + s.toFixed(3) + ')';
      }
      const ro3 = new ResizeObserver(scale3);
      ro3.observe(card3);
      observers.push(ro3);
      scale3();
    }

    return () => {
      timeouts.forEach(clearTimeout);
      observers.forEach(o => o.disconnect());
    };
  }, []);

  return (
    <>
      <Head>
        <title>Project Kaleidoscope</title>
        <meta name="description" content="Automated evaluation platform for AI-powered applications" />
        <link rel="icon" href="/kaleidoscope/img/favicon-color.ico" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap" rel="stylesheet" />
      </Head>

      <div className="bg-glow"></div>

      <main className="page">
        <div className="logo-lockup">
          <img src={logoSrc} alt="Project Kaleidoscope — Powered by GovTech Singapore" className="logo-combined" />
        </div>

        <div className="content">
          <div className="hero-row">
            <div className="feature-text">
              <h1>AI evaluation, human aligned.</h1>
              <div className="feature-divider"></div>
              <p className="feature-subhead">Build automated evals that stay grounded in human judgement.</p>
            </div>

            <div className="feature-cards">
              {/* Card 1: Define Criteria */}
              <div className="feat-wrapper">
                <div className="feat-card" ref={criteriaCardRef}>
                  <div className="feat-card-preview">
                    <div ref={c1InnerRef}>
                      <div className="mini-label-row">Evaluation criteria</div>
                      <div className="mini-input-wrap">
                        <span ref={typeTextRef}></span><span className="mini-cursor"></span>
                        <div className="mini-save-btn">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                        </div>
                      </div>
                      <div className="mini-celebration">
                        <svg className="celebration-check" width="36" height="36" viewBox="0 0 36 36">
                          <circle cx="18" cy="18" r="15" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeDasharray="94.25" strokeDashoffset="94.25"/>
                          <polyline points="11,18 16,23 25,13" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="22" strokeDashoffset="22"/>
                        </svg>
                        <span className="celebration-text">Added Accuracy metric!</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="feat-label">
                  <span>Define Criteria</span>
                  <small>Set up custom criteria in natural language.</small>
                </div>
              </div>

              {/* Card 2: Test Inputs */}
              <div className="feat-wrapper">
                <div className="feat-card" ref={testCardRef}>
                  <div className="feat-card-preview c2-preview">
                    <div className="c2-split" ref={c2SplitRef}>
                      <div className="c2-chat-col">
                        <div className="c2-user-area">
                          <div className="c2-bubble-bg user-bg"></div>
                          <div className="c2-sparkles">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z"/>
                            </svg>
                          </div>
                          <div className="c2-user-bubble">
                            <div className="c2-bubble">How do I apply for leave?</div>
                          </div>
                        </div>
                        <div className="c2-ai-area">
                          <div className="c2-bubble-bg ai-bg"></div>
                          <div className="c2-typing">
                            <div className="c2-dot"></div><div className="c2-dot"></div><div className="c2-dot"></div>
                          </div>
                          <div className="c2-ai-bubble">
                            <div className="c2-bubble">You can apply via the company portal in the &quot;Leaves&quot; section.</div>
                          </div>
                        </div>
                      </div>
                      <div className="c2-annot-col">
                        <div className="c2-annot-head">Annotate</div>
                        <div className="c2-annot-row">
                          <span>Accurate?</span>
                          <div className="c2-btn-grp">
                            <span className="c2-btn c2-btn-acc-y">Y</span>
                            <span className="c2-btn">N</span>
                          </div>
                        </div>
                        <div className="c2-annot-row">
                          <span>Relevant?</span>
                          <div className="c2-btn-grp">
                            <span className="c2-btn">Y</span>
                            <span className="c2-btn c2-btn-rel-n">N</span>
                          </div>
                        </div>
                        <div className="c2-annot-row">
                          <span>Safe?</span>
                          <div className="c2-btn-grp">
                            <span className="c2-btn c2-btn-saf-y">Y</span>
                            <span className="c2-btn">N</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="feat-label">
                  <span>Generate and Test Inputs</span>
                  <small>Create diverse and realistic inputs that probe your AI.</small>
                </div>
              </div>

              {/* Card 3: Score */}
              <div className="feat-wrapper">
                <div className="feat-card" ref={scoreCardRef}>
                  <div className="feat-card-preview">
                    <div className="mini-scoring-loader">
                      <div className="mini-spinner"></div>
                      <div className="mini-scoring-text">Scoring…</div>
                    </div>
                    <div className="mini-metrics">
                      <div ref={c3InnerRef}>
                        <div className="mini-metric-row metric-row-acc">
                          <div className="mini-metric-label">Accuracy</div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Score</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill score fill-acc-score"></div></div>
                            <span className="mini-bar-val">82%</span>
                          </div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Reliability</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill reliability fill-acc-rel"></div></div>
                            <span className="mini-bar-val">88%</span>
                          </div>
                        </div>
                        <div className="mini-metric-row metric-row-rel">
                          <div className="mini-metric-label">Relevance</div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Score</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill score fill-rel-score"></div></div>
                            <span className="mini-bar-val">71%</span>
                          </div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Reliability</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill reliability fill-rel-rel"></div></div>
                            <span className="mini-bar-val">79%</span>
                          </div>
                        </div>
                        <div className="mini-metric-row metric-row-saf">
                          <div className="mini-metric-label">Safety</div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Score</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill score fill-saf-score"></div></div>
                            <span className="mini-bar-val">90%</span>
                          </div>
                          <div className="mini-bar-row">
                            <span className="mini-bar-name">Reliability</span>
                            <div className="mini-bar-track"><div className="mini-bar-fill reliability fill-saf-rel"></div></div>
                            <span className="mini-bar-val">95%</span>
                          </div>
                        </div>
                        <div className="mini-chart">
                          <svg className="mini-chart-svg" width="100%" viewBox="0 0 116 55">
                            <defs>
                              <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#7c3aed"/>
                                <stop offset="100%" stopColor="#ba2fa2"/>
                              </linearGradient>
                            </defs>
                            <line x1="5" y1="44" x2="111" y2="44" stroke="#e2e8f0" strokeWidth="0.5"/>
                            <rect className="chart-bar bar-1" x="10" y="22" width="16" height="22" rx="2" fill="url(#barGrad)"/>
                            <rect className="chart-bar bar-2" x="30" y="18" width="16" height="26" rx="2" fill="url(#barGrad)"/>
                            <rect className="chart-bar bar-3" x="50" y="15" width="16" height="29" rx="2" fill="url(#barGrad)"/>
                            <rect className="chart-bar bar-4" x="70" y="13" width="16" height="31" rx="2" fill="url(#barGrad)"/>
                            <rect className="chart-bar bar-5" x="90" y="11" width="16" height="33" rx="2" fill="url(#barGrad)"/>
                            <text x="18" y="52" textAnchor="middle" className="chart-label">v1</text>
                            <text x="38" y="52" textAnchor="middle" className="chart-label">v2</text>
                            <text x="58" y="52" textAnchor="middle" className="chart-label">v3</text>
                            <text x="78" y="52" textAnchor="middle" className="chart-label">v4</text>
                            <text x="98" y="52" textAnchor="middle" className="chart-label">v5</text>
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="feat-label">
                  <span>Automated Scoring</span>
                  <small>Score responses with reliable judges.</small>
                </div>
              </div>
            </div>
          </div>

          {/* Destination cards */}
          <div className="dest-cards">
            <div className="dest-card">
              <div>
                <h3>Prototype &amp; Docs</h3>
                <p>Explore the framework, read the docs, or contribute on GitHub.</p>
              </div>
              <div className="dest-btns">
                <a href={docsUrl} className="dest-btn white">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                  What is Kaleidoscope?
                </a>
                <a href="https://github.com/govtech-responsibleai/kaleidoscope" target="_blank" rel="noopener" className="dest-btn black">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
                  View on GitHub
                </a>
              </div>
            </div>

            <div className="dest-card">
              <div>
                <h3>WOG Evaluation Platform</h3>
                <p>The managed evaluation platform for Singapore Government agencies.</p>
              </div>
              <div className="dest-btns">
                <a href="https://eval.ai-platform.string.sg/" target="_blank" rel="noopener" className="dest-btn purple">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                  Indicate your interest
                </a>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="site-footer">
        <p>&copy; 2026 Project Kaleidoscope &middot; GovTech Singapore &middot; AI Practice</p>
      </footer>
    </>
  );
}
