# ==============================================================================
    # MELHORIA APLICADA: GRAVAÇÃO ACUMULATIVA + RESPEITO AOS DESCARTADOS DO COCKPIT
    # ==============================================================================
    ARQUIVO_JSON = "licitacoes.json"
    ARQUIVO_DESCARTADOS = "descartados.json"
    historico_existente = []
    ids_descartados = set()

    if os.path.exists(ARQUIVO_DESCARTADOS):
        try:
            with open(ARQUIVO_DESCARTADOS, "r", encoding="utf-8") as f:
                ids_descartados = set(json.load(f))
        except Exception:
            ids_descartados = set()

    if os.path.exists(ARQUIVO_JSON):
        try:
            with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
                historico_existente = json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao carregar historico local: {e}", flush=True)
            historico_existente = []

    # Mapa para mesclar itens sem duplicar pelo ID e ignorando os descartados
    mapa_licitacoes = {
        item["id"]: item
        for item in historico_existente
        if item["id"] not in ids_descartados
    }

    # Atualiza ou insere as novas oportunidades encontradas (se não estiverem descartadas)
    for op in oportunidades_novas:
        if op["id"] not in ids_descartados:
            mapa_licitacoes[op["id"]] = op

    # Filtro dinâmico: remove apenas os editais cuja data de encerramento já expirou
    agora = datetime.now()
    lista_final_acumulada = []

    for id_lic, item in mapa_licitacoes.items():
        dt_fim_str = item.get("data_fim") or ""
        edital_expirado = False

        if dt_fim_str:
            try:
                dt_fim_clean = str(dt_fim_str).replace("Z", "+00:00")
                dt_fim = datetime.fromisoformat(dt_fim_clean)
                dt_agora = datetime.now(dt_fim.tzinfo) if dt_fim.tzinfo else agora
                if dt_fim < dt_agora:
                    edital_expirado = True
            except Exception:
                pass

        if not edital_expirado:
            lista_final_acumulada.append(item)

    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(lista_final_acumulada, f, ensure_ascii=False, indent=4)

    print("\n==================================================================")
    print(f"✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"📌 Novas Oportunidades Encontradas Hoje: {len(oportunidades_novas)}")
    print(f"🏆 Total de Oportunidades Abertas Mantidas no Cockpit: {len(lista_final_acumulada)}")
    print("==================================================================")