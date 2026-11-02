# Acelerômetro — 2ª visita (30/10/2026)

B&K 4507 001 (sensibilidade configurada no PULSE: 10,10 mV/(m/s²)) + LAN-XI 3160-A-4/2, PULSE LabShop.
Excitação por batida na barra, vídeo e acelerômetro gravados ao mesmo tempo.

| Arquivo | Tomada (sessão) | Mola |
|---|---|---|
| `med4_1.csv`, `med4.png` | `20261030_al_L735_k1_r1` | k₁ |
| `med5_1.csv`, `med5.png` | `20261030_al_L735_k1_r2` | k₁ |
| `med6_1.csv`, `med6.png` | `20261030_al_L735_k1_r3` | k₁ |
| `med1_1.csv`, `med1.png` | `20261030_al_L735_k2_r1` | k₂ |
| `m2_1.csv`, `m2.png` | `20261030_al_L735_k2_r2` | k₂ |
| `m3_1.csv`, `m3.png` | `20261030_al_L735_k2_r3` | k₂ |

**Os CSVs são digitalizados das capturas de tela do PULSE** (`*.png`), não são uma exportação do sinal.
Colunas: `t_s`, `a_m_s2` (curva), `a_max_m_s2` e `a_min_m_s2` (extremos da coluna de pixels); ≈ 79 pontos/s
(200 pontos/s em `med6_1.csv`, registro de 4 s); degraus de ≈ 0,2 m/s². No texto: "curva digitalizada a partir
da tela do PULSE".

**Limitações (entram como incerteza da referência):**
- A aquisição usou banda de 20 Hz (≈ 51 amostras/s): ≈ 6,5 pontos por ciclo na k₁ (7,8 Hz) e ≈ 3,5 na k₂
  (14,7 Hz). A tela liga as amostras com retas, o que achata os picos (≈ −8 % na k₁, mais na k₂).
- Amplitude vídeo × acelerômetro não fecha: com a escala da geometria o vídeo dá +14 a +82 % (k₁) e +23 a
  +30 % (k₂) a mais. A interpolação linear da tela a 51,2 Hz atenua a curva em sinc²(f/fs) ≈ 0,92 (k₁) e
  ≈ 0,76 (k₂), o que cobre quase toda a diferença da k₂; a dispersão da k₁ fica sem explicação (registros
  `med4`/`med6` começam na própria batida; conferir o passa-alta da entrada do LAN-XI). Tratada como
  incerteza da referência, não como validação de amplitude.
- **Frequência e amortecimento não são afetados** e concordam com o vídeo (`sessions/resumo_dia2.md`).
- Nas sessões, o passa-alta da integração para deslocamento é 4 Hz (k₁) e 8 Hz (k₂): com 1 Hz a deriva de
  ≈ 0,7 Hz da curva digitalizada domina o espectro.

## Conferência da associação vídeo ↔ CSV (2026-11-02)

Horário de cada medição na tela do PULSE ("Status"): med1 22:40:59.1, m2 22:43:36.5, m3 22:45:07.0, med4
22:50:20.2, med5 22:52:10.3, med6 22:53:22.6. O vídeo `IMG_7710.MOV` contém, nessa ordem, as batidas de k₂ r3 e
k₁ r1–r3; os intervalos entre elas no vídeo (em tempo real, corrigindo os quadros perdidos) são 310,1 / 426,0 /
494,5 s e no PULSE 313,2 / 425,6 / 495,6 s (diferenças ≤ 3 s, dentro do erro da estimativa). A razão entre as
envoltórias vídeo/acelerômetro fica aproximadamente constante ao longo de cada decaimento: os pares são o mesmo
evento. A razão muda entre tomadas: ≈ 1,1 em k₁ r2 e nas três de k₂, e ≈ 1,5 em k₁ r1 e r3. k₁ r1 e r3 são
justamente os registros do PULSE que começam na própria batida (sem trecho antes; `med6` com 4 s); a causa da
diferença de escala nesses dois registros não foi identificada a partir das telas.
