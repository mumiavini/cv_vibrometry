# TODO — fechamento do TCC (resultados, validação e texto)

Estado em 2026-10-31. Itens marcados `[ ]` abertos, `[x]` feitos.
Ordem sugerida: **A → B → C → D**. Dados e decisões (A) destravam tudo.

## Tese (mensagem central)

> Um **smartphone em slow motion** (rolling shutter, sem controle de exposição)
> mede a frequência natural com concordância aceitável com o acelerômetro e com
> o modelo analítico, **sem contato e sem mass loading**. Limitações
> (rolling shutter, fps do slow-mo, flicker, ausência do sinal bruto do
> acelerômetro) são **quantificadas e discutidas**, não escondidas.

---

## Estado atual (2026-10-31) — o que já existe e o que a primeira análise mostrou

**Parâmetros medidos no laboratório (2ª visita, roteiro seções 1 e 2; `Code/data/bancada/`,
`python -m tools.parametros_bancada`):**

| Grandeza | k₁ | k₂ |
|---|---|---|
| k estático (N/m) | **857 ± 62** (catálogo 1500, −43 %) | **3291 ± 346** (catálogo 2500, +32 %) |
| massa da mola (g) | 161 | 382 |
| m_ef = m_s/3 + parafuso 36 g + porcas 10 g (g) | 99,7 | 173,3 |
| **f₁ previsto, `BeamFE` (Hz)** | **7,69 ± 0,28** | **13,71 ± 0,72** |
| f₂ (Hz) | 78,6 | 76,6 |

Geometria a partir do eixo do mancal: L = 735 mm (ponta), a = 655 mm (parafuso da mola), x_a = 305 mm
(acelerômetro); barra 644 g (ρ efetiva 2662 kg/m³). Leituras da mola anotadas em "mm" são **cm** (em mm daria
f₁ ≈ 24 Hz). A sessão `k1_cm_acc` foi atualizada e reexportada (previsão, forma modal, incerteza).

**Já feito (em `main`):** aplicativo (`vibroapp`, 6 etapas), núcleo `vibrometry` (rastreamento por fase,
sincronismo, integração do acelerômetro, lote, relatório LaTeX), modelos analíticos da barra com mola e
raiz articulada (`BeamFE`), referência do acelerômetro digitalizada, primeira sessão real
(`Code/sessions/k1_cm_acc.vibro.json`, iPhone 17e, 240 fps, mola k₁), 67 testes. Ferramentas de análise da
sessão em `Code/tools/` (comparação de métodos E1, forma modal multiponto E5, incerteza B2/E2), resultados em
`Code/sessions/k1_cm_acc_resultados/{comparacao_metodos,forma_modal,incerteza}/`.

**Primeira análise (vídeo `k1_cm_acc.mov`, ROI no acelerômetro, escala corrigida 0,513 mm/px):**

| Resultado | Valor | Observação |
|---|---|---|
| f_n vídeo | 7,763 Hz (estável de 1 a 7,5 s) | PULSE: 7,600 Hz → +2,1 % (critério do app: 1 %); takes diferentes. **Modelo com k medido: 7,69 ± 0,28 Hz** (vídeo +0,9 %, PULSE −1,2 %) |
| amplitude no acelerômetro | 7,58 mm → ω²·A ≈ 18 m/s² | concorda com a envoltória do PULSE (17–19 m/s²) |
| razão de amplitudes acelerômetro/parafuso | 0,486 | forma modal do `BeamFE` com os valores medidos (305/655 mm): 0,473 → +2,8 % (antes, com 300/632 mm e 383 g: 0,481, +1,1 %); ver "pivô efetivo" abaixo |
| ζ vídeo (envoltória) | ≈ 0,0010 (σ = 0,049 1/s) | PULSE: ≈ 0,0072 (σ = 0,345 1/s) → **não concorda (×7)** |
| fase/forma de onda vídeo × acelerômetro | sem sentido | takes diferentes (20:22:39 × 20:48:57) e CSV não é forma de onda |

