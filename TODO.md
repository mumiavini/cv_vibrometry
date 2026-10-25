# TODO — fechamento do TCC (resultados, validação e texto)

Estado em 2026-10-25. Itens marcados `[ ]` abertos, `[x]` feitos.
Ordem sugerida: **A → B → C → D**. Dados e decisões (A) destravam tudo.

## Tese (mensagem central)

> Um **smartphone em slow motion** (rolling shutter, sem controle de exposição)
> mede a frequência natural com concordância aceitável com o acelerômetro e com
> o modelo analítico, **sem contato e sem mass loading**. Limitações
> (rolling shutter, fps do slow-mo, flicker, ausência do sinal bruto do
> acelerômetro) são **quantificadas e discutidas**, não escondidas.

---

## Estado atual (2026-10-25) — o que já existe e o que a primeira análise mostrou

**Já feito (em `main`):** aplicativo (`vibroapp`, 6 etapas), núcleo `vibrometry` (rastreamento por fase,
sincronismo, integração do acelerômetro, lote, relatório LaTeX), modelos analíticos da barra com mola e
raiz articulada (`BeamFE`), referência do acelerômetro digitalizada, primeira sessão real
(`Code/sessions/k1_cm_acc.vibro.json`, iPhone 17e, 240 fps, mola k₁), 67 testes. Ferramentas de análise da
sessão em `Code/tools/` (comparação de métodos E1, forma modal multiponto E5, incerteza B2/E2), resultados em
`Code/sessions/k1_cm_acc_resultados/{comparacao_metodos,forma_modal,incerteza}/`.

**Primeira análise (vídeo `k1_cm_acc.mov`, ROI no acelerômetro, escala corrigida 0,513 mm/px):**

| Resultado | Valor | Observação |
|---|---|---|
| f_n vídeo | 7,763 Hz (estável de 1 a 7,5 s) | PULSE: 7,600 Hz → +2,1 % (critério do app: 1 %); takes diferentes |
| amplitude no acelerômetro | 7,58 mm → ω²·A ≈ 18 m/s² | concorda com a envoltória do PULSE (17–19 m/s²) |
| razão de amplitudes parafuso/acelerômetro | 2,045 | forma modal do `BeamFE` (articulada + mola k₁ + massa efetiva 383 g): 2,079 → −1,7 % |
| ζ vídeo (envoltória) | ≈ 0,0010 (σ = 0,049 1/s) | PULSE: ≈ 0,0072 (σ = 0,345 1/s) → **não concorda (×7)** |
| fase/forma de onda vídeo × acelerômetro | sem sentido | takes diferentes (20:22:39 × 20:48:57) e CSV não é forma de onda |

**Problemas encontrados e corrigidos/registrados** (detalhes em `issues.md`): escala 7,2× errada na sessão,
`f_analysis = 0,79 Hz`, metadados de régua de aço; CSV do acelerômetro é um traço em zigue-zague; vídeo e PULSE
não são o mesmo ensaio; o app ainda prevê f₁ com viga engastada; vídeo de 91 MB no git.

**Próximos passos (ordem):**
1. **Ir ao laboratório** (roteiro em `docs/roteiro_laboratorio.md`): medir k das molas (estático) e pesar as ferragens; **gravar vídeo e PULSE ao mesmo tempo** (impacto + LED), mola k₁ e k₂, 3 repetições cada; anotar a posição
   da lâmina do amortecedor e se há pré-carga na mola. Sem isso, ζ e fase não fecham.
2. Explicar a diferença de amortecimento (ζ vídeo ≈ 0,001 × PULSE ≈ 0,007) e de f_n (+2,1 %).
3. ~~Integrar `BeamFE` ao app~~ — feito (etapa 1: apoio, molas, massas; etapa 2: posição das ROIs; etapa 6: forma modal). Falta **preencher na sessão as massas pesadas** da mola k₁, parafuso, porcas e gancho (hoje 0 → f₁ previsto 11,7 Hz).
4. Exportar os dados brutos do PULSE (hoje só há foto/digitalização) ou manter a digitalização rotulada.
5. Texto do TCC (seção D) com a tabela acima como esqueleto de resultados.

