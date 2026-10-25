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

## A. Dados e decisões (bloqueia o resto)

- [ ] **A1. Manifesto dos vídeos** (`Code/videos/manifest.csv`): um registro por vídeo
      com: arquivo, caso (barra / mola-variação X), fps *real de captura*,
      resolução, duração, escala mm/px, ROIs usadas, f_n do acelerômetro [Hz],
      observações (iluminação, fixação, excitação). Hoje o repo só tem o proxy
      `video low res.LRF`; os vídeos reais não estão versionados (guardar fora do
      git + SHA256 no manifesto).
- [x] **A2. fps do slow-mo**: decidido que não entra no TCC como tema; basta declarar na
      metodologia o fps de captura (240 fps) e passá-lo ao app via `--fps`.
- [ ] **A3. Descrever o acelerômetro**: modelo, tipo (MEMS/piezo), massa, fixação,
      taxa de amostragem, como o f_n em Hz foi extraído, incerteza do instrumento.
- [ ] **A4. Descrever a montagem da mola** (dados para o DCL e para o modelo):
      massa(s) suspensa(s) (incluindo o acelerômetro), constante k ou geometria da
      mola (d, D, N, G), o que "variação" significa (massa? mola? comprimento?),
      onde ficam as ROIs (parafuso de fixação × acelerômetro) e o papel de cada
      uma (ver B7).
- [ ] **A5. Dados da barra de alumínio**: L livre medido a partir da borda do
      engaste, b, h (paquímetro), E/ρ adotados.

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
- [ ] **B4. Modelo massa-mola** (`spring_mass.py`): f_n = (1/2π)√(k/(m + m_mola/3)),
      k de mola helicoidal = G d⁴ / (8 D³ N), incerteza propagada; reaproveitar a
      estrutura de `beam.py`. Integrar ao `PipelineConfig` (hoje só `CantileverBeam`).
- [ ] **B5. Análise de flicker** (`flicker.py`): espectro do brilho médio de uma região
      estática; checar picos em 100/120 Hz (rede 60 Hz → ripple em 120 Hz) e o
      alias deles dado o fps; reportar razão de modulação e se interfere na banda de
      f_n. Observação: a 240 fps o ripple de 120 Hz cai exatamente em Nyquist.
- [ ] **B6. Rolling shutter — quantificação** (`rolling_shutter.py`): tempo de readout
      (estimar do fps/modo ou medir com barra horizontal), atraso entre linhas
      Δt_linha, defasagem sobre a altura da ROI = 2π·f_n·Δt. Mostra que afeta a fase,
      não a frequência, e dá um número para a seção de limitações.
- [ ] **B7. ROI no parafuso × ROI no acelerômetro**: tratar a ROI do parafuso como
      (i) entrada/base e controle negativo (não deve ter pico em f_n) ou
      (ii) referência para compensação (eq. `compensacao`). Se entrada/saída:
      transmissibilidade H(f) = X_acc(f)/X_parafuso(f). Decidir em A4.
- [ ] **B8. Checagem de aliasing automática** no relatório: marcar picos acima de ~0,4·fs
      e listar candidatos de alias `|f − k·fs|` (hoje `f_n = peaks[0]`, o pico mais alto,
      sem checar).
- [ ] **B9. Testes** (`pytest`) a partir da verificação sintética já existente
      (f_n 0,09 %, ζ ~2 %) para travar regressões.
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
- [ ] **C6.** Se houver vídeo com/sem acelerômetro: mass loading medido × Eq. `mass_loading`.
- [ ] **C7. Multiponto / full-field**: ROIs definidas em pós-processamento sobre o mesmo
      vídeo atuam como uma matriz de sensores virtuais. Para sustentar o termo
      "full-field" no texto, mostrar N ROIs ao longo da barra (amplitude e fase × posição)
      e comparar com a forma modal teórica; sem isso, chamar de "medição multiponto
      sem contato" e deixar full-field como potencial.

## D. Texto (`Book/TCC - Vinicius Andrade Trento.tex`)

> Regra: o texto é escrito na forma final (incluindo o sinal bruto do acelerômetro), mas
> **todo número que ainda não saiu do app fica como placeholder marcado** (`\TODO{}`/`??`),
> nunca valor inventado. Os relatórios exportados pelo app entram como tabelas/figuras.

- [ ] **D1. Equipamentos**: substituir DJI Osmo Action 4 / RockSteady / exposição ≤ 1/2000 s
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

## Perguntas em aberto (respostas definem escopo)

1. Qual é exatamente o ensaio da mola? (massa-mola vertical? "variação" = massa, rigidez ou
   comprimento? o acelerômetro é a própria massa?)
2. O ROI do parafuso é referência, entrada ou controle?
3. Quantos vídeos por caso existem, e qual foi o modo/fps do celular?
4. Existe gravação com e sem o acelerômetro (para mass loading)?
5. O acelerômetro tem f_n só em Hz para todos os casos, ou também ζ?