**Problemas encontrados e corrigidos/registrados** (detalhes em `issues.md`): escala 7,2× errada na sessão,
`f_analysis = 0,79 Hz`, metadados de régua de aço; CSV do acelerômetro é um traço em zigue-zague; vídeo e PULSE
não são o mesmo ensaio; o app ainda prevê f₁ com viga engastada; vídeo de 91 MB no git.

**Acelerômetro da 2ª visita** (`Code/data/acelerometro/last measturements/`, sessões `20261030_*`; f pelo ajuste
senoidal na janela após a batida):

| Mola | Tomadas | f_acc (Hz) | média ± desvio (CV) | modelo (Hz) | diferença | k que reproduz |
|---|---|---|---|---|---|---|
| k₁ | med4, med5, med6 | 7,816 / 7,813 / 7,818 | 7,816 ± 0,002 (0,03 %) | 7,69 ± 0,28 | +1,6 % (0,45 u) | 885 N/m (medido 857 ± 62) |
| k₂ | med1, m2, m3 | 14,659 / 14,646 / 14,706 | 14,67 ± 0,03 (0,21 %) | 13,71 ± 0,72 | +7,0 % (1,3 u) | 3774 N/m (medido 3291 ± 346) |

k₂: o k que fecha a medição (3774 N/m) coincide com o ajuste do ensaio estático **sem o ponto de 0 N** (3806 N/m),
reforçando que o 1º trecho (assentamento) viesou k₂ para baixo. ζ (acelerômetro, decremento): k₁ 0,005–0,006,
k₂ 0,002–0,003. **Confirmar se esses CSVs são exportação do PULSE ou digitalização da tela** (≈ 79 amostras/s,
degraus de ≈ 0,2 m/s², colunas a_max/a_min): f vale nos dois casos; amplitude e ζ ficam menos confiáveis se for
digitalização. Pico do k₁ na 1ª visita: 7,600 Hz (cursor) — a 2ª visita dá 7,816 Hz.

**Vídeos da 2ª visita (2026-11-01):** usar o **original** do iPhone (cabo/DCIM); o corte no app Fotos
re-renderiza a câmera lenta e estraga a base de tempo. O original perde ≈ 17 % dos quadros (intervalos de
2/240 s); o app agora usa o tempo real de cada quadro e reamostra os sinais (`issues.md`). Recortar a tomada
pelo início/fim do trecho no próprio app. `k1_cm_acc`: 1 quadro perdido → f_n 7,763 → 7,752 Hz.

**Próximos passos (ordem):**
1. ~~Ir ao laboratório~~ — feito (2ª visita): k estático e massas medidos (acima). **Falta subir os vídeos e os
   arquivos do PULSE** da visita (pastas `tcc2/dia 2/Mola K1|K2/Medição 1–3` e `Fadiga` no Google Drive, ainda
   vazias em 2026-10-31) e as tabelas da seção 4 do roteiro (arquivo de cada tomada, f_n do cursor, lâmina,
   observações). Vídeos grandes: processar no app (etapas 1–6) e dar push das sessões e `_resultados/`.
2. Nas sessões novas, usar os parâmetros medidos (copiar o bloco `specimen` de `k1_cm_acc`; para k₂: k = 3291,
   mola 382 g, ferragens 46 g) e, se as marcas foram feitas no eixo do mancal, `calibration` com p1 no eixo
   (`x0_mm` = 0). Banda do PULSE ≥ 30 Hz é obrigatória para ver k₂ (f₁ ≈ 13,7 Hz).
3. Explicar a diferença de amortecimento (ζ vídeo ≈ 0,001 × PULSE ≈ 0,007) e de f_n (+2,1 %) com as tomadas
   simultâneas.
4. ~~Integrar `BeamFE` ao app~~ — feito. ~~Preencher as massas pesadas~~ — feito na sessão `k1_cm_acc`.
5. Texto do TCC (seção D): parâmetros e previsões já preenchidos; resultados das tomadas novas pendentes.

---

## ✔ Discrepância modelo × medição — resolvida (2026-10-31)