---

## ⚠ Discrepância modelo × medição (resolver antes de escrever resultados)

Confirmado: raiz = **junta com mancal (articulada)**, alumínio 6351-T6, 660 g, molas de
catálogo k₁ = 1500 e k₂ = 2500 N/m, acelerômetro 5 g a 300 mm do engaste, mola a 632 mm
do engaste (furo de 88 mm da ponta). Pico do acelerômetro: **7,600 Hz**.

**Não separável com os dados atuais (k × massa):** os 7,6 Hz só dizem que k_total/m_efetiva é o do ajuste; as
massas pesadas da mola/ferragens não foram registradas (o "383 g" é o valor *necessário* com k = 1500 N/m, não
uma medida). Com f₁ = 7,60 Hz: k = 1500 N/m exige ≈ 383 g de massa efetiva no ponto da mola; k = 1000 → ≈ 162 g;
k = 630 → 0 g. A mola 2 (nominal 2500 N/m) **não** distingue as hipóteses (≈ 9,8 Hz em ambas). Resolver
medindo **k estaticamente** (pendurar massa conhecida no mesmo ponto de fixação, k = m·g/Δx) e registrando a
massa da mola + parafuso + porcas + gancho.

Modelo `BeamFE` (articulada + mola + 5 g, **sem massa da mola**): **11,7 Hz (k₁)** e
**15,1 Hz (k₂)**. Falta ≈ 380 g de massa efetiva no ponto da mola (k₁) para chegar a 7,6 Hz
(k₂ exigiria ≈ 820 g, implausível → provavelmente a curva é da mola k₁, confirmar).
**A massa da mola interfere muito**: massa efetiva ≈ m_mola/3 (+ parafuso, porcas, gancho);
uma mola helicoidal dessas facilmente passa de 0,5–1 kg. Ações: **pesar mola + parafuso +
porcas** (balança), refazer o cálculo; checar k de catálogo (k necessário sem massa extra
seria 626 N/m); considerar inércia do conjunto cilindro/dial do lado da junta.

## A. Dados e decisões (bloqueia o resto)

- [~] **A1. Manifesto dos vídeos**: as sessões `Code/sessions/*.vibro.json` registram fps, escala, ROIs e
      acelerômetro de cada ensaio; `Code/videos/README.md` lista os vídeos versionados. Falta registrar
      SHA-256 dos vídeos guardados fora do git (limite de tamanho, ver `issues.md`).
- [x] **A2. fps do slow-mo**: decidido que não entra no TCC como tema; basta declarar na
      metodologia o fps de captura (240 fps) e passá-lo ao app via `--fps`.
- [x] **A3. Instrumentação (identificada nas fotos, conferir no certificado/datasheet)**:
      acelerômetro Brüel & Kjær **Type 4507 001** (nº de série na foto: 30837; ≈ 5 g,
      piezoelétrico DeltaTron), fixado sobre a face superior da barra; aquisitor
      **B&K LAN-XI Type 3160-A-4/2** (4 entradas/2 saídas, 51,2 kHz) ligado ao notebook;
      software **PULSE LabShop 20.0.0.455**, projeto "acelerometro pratica", medições de
      15/10/2026. Falta: sensibilidade/ganho, taxa de amostragem e duração do registro usadas.
- [ ] **A4. Montagem**: barra de alumínio, 750 mm (720 mm livres), 25,4 × 12,7 mm,
      ≈ 660 g; **mola k₁ = 1500 N/m e k₂ = 2500 N/m** presas por parafuso no **furo a 88 mm
      da ponta** (outro furo a 250 mm, não usado); acelerômetro de 5 g. Falta: como k₁/k₂
      foram obtidos (incerteza), massa da mola, e a condição real da raiz (ver acima).
