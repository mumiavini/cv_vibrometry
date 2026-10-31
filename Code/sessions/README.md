# Sessões

Um arquivo `*.vibro.json` por ensaio (parâmetros, ROIs, calibração, acelerômetro, sincronismo e
critérios), criado e lido pelo aplicativo (`Vibrometria.bat`). Os caminhos do vídeo e do acelerômetro
são relativos a esta pasta (`../videos/…`, `../data/acelerometro/…`). O cache do rastreamento
(`*.track.pkl`, ao lado da sessão) é regenerável e não é versionado.

| Sessão | Ensaio |
|---|---|
| `k1_cm_acc.vibro.json` | barra Al 6351-T6 + mola k₁ (857 N/m medido; catálogo 1500), com acelerômetro; 15/10/2026. Parâmetros do corpo de prova medidos em `../data/bancada/` (2ª visita) |

| `20261030_al_L735_k{1,2}_r{1,2,3}.vibro.json` | 2ª visita: molas k₁ e k₂, 3 tomadas cada, vídeo + acelerômetro simultâneos (batida). Corpo de prova e acelerômetro já configurados; **falta o vídeo**, as ROIs e a calibração |
| `20261030_al_L735_k1_afrouxa_c{1..5}.vibro.json` | teste de afrouxamento improvisado (ciclos 1–5), só vídeo |

### Sessões da 2ª visita: como usar

1. Baixe cada vídeo do Drive (`tcc2/dia 2/...`, caminho nas notas da sessão) e salve em `Code/videos/` com o
   **nome da sessão** + `.mov` (ex.: `20261030_al_L735_k1_r1.mov`). Os vídeos ficam fora do git.
2. Abra a sessão no app (`Vibrometria.bat <sessão>`). Etapa 2: crie as ROIs com os nomes **`Acelerometro`** e
   **`Parafuso`** (as posições 305 e 655 mm já estão na sessão), uma ROI de referência na parede e, se der, uma na
   peça giratória da junta e outra na barra junto do engaste (pivô efetivo, `issues.md`). Calibre com dois pontos
   de distância conhecida e informe o comprimento real.
3. Rode, sincronize pelo impacto (etapa 4) e exporte o relatório (etapa 6). Dê push da sessão e de `_resultados/`.

O acelerômetro já está configurado (CSV, janela após a batida, passa-alta de 4 Hz para k₁ e 8 Hz para k₂; com
1 Hz a integração para deslocamento amplifica a deriva de ≈ 0,7 Hz da curva e o app acha o pico errado).

Nome sugerido pelo app: `AAAAMMDD_<material>_L<mm>_t<mm>_<f>Hz_A<nível>_r<n>`.