O modelo antigo previa 11,7 Hz (k₁ de catálogo, sem massa da mola) contra 7,60 Hz medidos, e a sessão compensava
com uma "ferragem" ajustada de 383 g. **A causa era o k de catálogo**: o ensaio estático deu k₁ = 857 ± 62 N/m, e a
massa efetiva medida no ponto da mola é 99,7 g (161/3 + 36 + 10). Com isso o modelo dá 7,69 ± 0,28 Hz, entre o
PULSE (7,600) e o vídeo (7,763), ambos a ≤ 0,33 u. Detalhes e histórico em `issues.md` e `Code/data/bancada/README.md`.

**Pontos que ficam (não mudam a conclusão, entram na discussão):**
- **Pivô efetivo ≈ 24 mm além do eixo medido** (`issues.md`): perto da junta a barra se move mais do que um pino
  no eixo permitiria (+30 % a 65 mm; 1,45 × 1,0 mm a ≈ 40 mm), e a carcaça da junta fica parada (5 µm). Eixo e
  folga já descartados (medidas do meio do engaste, sem folga); resta flexibilidade elástica do eixo/peça que gira
  (≈ 0,5 mm na raiz) ou erro dos pontos perto da borda da imagem. Com a raiz em −24 mm o modelo dá 7,62 Hz (dentro
  da incerteza). → nas tomadas novas, ROI na peça que gira e na barra junto do engaste; se não se resolver, entra
  como limitação na discussão.
- **k₁ pouco linear** (k incremental 667–1429 N/m entre leituras; R² = 0,985) e **k₂ com o 1º trecho macio**
  (assentamento do gancho?). Repetir o ensaio estático subindo e descendo a carga reduziria ±7 % / ±10 % de k,
  que é ≈ 98 % da incerteza do f₁ previsto.
- **Pré-carga × amplitude:** o peso da barra dá ≈ 4 N de tração na mola; a ±15,5 mm no parafuso a força dinâmica
  com k₁ é ±13 N. A mola afrouxaria no alto do ciclo se nada mais a pré-carregar; o sinal limpo indica que não
  afrouxa, mas conferir harmônicos no início das tomadas novas.
- **Posição do parafuso:** trena 655 mm (80 mm da ponta) × imagem ≈ 650 mm (≈ 85 mm da ponta); 5 mm em a
  mudam f₁ em ≈ 0,04 Hz.

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
- [x] **A4. Montagem** (medida em 2026-10, `Code/data/bancada/`): barra de alumínio 750 mm, 25,4 × 12,7 mm
      (nominal), **644 g**; eixo do mancal a **735 mm** da ponta; **k₁ = 857 ± 62 N/m (161 g)** e
      **k₂ = 3291 ± 346 N/m (382 g)** por ensaio estático (catálogo 1500/2500); parafuso 36 g, porcas 10 g;
      acelerômetro 5 g (pesado). Falta: conferir b/h com paquímetro (efeito pequeno);
      condição real da raiz (pivô efetivo, ver acima).
- [x] **A5. Posições** (medidas do eixo do mancal): acelerômetro a **305 mm**; parafuso da mola a **655 mm**
      (80 mm da ponta). Antes: 300 e 632 mm, medidos de outra referência. No vídeo `k1_cm_acc`, o ponto p1 da
      calibração é a face da junta, 15 mm do eixo (`calibration.x0_mm`). ROIs: parafuso, acelerômetro,
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
- [x] **B7. Dois pontos medidos (parafuso e acelerômetro)**: razão acelerômetro/parafuso medida 0,486 × 0,473 da
      forma modal do `BeamFE` com os parâmetros medidos (+2,8 %), ver "Estado atual". Falta repetir nas demais
      gravações e conferir a fase 0°/180°.
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

