# Sessões

Um arquivo `*.vibro.json` por ensaio (parâmetros, ROIs, calibração, acelerômetro, sincronismo e
critérios), criado e lido pelo aplicativo (`Vibrometria.bat`). Os caminhos do vídeo e do acelerômetro
são relativos a esta pasta (`../videos/…`, `../data/acelerometro/…`). O cache do rastreamento
(`*.track.pkl`, ao lado da sessão) é regenerável e não é versionado.

| Sessão | Ensaio |
|---|---|
| `k1_cm_acc.vibro.json` | barra Al 6351-T6 + mola k₁ = 1500 N/m, com acelerômetro; 15/10/2026 |

Nome sugerido pelo app: `AAAAMMDD_<material>_L<mm>_t<mm>_<f>Hz_A<nível>_r<n>`.