- [x] **A5. Posições** (confirmadas): acelerômetro a 300 mm do engaste (430 mm da ponta);
      furo/parafuso da mola a 88 mm da ponta (632 mm do engaste). ROIs: parafuso, acelerômetro,
      parede (limpeza/compensação).
- [x] **A6. Sinal do acelerômetro** — sem exportação possível; decidido usar a curva
      **digitalizada** como base (CSV em `Code/data/acelerometro/`, rotulada como digitalizada
      no texto e nos arquivos). f_n = 7,600 Hz é leitura direta do cursor do PULSE. Setup provável:
      200 linhas, 10 Hz, 20 s, fs = 25,6 Hz (confirmar). (PULSE mostra sinal no tempo, 0–18 s, decaimento a partir
      de ≈ 2 s, pico ±15–20 m/s², e espectro 0–10 Hz): 1ª opção, **exportar do PULSE LabShop**
      (dados do Recorder/Display para ASCII/Excel/MAT) — dado real. 2ª opção (fallback):
      **digitalizar a imagem da curva** (a foto atual é da tela com perspectiva/moiré, serve
      pouco; screenshot ou export do gráfico é melhor) (calibração dos eixos +
      segmentação da linha) para obter f_n e ζ. Nesse caso o texto deve dizer
      "sinal digitalizado a partir da curva exportada pelo software", nunca "sinal bruto".
      Precisa saber se a imagem é domínio do tempo ou espectro, resolução e escala dos eixos.
      Colocar as imagens em `Code/data/acelerometro/`.

## B. Código (`Code/vibrometry/`)

- [x] **B1. Execução em lote**: etapa 5 do app (`workflow.process_session`); falta rodar com as
      repetições reais (3 vídeos por mola).
- [~] **B2. Incerteza e repetibilidade** (`vibrometry/uncertainty.py`, CLI `python -m tools.incerteza <sessão>`):
      feito — resolução 1/T, f_n por segmentos (tipo A, entra em `ModalSummary.f_uncertainty` e no relatório),
      repetibilidade de N tomadas (média, desvio, IC 95 % t-Student), propagação linear + Monte Carlo dos
      parâmetros do modelo (`SpecimenCfg.uncertainties`, caminhos tipo `springs[0].k_n_m`), incerteza da escala e
      do erro relativo. Falta: rodar `repeatability` com as 3 tomadas reais por mola (sem bootstrap: com 4
      segmentos e n = 3 tomadas o t-Student basta).
- [~] **B3. Comparação com o acelerômetro** (`vibrometry/reference.py`, CLI
      `python -m vibrometry.reference`): feito e testado com sinais sintéticos — f_n vídeo ×
      acelerômetro (erro %), decaimento/ζ de cada envoltória, razão de amplitude
      (ω²·x do vídeo ÷ envoltória do acelerômetro), figura de sobreposição. Referência
      **digitalizada** em `Code/data/acelerometro/` (ver README lá). Falta rodar com os dados
      reais: `displacement_signals.csv` da gravação da mola k₁ (ROI no acelerômetro) —
      informar qual vídeo corresponde à curva e se foram simultâneos.
      Para as demais molas/gravações: precisa de f_n (cursor) de cada uma.
- [x] **B4. Modelos analíticos** (`beam.py`): `SpringSupportedBeam` (forma fechada, mola na
      ponta) e **`BeamFE`** (elementos finitos de Euler-Bernoulli: molas e massas em posições
      quaisquer, raiz engastada/articulada/mola torsional, forma modal). Verificados entre si
      e contra a tabela do texto (21,1 Hz). CLI: `--spring-k/--spring-pos`,
      `--tip-mass/--mass-pos`, `--root`, `--root-stiffness`. Incerteza propagada: feita (B2). Molas e
      massas agora entram pela função de forma do elemento (antes iam para o nó mais próximo, `issues.md`).
- [ ] **B5. Análise de flicker** (`flicker.py`): espectro do brilho médio de uma região
      estática; checar picos em 100/120 Hz (rede 60 Hz → ripple em 120 Hz) e o
      alias deles dado o fps; reportar razão de modulação e se interfere na banda de
      f_n. Observação: a 240 fps o ripple de 120 Hz cai exatamente em Nyquist.
