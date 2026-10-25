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

## ⚠ Discrepância modelo × medição (resolver antes de escrever resultados)

Confirmado: raiz = **junta com mancal (articulada)**, alumínio 6351-T6, 660 g, molas de
catálogo k₁ = 1500 e k₂ = 2500 N/m, acelerômetro 5 g a 300 mm do engaste, mola a 632 mm
do engaste (furo de 88 mm da ponta). Pico do acelerômetro: **7,600 Hz**.

Modelo `BeamFE` (articulada + mola + 5 g, **sem massa da mola**): **11,7 Hz (k₁)** e
**15,1 Hz (k₂)**. Falta ≈ 380 g de massa efetiva no ponto da mola (k₁) para chegar a 7,6 Hz
(k₂ exigiria ≈ 820 g, implausível → provavelmente a curva é da mola k₁, confirmar).
**A massa da mola interfere muito**: massa efetiva ≈ m_mola/3 (+ parafuso, porcas, gancho);
uma mola helicoidal dessas facilmente passa de 0,5–1 kg. Ações: **pesar mola + parafuso +
porcas** (balança), refazer o cálculo; checar k de catálogo (k necessário sem massa extra
seria 626 N/m); considerar inércia do conjunto cilindro/dial do lado da junta.

## A. Dados e decisões (bloqueia o resto)

- [ ] **A1. Manifesto dos vídeos** (`Code/videos/manifest.csv`): um registro por vídeo
      com: arquivo, caso (barra / mola-variação X), fps *real de captura*,
      resolução, duração, escala mm/px, ROIs usadas, f_n do acelerômetro [Hz],
      observações (iluminação, fixação, excitação). Hoje o repo só tem o proxy
      `video low res.LRF`; os vídeos reais não estão versionados (guardar fora do
      git + SHA256 no manifesto).
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
- [~] **A6. Sinal do acelerômetro** — digitalização feita (ver `Code/data/acelerometro/README.md`):
      pico 7,62 Hz (cursor 7,600 → +0,26 %), ζ ≈ 0,0073. **Para o texto**: f_n = 7,600 Hz é
      leitura direta do PULSE (dado real); ζ e a envolvente vêm da foto e devem ser
      identificados como tal ou substituídos pela exportação do PULSE. Setup provável:
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

- [ ] **B1. Execução em lote** (`batch.py` + CLI `--batch manifest.csv`): processa
      todos os vídeos e grava `results.csv` (f_n, ζ, pico, SNR, fps, ROI).
- [ ] **B2. Incerteza e repetibilidade** (`uncertainty.py`): resolução Δf = 1/T,
      interpolação parabólica do pico, f_n por janelas/segmentos (média ± desvio),
      bootstrap; agregar N vídeos por caso → média ± desvio.
- [ ] **B3. Comparação com o acelerômetro** (`reference.py`): erro absoluto/relativo
      de f_n por vídeo; gráfico f_vídeo × f_acc com reta 1:1 (e regressão / Bland-Altman se
      n permitir). Quando o sinal bruto do acelerômetro estiver disponível: leitor de CSV,
      reamostragem, f_n/ζ do acelerômetro pelo mesmo estimador e comparação direta
      (dupla integração no domínio da frequência, eq. do texto) com o deslocamento óptico.
      Trocar o critério de aprovação: referência primária = acelerômetro; teoria =
      secundária (hoje `validate_frequency` só compara com a viga).
- [x] **B4. Modelos analíticos** (`beam.py`): `SpringSupportedBeam` (forma fechada, mola na
      ponta) e **`BeamFE`** (elementos finitos de Euler-Bernoulli: molas e massas em posições
      quaisquer, raiz engastada/articulada/mola torsional, forma modal). Verificados entre si
      e contra a tabela do texto (21,1 Hz). CLI: `--spring-k/--spring-pos`,
      `--tip-mass/--mass-pos`, `--root`, `--root-stiffness`. Falta: incerteza propagada
      (k, L, h, E).
- [ ] **B5. Análise de flicker** (`flicker.py`): espectro do brilho médio de uma região
      estática; checar picos em 100/120 Hz (rede 60 Hz → ripple em 120 Hz) e o
      alias deles dado o fps; reportar razão de modulação e se interfere na banda de
      f_n. Observação: a 240 fps o ripple de 120 Hz cai exatamente em Nyquist.
- [ ] **B6. Rolling shutter — quantificação** (`rolling_shutter.py`): tempo de readout
      (estimar do fps/modo ou medir com barra horizontal), atraso entre linhas
      Δt_linha, defasagem sobre a altura da ROI = 2π·f_n·Δt. Mostra que afeta a fase,
      não a frequência, e dá um número para a seção de limitações.
