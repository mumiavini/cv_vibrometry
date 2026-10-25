# cv_vibrometry — vibrometria óptica (TCC, PUCPR)

Medição de vibração por vídeo (estimativa de movimento por fase com filtros de Gabor), validada contra
um acelerômetro e contra o modelo analítico. TCC: *Vibrometria óptica aplicada para medição de vibrações
em testes dinâmicos de bancada*, Vinicius Andrade Trento (orientador: Prof. Helio Emmendoerfer Junior).

## Estrutura

```
Book/                    TCC em LaTeX (.tex, .bib, figuras em Images/, PDF compilado)
Code/
  vibrometry/            núcleo (sem interface): vídeo → fase → sinais → análise modal; modelos analíticos
  vibroapp/              aplicativo desktop (PySide6), usa o núcleo — ver vibroapp/README.md
  tests/                 pytest do núcleo
  sessions/              *.vibro.json: um arquivo por ensaio (parâmetros, ROIs, calibração)
  videos/                vídeos brutos (fora do git, exceto os listados no README da pasta)
  data/acelerometro/     referência do acelerômetro (curvas do PULSE) — ver README da pasta
  tools/                 scripts auxiliares: digitalização da foto do PULSE, figuras do TCC
  legacy/                material antigo/exploratório (notebooks, imagens de teste)
docs/                    planejamento da campanha de medição
TODO.md                  plano de fechamento do TCC e estado atual
issues.md                registro de bugs e problemas encontrados
Cronograma.xlsx          cronograma
Vibrometria.bat          abre o aplicativo (Windows)
```

## Como usar

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt      # Windows
Vibrometria.bat                                  # abre o aplicativo (aceita uma sessão como argumento)
cd Code && python -m pytest tests                # testes
cd Code && python -m vibrometry.run_analysis --synthetic          # verificação com vídeo sintético
cd Code && python -m vibrometry.reference …      # vídeo × acelerômetro (envoltória, f, ζ, amplitude)
cd Code && python -m tools.figuras_tcc_regua     # figuras do ensaio preliminar da régua
```

## Módulos principais do núcleo (`Code/vibrometry/`)

| Módulo | Função |
|---|---|
| `gabor`, `tracking`, `streaming`, `video_io` | leitura do vídeo e rastreamento por fase nas ROIs |
| `spectral`, `analysis`, `sync` | FFT, f e ζ, ajuste senoidal, sincronismo vídeo × acelerômetro |
| `accelerometer` | importação do CSV e integração aceleração → deslocamento |
| `beam` | Euler-Bernoulli: viga engastada, **mola/massa na ponta (`SpringSupportedBeam`)**, **elementos finitos com mola, massa e raiz articulada (`BeamFE`)** |
| `reference` | comparação do vídeo com a referência digitalizada do acelerômetro |
| `session`, `workflow`, `report`, `render` | sessões, processamento de ponta a ponta, tabelas/figuras para o texto |

## Ensaio atual (bancada)

Barra de alumínio 6351-T6 (750 mm; 720 mm livres; 25,4 × 12,7 mm; ≈ 660 g) **articulada em mancal**, com mola
(k₁ = 1500 N/m ou k₂ = 2500 N/m) presa a 88 mm da ponta; acelerômetro B&K 4507 001 (5 g) a 300 mm da
articulação; aquisição B&K LAN-XI 3160-A-4/2 + PULSE LabShop; vídeo com iPhone 17e a 240 fps.
Estado e pendências em `TODO.md` e `issues.md`.
