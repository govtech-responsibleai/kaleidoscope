import {useEffect, useRef, useState} from 'react';
import Head from '@docusaurus/Head';
import useBaseUrl from '@docusaurus/useBaseUrl';
import '../css/landing.css';

const FULL_TEXT = 'The chatbot should only provide accurate information.';
const TYPE_SPEED = 42;
const HOLD = 5450;

export default function Home() {
  const logoSrc = useBaseUrl('/img/kaleidoscope-logo-text-2.png');
  const docsUrl = useBaseUrl('/docs/getting-started/quickstart');
  const workflowLongSrc = useBaseUrl('/img/workflow_long.svg');
  const workflowTallSrc = useBaseUrl('/img/workflow_tall.svg');

  const typeTextRef = useRef<HTMLSpanElement>(null);
  const criteriaCardRef = useRef<HTMLDivElement>(null);
  const c1InnerRef = useRef<HTMLDivElement>(null);
  const testCardRef = useRef<HTMLDivElement>(null);
  const c2SplitRef = useRef<HTMLDivElement>(null);
  const scoreCardRef = useRef<HTMLDivElement>(null);
  const c3InnerRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [activeCard, setActiveCard] = useState(0);

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

    // Mobile card carousel
    const mql = window.matchMedia('(max-width: 640px)');
    let cardInterval: ReturnType<typeof setInterval> | null = null;
    function startCarousel() {
      if (mql.matches) {
        cardInterval = setInterval(() => {
          setActiveCard(prev => (prev + 1) % 3);
        }, 8000);
      }
    }
    function stopCarousel() {
      if (cardInterval) { clearInterval(cardInterval); cardInterval = null; }
    }
    function handleMqlChange() {
      stopCarousel();
      startCarousel();
    }
    startCarousel();
    mql.addEventListener('change', handleMqlChange);

    // Track scroll progress
    const container = document.getElementById('__docusaurus');
    function onScroll() {
      const y = container?.scrollTop || window.scrollY;
      setScrolled(y > 100);
      setScrollProgress(Math.min(y / 400, 1));
    }
    container?.addEventListener('scroll', onScroll);
    window.addEventListener('scroll', onScroll);

    return () => {
      timeouts.forEach(clearTimeout);
      observers.forEach(o => o.disconnect());
      container?.removeEventListener('scroll', onScroll);
      window.removeEventListener('scroll', onScroll);
      stopCarousel();
      mql.removeEventListener('change', handleMqlChange);
    };
  }, []);

  function handleCopyBibtex() {
    const bibtex = `@misc{kaleidoscope2026,
  title   = {Project {\\textsc{Kaleidoscope}}: Contextual, Human-Aligned
             Evaluation for Real-World AI Applications},
  author  = {{GovTech AI Practice}},
  year    = {2026},
  url     = {https://github.com/govtech-responsibleai/kaleidoscope}
}`;
    navigator.clipboard.writeText(bibtex);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <Head>
        <title>Kaleidoscope - AI evaluation, human aligned</title>
        <meta name="description" content="A structured workflow for realistic and scalable contextual AI evaluations." />
        <meta property="og:description" content="A structured workflow for realistic and scalable contextual AI evaluations." />
        <meta name="twitter:title" content="Kaleidoscope - AI evaluation, human aligned" />
        <meta name="twitter:description" content="A structured workflow for realistic and scalable contextual AI evaluations." />
        <link rel="icon" href="/kaleidoscope/img/favicon-color.ico" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap" rel="stylesheet" />
      </Head>

      <div className="bg-glow"></div>

      <main className="page">
        <div className="hero-viewport">
        {/* Section 1: Logo */}
        <div className="logo-lockup">
          <img src={logoSrc} alt="Project Kaleidoscope — Powered by GovTech Singapore" className="logo-combined" />
        </div>

        {/* Section 2: Tagline + Abstract + Pill Buttons */}
        <section className="abstract-section">
          <h1 className="hero-title">AI evaluation, human aligned.</h1>
          <div className="hero-divider"></div>
          <p className="abstract-text">
            Evals are the process of measuring the abilities of an AI system to understand and improve it. Functional, product-specific evaluations are challenging: public benchmarks don&rsquo;t reflect application context, human review workflows are tedious and prone to annotation fatigue and automation bias, and automated scoring is often hard to trust.
          </p>
          <p className="abstract-text">
            We introduce <strong>Kaleidoscope</strong>, an end-to-end workflow for contextual, functional evaluation, from evaluation set construction to human-aligned automated judging.
          </p>
          <div className="pill-buttons">
            <a href="#" className="pill-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/><path d="M9 17h6"/><path d="M9 13h6"/></svg>
              Paper
            </a>
            <a href="https://blog.ai.gov.sg/building-an-automated-evals-workflow-that-works-and-open-sourcing-it/" target="_blank" rel="noopener" className="pill-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 19a9 9 0 0 1 9 0a9 9 0 0 1 9 0"/><path d="M3 6a9 9 0 0 1 9 0a9 9 0 0 1 9 0"/><path d="M3 6v13"/><path d="M12 6v13"/><path d="M21 6v13"/></svg>
              Blog
            </a>
            <a href="https://github.com/govtech-responsibleai/kaleidoscope" target="_blank" rel="noopener" className="pill-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-4.3 1.4 -4.3 -2.5 -6 -3m12 5v-3.5c0 -1 .1 -1.4 -.5 -2c2.8 -.3 5.5 -1.4 5.5 -6a4.6 4.6 0 0 0 -1.3 -3.2a4.2 4.2 0 0 0 -.1 -3.2s-1.1 -.3 -3.5 1.3a12.3 12.3 0 0 0 -6.2 0c-2.4 -1.6 -3.5 -1.3 -3.5 -1.3a4.2 4.2 0 0 0 -.1 3.2a4.6 4.6 0 0 0 -1.3 3.2c0 4.6 2.7 5.7 5.5 6c-.6 .6 -.6 1.2 -.5 2v3.5"/></svg>
              GitHub
            </a>
            <a href={docsUrl} className="pill-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 13a8 8 0 0 1 7 7a6 6 0 0 0 3 -5a9 9 0 0 0 6 -8a3 3 0 0 0 -3 -3a9 9 0 0 0 -8 6a6 6 0 0 0 -5 3"/><path d="M7 14a6 6 0 0 0 -3 6a6 6 0 0 0 6 -3"/><circle cx="15" cy="9" r="1"/></svg>
              Getting Started
            </a>
          </div>
        </section>

        {/* Section 3: Animated Feature Cards */}
        <section className="animated-cards-section">
          <div className="feature-cards">
            {/* Card 1: Define Criteria */}
            <div className={`feat-wrapper ${activeCard === 0 ? 'card-active' : ''}`}>
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
            <div className={`feat-wrapper ${activeCard === 1 ? 'card-active' : ''}`}>
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
            <div className={`feat-wrapper ${activeCard === 2 ? 'card-active' : ''}`}>
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
          <div className="carousel-dots">
            {[0, 1, 2].map(i => (
              <button key={i} className={`carousel-dot ${activeCard === i ? 'active' : ''}`} onClick={() => setActiveCard(i)} aria-label={`Show card ${i + 1}`} />
            ))}
          </div>
        </section>

        {/* Scroll hint chevron */}
        <div className={`scroll-hint ${scrolled ? 'hidden' : ''}`}>
          <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        </div>{/* end .hero-viewport */}

        {/* Section 4: Sticky Nav */}
        <nav className="sticky-nav" style={{
          background: `rgba(30, 27, 75, ${scrollProgress})`,
        }}>
          <a href="#overview" className="sticky-nav-link" style={{ color: scrollProgress > 0.5 ? '#e2e8f0' : undefined }}>Overview</a>
          <a href="#features" className="sticky-nav-link" style={{ color: scrollProgress > 0.5 ? '#e2e8f0' : undefined }}>Features</a>
          <a href="#wog" className="sticky-nav-link" style={{ color: scrollProgress > 0.5 ? '#e2e8f0' : undefined }}>WOG</a>
        </nav>

        {/* Section 5: Overview */}
        <section className="overview-section" id="overview">
          <h2>Overview</h2>
          <p className="section-subtitle">How Kaleidoscope works</p>
          <img src={workflowLongSrc} alt="Kaleidoscope workflow diagram" className="overview-diagram overview-diagram-long" />
          <img src={workflowTallSrc} alt="Kaleidoscope workflow diagram" className="overview-diagram overview-diagram-tall" />
        </section>

        {/* Section 6: Key Features */}
        <section className="features-section" id="features">
          <h2>Key Features</h2>

          <div className="features-list">
            <div className="feature-item">
              <div className="feature-screenshot">
                <img src="/kaleidoscope/img/rubrics.png" alt="Custom rubrics interface" />
              </div>
              <div className="feature-desc">
                <h3>Define Custom Rubrics</h3>
                <p>Define evaluation criteria in natural language with guided workflows. Rubrics capture what &ldquo;good&rdquo; means for your specific AI product.</p>
              </div>
            </div>

            <div className="feature-item reverse">
              <div className="feature-screenshot offset-pair">
                <img src="/kaleidoscope/img/persona-1.png" alt="Persona generation" className="offset-back" />
                <img src="/kaleidoscope/img/persona-2.png" alt="Generated personas" className="offset-front" />
              </div>
              <div className="feature-desc">
                <h3>Generate Diverse Test Sets</h3>
                <p>Synthesise realistic, varied inputs using persona-driven generation. Cover edge cases and representative user archetypes automatically.</p>
              </div>
            </div>

            <div className="feature-item">
              <div className="feature-screenshot">
                <img src="/kaleidoscope/img/highlighter.png" alt="Annotation highlighting" />
              </div>
              <div className="feature-desc">
                <h3>Streamline Human Review</h3>
                <p>Purpose-built annotation and validation workflows designed to reduce reviewer fatigue while maintaining rigorous human oversight.</p>
              </div>
            </div>

            <div className="feature-item reverse">
              <div className="feature-screenshot stacked-pair">
                <img src="/kaleidoscope/img/scoring.png" alt="Scoring results" />
                <img src="/kaleidoscope/img/disagreement.png" alt="Judge disagreement analysis" />
              </div>
              <div className="feature-desc">
                <h3>Calibrate LLM Judges</h3>
                <p>Score responses with LLM judges calibrated against human annotations. Measure reliability and track alignment with human ground truth.</p>
              </div>
            </div>

            {/* TODO: uncomment when demo video is ready
            <div className="feature-video">
              <div className="video-placeholder">&#9654; Demo Video</div>
              <p className="video-caption">See Kaleidoscope in action</p>
            </div>
            */}
          </div>
        </section>

        {/* Section 7: WOG */}
        <section className="wog-section" id="wog">
          <div className="wog-mascots">
            <img src="/kaleidoscope/img/litmus_mascot.svg" alt="Litmus" className="wog-mascot" />
            <img src="/kaleidoscope/img/sentinel_mascot.svg" alt="Sentinel" className="wog-mascot" />
          </div>
          <h2>For Singapore Government Agencies</h2>
          <p className="wog-text">
            <a href="https://www.aiguardian.gov.sg/#litmus" target="_blank" rel="noopener">Litmus</a> is AI Guardian&rsquo;s testing and evaluation platform for Whole-of-Government AI products. We are extending Litmus to support Kaleidoscope&rsquo;s structured evaluation workflow in the upcoming months.
          </p>
          <a href="https://eval.ai-platform.string.sg/" target="_blank" rel="noopener" className="wog-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Indicate Interest
          </a>
        </section>

        {/* Section 8: Citation */}
        <section className="citation-section">
          <h2>Citation</h2>
          <div className="citation-block">
            <pre className="citation-code">{`@misc{kaleidoscope2026,
  title   = {Project {\\textsc{Kaleidoscope}}: Contextual, Human-Aligned
             Evaluation for Real-World AI Applications},
  author  = {{GovTech AI Practice}},
  year    = {2026},
  url     = {https://github.com/govtech-responsibleai/kaleidoscope}
}`}</pre>
            <button className="citation-copy-btn" onClick={handleCopyBibtex}>
              {copied ? (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  Copied
                </>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="12" rx="2" ry="2"/><path d="M16 8v-2a2 2 0 0 0 -2 -2h-8a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h2"/></svg>
                  Copy
                </>
              )}
            </button>
          </div>
        </section>
      </main>

      {/* Section 9: Footer */}
      <footer className="site-footer">
        <div className="footer-label">More like this</div>
        <div className="footer-links">
          <a href="https://blog.ai.gov.sg/" target="_blank" rel="noopener">Blog</a>
          <span className="footer-dot">&middot;</span>
          <a href="https://huggingface.co/govtech" target="_blank" rel="noopener">HuggingFace</a>
          <span className="footer-dot">&middot;</span>
          <a href="https://github.com/govtech-responsibleai" target="_blank" rel="noopener">GitHub</a>
        </div>
      </footer>
    </>
  );
}
