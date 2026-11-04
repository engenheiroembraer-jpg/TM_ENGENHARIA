// ==UserScript==
// @name         Robô Sniper TM Engenharia
// @namespace    http://tampermonkey.net/
// @version      2.3
// @description  Automação com Sincronização Bidirecional (Ativar/Desativar/Reativar)
// @match        *://*.pncp.gov.br/*
// @match        *://pncp.gov.br/*
// @match        *://*.compras.gov.br/*
// @match        *://*.comprasnet.gov.br/*
// @match        *://*.vercel.app/*
// @run-at       document-end
// @grant        GM_setValue
// @grant        GM_getValue
// ==/UserScript==

(function() {
    'use strict';

    const URL_ATUAL = window.location.href;
    const HOST_ATUAL = window.location.hostname;

    // Extrai identificador único do edital
    function extrairID(url) {
        if (!url) return '';
        const num = url.match(/\d+/g);
        return num ? num.join('') : '';
    }

    // 1. DENTRO DO DASHBOARD (VERCEL): Sincronização de ida e volta
    if (HOST_ATUAL.includes('vercel.app')) {
        function sincronizarComVercel() {
            const agendamentos = JSON.parse(localStorage.getItem('agendamentos_tm') || '[]');
            GM_setValue('lista_disputas_tm', JSON.stringify(agendamentos));
        }

        sincronizarComVercel();
        window.addEventListener('storage', sincronizarComVercel);
        setInterval(sincronizarComVercel, 2000);

        setInterval(() => {
            const comandoCancelar = GM_getValue('comando_cancelar_link', null);
            if (comandoCancelar) {
                let agendamentos = JSON.parse(localStorage.getItem('agendamentos_tm') || '[]');
                const idCancelar = extrairID(comandoCancelar);
                agendamentos = agendamentos.filter(item => !extrairID(item.link).includes(idCancelar) && !idCancelar.includes(extrairID(item.link)));
                localStorage.setItem('agendamentos_tm', JSON.stringify(agendamentos));
                GM_setValue('comando_cancelar_link', null);
                sincronizarComVercel();
            }
        }, 1000);

        return;
    }

    // 2. FUNÇÃO DE CANCELAMENTO PELO BANNER
    window.cancelarDisputaAtual = function(linkEdital) {
        let agendamentos = JSON.parse(GM_getValue('lista_disputas_tm', '[]'));
        const idAtual = extrairID(linkEdital);

        agendamentos = agendamentos.filter(item => {
            const idItem = extrairID(item.link);
            return !idAtual.includes(idItem) && !idItem.includes(idAtual);
        });
        GM_setValue('lista_disputas_tm', JSON.stringify(agendamentos));

        GM_setValue('comando_cancelar_link', linkEdital);

        const bannerExistente = document.getElementById('banner-robo-tm');
        if (bannerExistente) bannerExistente.remove();

        alert("❌ ROBÔ DESATIVADO!\n\nDisputa removida com sucesso. Você pode reativá-la no Dashboard a qualquer momento.");
    };

    // 3. MONITORAMENTO E INJEÇÃO NO PORTAL
    function verificarEInjetarBanner() {
        const agendamentos = JSON.parse(GM_getValue('lista_disputas_tm', '[]'));
        const bannerExistente = document.getElementById('banner-robo-tm');
        const idUrlAtual = extrairID(URL_ATUAL);

        if (!Array.isArray(agendamentos) || agendamentos.length === 0) {
            if (bannerExistente) bannerExistente.remove();
            return;
        }

        const disputaCorrespondente = agendamentos.find(item => {
            if (!item.link) return false;
            const idItem = extrairID(item.link);
            return (idItem.length > 5 && idUrlAtual.includes(idItem)) || URL_ATUAL.includes(item.link) || item.link.includes(URL_ATUAL);
        });

        if (!disputaCorrespondente || disputaCorrespondente.confirmarEntrada === "NAO") {
            if (bannerExistente) bannerExistente.remove();
            return;
        }

        if (!bannerExistente) {
            const banner = document.createElement('div');
            banner.id = 'banner-robo-tm';
            banner.style.cssText = "position: fixed !important; top: 15px !important; right: 15px !important; z-index: 999999999 !important; background: #0f172a !important; color: #10b981 !important; border: 2px solid #10b981 !important; padding: 12px 18px !important; border-radius: 12px !important; font-family: sans-serif !important; font-size: 12px !important; font-weight: bold !important; box-shadow: 0 10px 25px rgba(0,0,0,0.6) !important; display: flex !important; flex-direction: column !important; gap: 8px !important;";
            
            banner.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="height:10px; width:10px; background:#10b981; border-radius:50%; display:inline-block; box-shadow:0 0 8px #10b981;"></span>
                        <span>🚀 ROBÔ TM ENGENHARIA CONECTADO</span>
                    </div>
                </div>
                <div style="color:#f97316; font-size:11px;">
                    Teto P26: ${disputaCorrespondente.valorTeto || 'R$ 0,00'} | Modo: ${disputaCorrespondente.estrategia || 'SNIPER'}
                </div>
                <button id="btn-cancelar-tm-robo" style="background: #ef4444 !important; color: white !important; border: none !important; padding: 6px 10px !important; border-radius: 6px !important; font-size: 11px !important; font-weight: bold !important; cursor: pointer !important; margin-top: 4px !important; transition: 0.2s;">
                    🚫 DESATIVAR ROBÔ DESTE EDITAL
                </button>
            `;
            document.body.appendChild(banner);

            document.getElementById('btn-cancelar-tm-robo').onclick = function() {
                window.cancelarDisputaAtual(disputaCorrespondente.link || URL_ATUAL);
            };
        }
    }

    setInterval(() => {
        if (document.body) {
            verificarEInjetarBanner();
        }
    }, 1000);
})();