- [ ] **B7. Dois pontos medidos (parafuso e acelerômetro)**: o parafuso foi usado como mais
      um ponto de medição. Usar as duas ROIs como duas amostras da **forma modal**: razão de
      amplitudes (e fase 0/180°) medida × `SpringSupportedBeam.mode_shape(x)` nas posições
      reais (A5). Isso dá um resultado multiponto concreto além da frequência. Se o
      parafuso estiver muito perto do engaste (amplitude ≈ 0), reportar o SNR dele.
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
- [ ] **C7. Multiponto / full-field**: ROIs definidas em pós-processamento sobre o mesmo
      vídeo atuam como uma matriz de sensores virtuais. Para sustentar o termo
      "full-field" no texto, mostrar N ROIs ao longo da barra (amplitude e fase × posição)
      e comparar com a forma modal teórica; sem isso, chamar de "medição multiponto
      sem contato" e deixar full-field como potencial.

## D. Texto (`Book/TCC - Vinicius Andrade Trento.tex`)

> Regra: o texto é escrito na forma final (incluindo o sinal bruto do acelerômetro), mas
> **todo número que ainda não saiu do app fica como placeholder marcado** (`\TODO{}`/`??`),
> nunca valor inventado. Os relatórios exportados pelo app entram como tabelas/figuras.

- [ ] **D1. Equipamentos** (acelerômetro B&K 4507 001, aquisitor LAN-XI 3160-A-4/2, PULSE
      LabShop; fotos já em `Book/Images/acelerometro_montado.jpg`, `aquisitor_bk_3160.jpg`,
      `frame_ensaio_mola.jpg`; a foto da tela `pulse_curva_acelerometro_foto.jpg` é provisória): substituir DJI Osmo Action 4 / RockSteady / exposição ≤ 1/2000 s
      pelo smartphone real (modelo, modo slow-mo, fps real, resolução, exposição se
      conhecida). Reescrever o parágrafo de rolling shutter: não foi mitigado por exposição,
      foi **quantificado** (B6).
- [ ] **D2. Modelo analítico da mola com DCL**: figura TikZ do diagrama de corpo livre
      (mola, massa, peso, força elástica, inércia), EOM `m ẍ + c ẋ + k x = 0`, ω_n = √(k/m_ef),
      k da mola helicoidal, massa efetiva da mola, tabela de parâmetros com incerteza.
      Fazer o mesmo DCL/seção para a barra (Euler-Bernoulli já existe; faltam condições de
      contorno e figura).
- [ ] **D3. Reescrever "Estratégia de Validação"**: referência primária = acelerômetro
      (f_n, ζ e, com o sinal bruto, comparação de forma de onda/deslocamento); secundária =
      teoria; critério de aceitação e como a incerteza entra.
- [ ] **D4. Seção de iluminação/flicker** (B5) e declaração do fps de captura (240 fps).
- [ ] **D5. Resultados**: substituir "Resultados Preliminares" (régua a 23,98 fps, erro 12,5 %,
      Nyquist 11,99 Hz) por: resultados principais (barra, mola) + a régua mantida como ensaio
      exploratório/histórico, com a discussão honesta já escrita.
- [ ] **D6. Discussão e Limitações** (seção própria): rolling shutter, câmera de celular, fps,
      flicker, sem sinal bruto do acelerômetro, n de repetições, escala 2D.
- [ ] **D7. Conclusão + Trabalhos futuros** (global shutter, aquisição sincronizada,
      full-field, tempo real). Não existe seção de conclusão hoje.
- [ ] **D8. Resumo com resultado numérico + Abstract em inglês + palavras-chave**.
- [ ] **D9. Cabeçalho** ("1º Semestre 2026" → semestre atual), checar com a coordenação se o
      formato artigo 2 colunas é aceito para a entrega final do TCC 2.
- [ ] **D10. Cronograma** atualizado ao que de fato foi feito.
- [ ] **D11. Referências**: adicionar fontes para flicker/rolling shutter em vibrometria de
      baixo custo e para a mola helicoidal (Shigley/Rao).

## Perguntas em aberto

1. Massa da(s) mola(s), do parafuso, das porcas e do gancho (pesar). Qual mola gerou 7,6 Hz?
2. f_n do acelerômetro nas demais gravações/molas.
3. Setup do PULSE: banda, linhas, tempo, taxa de amostragem, sensibilidade; exportação dos dados.
4. A junta (conjunto cilindro/dial à esquerda): distância do centro do mancal à borda da barra
   e inércia/atrito do conjunto.
