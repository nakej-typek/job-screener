// ==UserScript==
// @name         WorkAtAStartup Screener
// @namespace    job-screener
// @version      0.1
// @description  Screen job postings through a self-hosted LLM screener
// @match        https://www.workatastartup.com/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      *            // <-- narrow this to your server's host
// ==/UserScript==

(function () {
    'use strict';

    // Where server.py is reachable. Same machine -> localhost;
    // a home server on the LAN or a VPN -> that host:port.
    const SERVER_HOST = 'localhost:8080';

    const SERVER = `http://${SERVER_HOST}/screen`;

    const btn = document.createElement('button');
    btn.textContent = '🔎 Screen';
    Object.assign(btn.style, {
        position: 'fixed', bottom: '20px', right: '20px', zIndex: 99999,
        padding: '10px 16px', background: '#ff6600', color: 'white',
        border: 'none', borderRadius: '6px', fontSize: '14px',
        fontWeight: 'bold', cursor: 'pointer',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    });
    document.body.appendChild(btn);

    const overlay = document.createElement('div');
    Object.assign(overlay.style, {
        position: 'fixed', top: '20px', right: '20px', width: '420px',
        maxHeight: '80vh', overflow: 'auto', zIndex: 99998,
        background: 'white', border: '2px solid #ff6600', borderRadius: '8px',
        padding: '16px', fontSize: '13px', lineHeight: '1.4',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)', display: 'none',
        fontFamily: 'system-ui, sans-serif',
    });
    document.body.appendChild(overlay);

    const show = (html) => { overlay.innerHTML = html; overlay.style.display = 'block'; };

    const renderVerdict = (v) => {
        if (v.error) return `<b>ERROR:</b> ${v.error}<br><pre>${(v.raw || '').slice(0, 500)}</pre>`;
        const color = { GO: '#0a0', MAYBE: '#d80', NO: '#c00', ERROR: '#999' }[v.verdict] || '#333';
        const list = (arr) => (arr || []).map(x => `<li>${x}</li>`).join('');
        return `
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:8px;">
                <span style="font-size:24px;font-weight:bold;color:${color};">${v.verdict} ${v.score ?? ''}/10</span>
                <span style="cursor:pointer;font-size:18px;" onclick="this.parentElement.parentElement.style.display='none'">✕</span>
            </div>
            <div><b>${v.company || '?'}</b> — ${v.role || '?'}</div>
            <div style="color:#666;margin:4px 0;">${v.location || '?'} · ${v.salary || 'plat n/a'}</div>
            <div style="margin:8px 0;font-style:italic;">${v.tldr || ''}</div>
            <div><b style="color:#0a0;">✓ Fit</b><ul style="margin:4px 0 8px 20px;padding:0;">${list(v.fit)}</ul></div>
            <div><b style="color:#d80;">⚠ Concerns</b><ul style="margin:4px 0 8px 20px;padding:0;">${list(v.concerns)}</ul></div>
            ${v.red_flags?.length ? `<div><b style="color:#c00;">🚩 Red flags</b><ul style="margin:4px 0 8px 20px;padding:0;">${list(v.red_flags)}</ul></div>` : ''}
            ${v.questions?.length ? `<div><b>❓ Otázky</b><ul style="margin:4px 0 8px 20px;padding:0;">${list(v.questions)}</ul></div>` : ''}
        `;
    };

    btn.addEventListener('click', () => {
        const text = document.body.innerText.trim();
        if (text.length < 100) { show('<b>Page too short.</b>'); return; }
        show('<b>⏳ Screening… (může trvat 20-60s)</b>');
        btn.disabled = true; btn.textContent = '⏳ ...';

        GM_xmlhttpRequest({
            method: 'POST',
            url: SERVER,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({ text, url: location.href }),
            timeout: 180000,
            onload: (res) => {
                btn.disabled = false; btn.textContent = '🔎 Screen';
                try { show(renderVerdict(JSON.parse(res.responseText))); }
                catch (e) { show(`<b>Parse error:</b> ${e}<br><pre>${res.responseText.slice(0, 500)}</pre>`); }
            },
            onerror: (e) => {
                btn.disabled = false; btn.textContent = '🔎 Screen';
                show(`<b>Network error.</b> Server běží na ${SERVER}? <br>${e.error || ''}`);
            },
            ontimeout: () => {
                btn.disabled = false; btn.textContent = '🔎 Screen';
                show('<b>Timeout.</b> Claude moc dlouho přemýšlel.');
            },
        });
    });
})();