- [ ] **B6. Rolling shutter — quantificação** (`rolling_shutter.py`): tempo de readout
      (estimar do fps/modo ou medir com barra horizontal), atraso entre linhas
      Δt_linha, defasagem sobre a altura da ROI = 2π·f_n·Δt. Mostra que afeta a fase,
      não a frequência, e dá um número para a seção de limitações.
- [x] **B7. Dois pontos medidos (parafuso e acelerômetro)**: razão de amplitudes medida 2,045 × 2,079 da forma
      modal do `BeamFE` (−1,7 %), ver "Estado atual". Falta repetir nas demais gravações e conferir a fase 0°/180°.
- [ ] **B8. Checagem de aliasing automática** no relatório: marcar picos acima de ~0,4·fs
      e listar candidatos de alias `|f − k·fs|` (hoje `f_n = peaks[0]`, o pico mais alto,
      sem checar).
- [~] **B9. Testes**: `Code/tests/test_beam.py` (11 testes, passam). Falta teste da verificação
      sintética (f_n 0,09 %, ζ ~2 %) como regressão.
- [x] **B10. Higiene do repositório** (feito)
  - [x] `__pycache__` removido do git e ignorado (`**/__pycache__/`, `*.pyc`).
  - [x] Notebooks de rascunho sem valor pro TCC removidos (`random.ipynb` = IRA,
        `interesting.ipynb`); recuperáveis pelo histórico.
  - [x] Material antigo movido para `Code/legacy/` (`main.ipynb`, `opa main.ipynb`,
        `demo.ipynb`, `EUR_1584.NEF`, `Images/`) com README explicando.
  - [ ] README do pacote ainda cita DJI Osmo / RockSteady / exposição curta: atualizar
        para smartphone em slow motion (240 fps).
  - [ ] Issue aberto de desempenho (vídeo inteiro em memória): para o TCC basta recortar
        o trecho útil; documentar.
  - (`requirements.txt` em UTF-16 mantido: o ambiente é Windows.)

## C. Resultados e figuras

- [ ] **C1.** Tabela principal: caso × vídeo × f_vídeo × f_acelerômetro × erro % × f_teórica × erro %.
- [ ] **C2.** Gráfico f_vídeo × f_acc (1:1) com as variações de mola.
- [ ] **C3.** Espectros com pico marcado, Nyquist e (se houver) alias/flicker.
- [ ] **C4.** Amortecimento ζ (decremento logarítmico, só óptico) por caso — o ensaio não
      precisa do acelerômetro para isso.
- [ ] **C5.** Mapa de sensibilidade: efeito de ROI, resize e fps na f_n (barato de rodar com B1).
- [ ] **C6. Mass loading — medir.** Existe um vídeo **sem** o acelerômetro. Previsão com
      `BeamFE` (5 g a 300–420 mm): −0,1 a −0,4 % (≈ 0,02–0,08 Hz), **abaixo ou na ordem da
      resolução espectral Δf = 1/T** — o esperado é "diferença não resolvida", e isso vira
      resultado (o efeito é pequeno nessa posição/massa; para 10 g na ponta seria ≈ 3 %).
      Comparar f_n com/sem acelerômetro com a incerteza de cada vídeo.
- [~] **C7. Multiponto / full-field**: ROIs definidas em pós-processamento sobre o mesmo
      vídeo atuam como uma matriz de sensores virtuais. Para sustentar o termo
      "full-field" no texto, mostrar N ROIs ao longo da barra (amplitude e fase × posição)
      e comparar com a forma modal teórica; sem isso, chamar de "medição multiponto
      sem contato" e deixar full-field como potencial. **Feito na sessão k₁ (ver E5)**; falta repetir com
      marcas ao longo da barra.

## D. Texto (`Book/TCC - Vinicius Andrade Trento.tex`)

