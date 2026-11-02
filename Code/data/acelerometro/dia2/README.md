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
- Amplitude vídeo × acelerômetro não fecha (diferenças de −20 % a +35 % entre tomadas): tratada como
  incerteza da referência (calibração/aquisição/digitalização), não como validação de amplitude.
- **Frequência e amortecimento não são afetados** e concordam com o vídeo (`sessions/resumo_dia2.md`).
- Nas sessões, o passa-alta da integração para deslocamento é 4 Hz (k₁) e 8 Hz (k₂): com 1 Hz a deriva de
  ≈ 0,7 Hz da curva digitalizada domina o espectro.
