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
- Amplitude vídeo × acelerômetro: com a escala da geometria e o sincronismo corrigido (abaixo), o vídeo dá
  +13 a +16 % (k₁) e +23 a +30 % (k₂) a mais. A interpolação linear da curva a 51,2 Hz atenua uma senoide em
  sinc²(f/fs) ≈ 0,93 (k₁) e ≈ 0,76 (k₂); descontado esse fator, sobra +4 a +8 % (k₁) e −7 a −2 % (k₂). Tratada
  como comparação indicativa (calibração do acelerômetro não verificada), não como validação de amplitude.
- **Frequência e amortecimento não são afetados** e concordam com o vídeo (`sessions/resumo_dia2.md`).
- Nas sessões, o passa-alta da integração para deslocamento é 4 Hz (k₁) e 8 Hz (k₂): com 1 Hz a deriva de
  ≈ 0,7 Hz da curva digitalizada domina o espectro.

## Conferência da associação vídeo ↔ CSV (2026-11-02)

Horário de cada medição na tela do PULSE ("Status"): med1 22:40:59.1, m2 22:43:36.5, m3 22:45:07.0, med4
22:50:20.2, med5 22:52:10.3, med6 22:53:22.6. O vídeo `IMG_7710.MOV` contém, nessa ordem, as batidas de k₂ r3 e
k₁ r1–r3; os intervalos entre elas no vídeo (em tempo real, corrigindo os quadros perdidos) são 310,1 / 426,0 /
494,5 s e no PULSE 313,2 / 425,6 / 495,6 s (diferenças ≤ 3 s, dentro do erro da estimativa). A razão entre as
envoltórias vídeo/acelerômetro fica aproximadamente constante ao longo de cada decaimento: os pares são o mesmo
evento. A razão muda entre tomadas:
≈ 1,1 em k₁ r2 e nas três de k₂, e ≈ 1,5 em k₁ r1 e r3 — **resolvido em 2026-11-03: erro de sincronismo.**

## Sincronismo de k₁ r1 e r3 (corrigido em 2026-11-03)

`med4` (k₁ r1), `med6` (k₁ r3) e `m3` (k₂ r3) começam com a barra já em movimento, sem a batida. Nas sessões de
k₁ r1 e r3, o início do registro tinha sido alinhado à batida do vídeo. O horário "Status" de cada medição,
comparado ao instante da batida no vídeo (tempo real, quadros perdidos corrigidos) e tomando `med5` como
referência (registro com a batida), mostra que `med4` começou **3,06 s** e `med6` **1,01 s** depois da batida
(`m3`: 0,11 s, dentro de um período; o sincronismo dela já estava certo). O máximo da correlação perto desses
valores dá deslocamentos de 24,0 e 8,0 períodos — por isso a fase concordava mesmo com o sincronismo errado.

| Tomada | offset antigo (s) | offset corrigido (s) | diferença de amplitude antes → depois |
|---|---|---|---|
| k₁ r1 (`med4`) | −0,940 | −4,012 | +82,5 % → +12,8 % |
| k₁ r3 (`med6`) | −1,574 | −2,596 | +47,6 % → +16,3 % |

Janelas novas: [4,3; 13,9] s (r1) e [2,9; 6,5] s (r3), 0,3 s depois do início do registro (borda da
integração). Reexportado com `python -m tools.reexportar_modelo --comparacao` (Code/). Status do PULSE:
med1 22:40:59.057, m2 22:43:36.479, m3 22:45:06.994, med4 22:50:20.245, med5 22:52:10.337, med6 22:53:22.587.