> Regra: o texto é escrito na forma final (incluindo o sinal bruto do acelerômetro), mas
> **todo número que ainda não saiu do app fica como placeholder marcado** (`\TODO{}`/`??`),
> nunca valor inventado. Os relatórios exportados pelo app entram como tabelas/figuras.

> **Estado (2026-10-25):** texto reescrito com placeholders `\TODO{}` (57) para tudo que depende da
> campanha de laboratório; comentários `% PRELIMINAR:` guardam os valores da primeira análise e `% REVISAR:`
> marcam afirmações que dependem do resultado final. D1–D8 e D11 estão em rascunho completo; falta preencher.

- [~] **D1. Equipamentos** (acelerômetro B&K 4507 001, aquisitor LAN-XI 3160-A-4/2, PULSE
      LabShop; fotos já em `Book/Images/acelerometro_montado.jpg`, `aquisitor_bk_3160.jpg`,
      `frame_ensaio_mola.jpg`; a foto da tela `pulse_curva_acelerometro_foto.jpg` é provisória): substituir DJI Osmo Action 4 / RockSteady / exposição ≤ 1/2000 s
      pelo smartphone real (modelo, modo slow-mo, fps real, resolução, exposição se
      conhecida). Reescrever o parágrafo de rolling shutter: não foi mitigado por exposição,
      foi **quantificado** (B6).
- [~] **D2. Modelo analítico da mola com DCL**: figura TikZ do diagrama de corpo livre
      (mola, massa, peso, força elástica, inércia), EOM `m ẍ + c ẋ + k x = 0`, ω_n = √(k/m_ef),
      k da mola helicoidal, massa efetiva da mola, tabela de parâmetros com incerteza.
      Fazer o mesmo DCL/seção para a barra (Euler-Bernoulli já existe; faltam condições de
      contorno e figura).
- [~] **D3. Reescrever "Estratégia de Validação"**: referência primária = acelerômetro
      (f_n, ζ e, com o sinal bruto, comparação de forma de onda/deslocamento); secundária =
      teoria; critério de aceitação e como a incerteza entra.
- [~] **D4. Seção de iluminação/flicker** (B5) e declaração do fps de captura (240 fps).
- [~] **D5. Resultados**: substituir "Resultados Preliminares" (régua a 23,98 fps, erro 12,5 %,
      Nyquist 11,99 Hz) por: resultados principais (barra, mola) + a régua mantida como ensaio
      exploratório/histórico, com a discussão honesta já escrita.
- [~] **D6. Discussão e Limitações** (seção própria): rolling shutter, câmera de celular, fps,
      flicker, sem sinal bruto do acelerômetro, n de repetições, escala 2D.
- [~] **D7. Conclusão + Trabalhos futuros** (global shutter, aquisição sincronizada,
      full-field, tempo real). Não existe seção de conclusão hoje.
- [~] **D8. Resumo com resultado numérico + Abstract em inglês + palavras-chave**.
- [~] **D9. Cabeçalho** ("1º Semestre 2026" → semestre atual), checar com a coordenação se o
      formato artigo 2 colunas é aceito para a entrega final do TCC 2.
- [ ] **D10. Cronograma** atualizado ao que de fato foi feito.
- [~] **D11. Referências**: adicionar fontes para flicker/rolling shutter em vibrometria de
      baixo custo e para a mola helicoidal (Shigley/Rao).

## E. Pontos de melhoria da autoavaliação (2026-10-25)

Impacto decrescente. Os pontos 1 e 2 são os que mais elevam o nível do trabalho.