- [x] **E1. Linha de base: fase × correlação simples.** **Decisão (2026-10-25): não entra no texto** — não é
      necessário para a tese (f_n vídeo × acelerômetro); as vantagens da fase ficam só na fundamentação, citadas da
      literatura, e Resultados/Conclusão não afirmam que este trabalho provou a fase superior. Registro do que foi
      feito, caso a banca pergunte: O texto afirma que a estimativa por fase é mais robusta
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
      **Atualizado (2026-10-31) com k e massas medidos** (`specimen.uncertainties` da sessão: k ± 62 N/m pelo
      ajuste, massas ± 1 g, posições e L ± 2 mm, b/h ± 0,1 mm, ρ ± 0,5 %, E ± 2 GPa): f₁ = 7,692 ± 0,280 Hz
      (3,6 %; Monte Carlo 7,697 ± 0,270), k ainda responde por 98 % da variância; erro vídeo × modelo
      = +0,93 ± 3,7 %. Para k₂: 13,71 ± 0,72 Hz. Falta: n = 3 tomadas e barras de erro em C1–C2.
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
      **Atualizado (2026-10-31):** com a geometria medida (eixo do mancal 15 mm antes de p1, L = 735 mm) e o k
      medido, MAC (raiz no eixo) = **0,9996**; a reta pelos pontos cruza zero em **−24 mm** do eixo, contra −4 mm
      na forma do próprio modelo → o pivô efetivo fica ≈ 20 mm além do eixo medido (ver "Discrepância" e
      `issues.md`); com a raiz lá, MAC = 1,0000 e f₁ = 7,62 Hz.
      **Decisão (2026-10-31): multiponto.** Usar "medição multiponto sem contato" no texto, com pontos igualmente
      espaçados ao longo da barra (≈ 50 mm) + acelerômetro e parafuso, MAC × `BeamFE` e os pontos excluídos pelo
      critério de qualidade mostrados. Full-field (linha densa ao longo da barra) fica como trabalho futuro: viável
      offline (minutos por vídeo), mas com ganho pequeno para o 1º modo, que é quase uma reta.
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
      **Feito em versão improvisada na 2ª visita (pasta `Fadiga`, mola k₁):** sistema completo gravado com o
      acelerômetro; depois a porca da mola foi afrouxada **meia volta por vez**, com a barra excitada por
      **batida** (sem shaker, sem medir força) em cada nível; fotos antes e depois de cada batida. Diferenças do
      roteiro: níveis por meia volta (não por torque), sem reaperto (A') registrado, repetições a confirmar.
      Falta: subir os arquivos do PULSE/vídeos e anotar o nº de meias-voltas de cada registro.

## Perguntas em aberto

1. ~~Massa da(s) mola(s), do parafuso, das porcas e do gancho (pesar). Qual mola gerou 7,6 Hz?~~ Pesadas; a
   curva de 7,6 Hz é da mola k₁ (o modelo dá 7,69 Hz com k₁ e 13,7 Hz com k₂). Não há gancho; "porcas" inclui as arruelas. Acelerômetro: 5 g (pesado).
2. f_n do acelerômetro nas demais gravações/molas.
3. Setup do PULSE: banda, linhas, tempo, taxa de amostragem, sensibilidade; exportação dos dados.
4. A junta (conjunto cilindro/dial à esquerda): ~~distância do centro do mancal à borda da barra~~ (735 mm à
   ponta, medido do **meio do engaste**, que é o eixo; barra de 750 mm); **sem folga** (confirmado). Geometria do
   modelo confirmada. O pivô efetivo do vídeo (−24 mm) segue sem explicação: ver `issues.md`.
5. ~~O que é a pasta `Fadiga`~~: teste de afrouxamento improvisado (E10). Faltam os arquivos e quantas meias-voltas
   em cada registro.
7. Ensaio estático das molas: ~~como foram aplicadas as forças~~ massas penduradas, rotuladas em newtons. Falta
   paquímetro. Acelerômetro pesado: 5 g.
8. ~~Excitação~~: batida manual na barra, sem medir força, em todas as tomadas (vídeo + PULSE e afrouxamento).
   Texto do TCC atualizado.
6. A barra do amortecedor (haste e placa perto de x ≈ 165 mm) não se move no vídeo (≤ 0,01 mm): não está presa
   à barra e não entra no modelo.