- [x] **E1. Linha de base: fase × correlação simples.** O texto afirma que a estimativa por fase é mais robusta
      que a correlação de intensidade, mas isso não foi medido. Rodar os mesmos vídeos só com a correlação
      cruzada normalizada (o estágio grosseiro já existe em `tracking.py`, sem o refinamento por fase) e comparar
      f_n, amplitude, ruído (D1) e ζ com o método completo. Entra em Resultados (nova subseção) e na Discussão.
      **Feito** (`vibrometry/baseline.py`, `python -m tools.comparar_metodos <sessão>`; `RoiTracker(subpixel=
      "phase"|"parabolic"|"none")`). Sessão k₁, ROIs acelerômetro/parafuso:

      | | fase (ω₀) | fase (ω local) | NCC + parábola | NCC inteiro |
      |---|---|---|---|---|
      | f_n [Hz] | 7,7630 | 7,7630 | 7,7630 | 7,7630 |
      | A acelerômetro [mm] | 7,541 | 7,539 | 7,545 | 7,542 |
      | ζ (acelerômetro) | 0,00103 | 0,00102 | 0,00103 | 0,00106 |
      | piso de ruído espectral, acel./parafuso [µm] | 2,7 / 5,3 | 2,7 / 5,0 | 2,9 / 5,2 | 7,0 / 9,0 |
      | ruído estático, 2 ROIs na parede, σ_y [px] | 0,030 | 0,035 | 0,026 | 0 (quantizado em 1 px) |

      **Conclusão honesta:** a 7,5–15,5 mm de amplitude (15–30 px) os quatro dão a mesma f_n, A (±0,3 %) e ζ; a
      fase empata com a NCC com interpolação parabólica e as duas têm piso de ruído 1,7–2,6× menor que a NCC
      inteira. **A frase "fase é mais robusta que correlação de intensidade" não é sustentada por este ensaio**:
      reescrever como "o refinamento sub-pixel (fase ou parábola) reduz o piso de ruído em relação à correlação
      inteira; a vantagem da fase deve aparecer em amplitudes sub-pixel" e, se quiser provar, filmar um ensaio de
      baixa amplitude (toque leve, < 1 px). Achado lateral: a fase com ω₀ tem viés de ganho quando a textura não
      está centrada no filtro (opção `local_frequency`, `issues.md`).
- [~] **E2. Orçamento de incerteza** (junto de B2): propagar a incerteza de k (medido), massas, L, posições, escala
      (mm/px), fps e resolução espectral (Δf = 1/T) até f_n previsto e medido, e colocar barras de erro nas
      tabelas e figuras de C1–C2. Reportar também n = 3 como mínimo (média, desvio, intervalo).
      **Feito com tolerâncias de hipótese** (`Code/sessions/k1_cm_acc_resultados/incerteza/`; k de catálogo ±10 %,
      massa da ferragem ±5 g, posições ±2 mm, L ±2 mm, b/h ±0,05 mm, E ±2 GPa, ρ ±1 %):
      modelo f₁ = 7,602 ± 0,382 Hz (5,0 %; Monte Carlo 7,576 ± 0,394 Hz), **k responde por 98,6 % da variância**
      (massa 0,6 %, posição da mola 0,4 %, resto < 0,3 %); vídeo f_n = 7,763 Hz, u tipo A (4 segmentos) =
      0,007 Hz, 1/T = 0,148 Hz; erro vídeo × modelo = +2,1 ± 5,1 % → **dentro da incerteza do modelo**, ou seja,
      com k de catálogo o modelo não discrimina 2 %. Escala 0,5130 ± 0,0009 mm/px (0,17 %). Com k medido
      estaticamente a ±2 %, u(f₁) do modelo cai para ≈ 0,09 Hz. Não incluído: erro de forma do modelo (posição da
      raiz, ver E5). Falta: k e massas medidos, n = 3 tomadas, barras de erro em C1–C2.
- [~] **E5. Decidir "full-field".** Ou mostrar a forma modal com ≥ 5 ROIs ao longo da barra (amplitude e fase ×
      posição, comparada ao `BeamFE`; é só pós-processamento do mesmo vídeo) ou trocar "full-field" por
      "medição multiponto" na introdução, na justificativa, no resumo e na discussão. (Ver também C7.)
      **Forma modal feita** (`vibrometry/modeshape.py`, `python -m tools.forma_modal_multiponto <sessão>`,
      `Code/sessions/k1_cm_acc_resultados/forma_modal/`): 15 ROIs (13 ao longo da borda inferior da barra +
      acelerômetro + parafuso), busca só vertical; **9 confiáveis** (NCC ≥ 0,8 e R² ≥ 0,9; falham 250, 350, 400,
      450, 680 e 710 mm, borda sem textura). Todos os pontos confiáveis em fase (|φ| < 1°).
      MAC × `BeamFE` (raiz em x = 0) = **0,9988**. Os pontos caem numa reta (corpo quase rígido girando sobre a
      raiz): ajuste linear dá centro de rotação efetivo **x₀ = −36 mm** (R² = 0,9997), ou seja, 36 mm antes do
      x = 0 da calibração. Com a raiz do modelo em x₀: MAC = **0,9999**, erros pontuais ≤ 2 % (acelerômetro
      −4 %), f₁ previsto 7,543 Hz. → medir no laboratório a distância do eixo do mancal ao x = 0 (roteiro, seção 2).
      **Decisão sugerida (falta confirmar):** 9 pontos não são "full-field"; usar "medição multiponto sem contato"
      no texto e deixar full-field como trabalho futuro, a não ser que a próxima sessão com marcas a cada 50 mm
      dê os 15 pontos.
- [ ] **E6. Enxugar a teoria.** Cortar ou ligar aos resultados o que não é usado: célula de Bragg/heterodinagem,
      rainflow e Palmgren-Miner, detalhes de SHM. Ver também E9 (escopo de SHM).
- [ ] **E7. Fixar os critérios de aceitação antes de olhar os dados finais.** Hoje o texto usa 1 % para a frequência
      vídeo × acelerômetro e a sessão `k1_cm_acc` usa 2,7 % (`crit_freq_pct`), valor que faz o resultado
      preliminar passar. Combinar com o orientador, gravar o valor no texto e na sessão, e não alterar depois.
- [ ] **E8. Explicar o amortecimento.** Vídeo ζ ≈ 0,001 × PULSE ζ ≈ 0,007 (≈ 7×) na primeira análise, em tomadas
      diferentes. Na campanha, comparar na mesma liberação; testar configuração (lâmina do amortecedor, pré-carga,
      cabo do acelerômetro) e o método (janela, ROI, taxa). Se persistir, discutir como limitação, não esconder.
- [ ] **E9. Escopo de SHM.** O trabalho valida uma técnica de **medição** de vibração; nenhum ensaio detecta dano.
      Decidir e alinhar com o orientador: (a) rebaixar SHM a motivação/trabalho futuro (objetivo específico 1,
      subseção de SHM, palavras-chave, justificativa) ou (b) manter um recorte honesto: a troca k₁ → k₂ emula uma
      variação de rigidez e mostra que o método detecta Δf, sem afirmar detecção de dano.
- [ ] **E10. Teste de afrouxamento da fixação (SHM, recorte honesto).** Mesma mola k₁ com a porca/parafuso de
      fixação em 4 níveis (torque normal, ≈ 50 %, só dedos, frouxo) × 3 tomadas, mais um reaperto ao torque base
      (24 tomadas totais no roteiro, seção 5b). Medir f_n, ζ, amplitude e harmônicos (Δζ costuma aparecer antes de
      Δf); duas amplitudes de liberação; confirmar reversibilidade (A' = A). Prioridade P2: só depois do P1 do
      roteiro e de E8 (ζ vídeo × PULSE). **Não entra no texto por enquanto** — decidir após ver os dados e alinhar
      com o orientador (ver E9).

## Perguntas em aberto

1. Massa da(s) mola(s), do parafuso, das porcas e do gancho (pesar). Qual mola gerou 7,6 Hz?
2. f_n do acelerômetro nas demais gravações/molas.
3. Setup do PULSE: banda, linhas, tempo, taxa de amostragem, sensibilidade; exportação dos dados.
4. A junta (conjunto cilindro/dial à esquerda): distância do centro do mancal à borda da barra
   e inércia/atrito do conjunto.
