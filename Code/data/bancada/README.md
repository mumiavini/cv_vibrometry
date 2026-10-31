# Bancada: massas, rigidez das molas e geometria (medidos no laboratório)

Medições da segunda visita ao laboratório, feitas pelo `docs/roteiro_laboratorio.md` (seções 1 e 2).
Data a confirmar.

| Arquivo | Conteúdo |
|---|---|
| `massas.csv` | massas pesadas [g]: molas k₁ e k₂, parafuso, porcas + arruelas, barra; acelerômetro nominal (não pesado) |
| `rigidez_molas.csv` | ensaio estático: força aplicada [N] × leitura de comprimento da mola, para k₁ e k₂ |
| `geometria.csv` | distâncias a partir do **centro do eixo do mancal** [mm] e seção da barra |
| `resultados/` | gerado por `python -m tools.parametros_bancada` (a partir de `Code/`) |

## Unidade das leituras da mola

As leituras foram anotadas como "mm" (12,75 → 15,11 de 0 a 20 N), mas são **cm**:

- 12,75 mm seria curto demais para uma mola helicoidal de 161 g;
- em mm, k₁ ≈ 8,6 kN/m e o modelo daria f₁ ≈ 23,9 Hz, contra 7,60 Hz (PULSE) e 7,76 Hz (vídeo) medidos;
- em cm, k₁ = 857 N/m e o modelo dá 7,69 Hz.

O arquivo guarda o número como anotado (coluna `leitura`). A conversão (`READING_TO_M = 1e-2`) está em
`tools/parametros_bancada.py`.

## Resultado

Ajuste por mínimos quadrados de F = k·Δx + c, com intercepto livre, e incerteza-padrão de k pelos resíduos.
O modelo é o de elementos finitos da barra articulada: ⅓ da massa da mola mais parafuso e porcas a 655 mm, e
acelerômetro de 5 g a 305 mm. A densidade efetiva, 2662 kg/m³, vem da massa medida da barra.

| | k₁ | k₂ |
|---|---|---|
| k de catálogo (N/m) | 1500 | 2500 |
| **k medido (N/m)** | **857 ± 62** (−43 % do catálogo) | **3291 ± 346** (+32 %) |
| massa efetiva m_s/3 + m_f (g) | 99,7 | 173,3 |
| **f₁ previsto (Hz)** | **7,69 ± 0,28** | **13,71 ± 0,72** |
| f₂ (Hz) | 78,6 | 76,6 |
| φ(a)/φ(x_a) (parafuso/acelerômetro) | 2,113 | 2,040 |
| efeito do acelerômetro em f₁ | −0,15 % | −0,13 % |

Com k₁ as frequências já medidas ficam dentro da incerteza do modelo: PULSE 7,600 Hz (−1,2 %, −0,33 u) e
vídeo 7,763 Hz (+0,9 %, +0,26 u). O k reproduziria cada uma com 837 e 873 N/m, respectivamente; ambos estão
dentro de ±1 u de 857. A diferença entre o modelo antigo (11,7 Hz) e a medição vinha do **k de catálogo**,
não de massa ausente. Com k medido, a mola e as ferragens baixam f₁ de 9,00 para 7,69 Hz. O "383 g" da
sessão antiga era apenas o valor que fechava a conta com k = 1500 N/m.

Tabelas completas, com o orçamento de incerteza, em `resultados/parametros.md`. A figura é
`resultados/fig_rigidez_molas.{png,pdf}`.

## Observações

- **k₁ não é bem linear.** O k incremental entre leituras é 667, 1429, 1163 e 704 N/m. O ajuste tem
  R² = 0,985, e a incerteza de ±7 % já inclui essa dispersão. Uma repetição **subindo e descendo** a carga
  separaria não linearidade, histerese e erro de leitura.
- **k₂: o primeiro trecho (0 → 2 N) é mais macio** (1176 N/m contra ≈ 4000 N/m depois), provavelmente pelo
  assentamento do gancho ou da rosca. Sem o ponto de 0 N, o ajuste dá 3806 N/m. O intercepto livre absorve
  parte do efeito, mas k₂ é a maior incerteza da previsão (±10 %).
- **Pré-carga × amplitude.** O peso da barra, do parafuso e das porcas dá cerca de 4 N de tração na mola em
  equilíbrio. Na sessão k1_cm_acc, a amplitude no parafuso (≈ 15,5 mm) corresponde a ±13 N de força
  dinâmica com k₁. Se nada mais pré-carregar a mola, ela afrouxaria no alto de cada ciclo. O sinal limpo e
  o f estável indicam que isso não ocorre, mas vale conferir o espectro (harmônicos) no início das novas
  tomadas, onde a amplitude é maior.
- **Junta:** sem folga (confirmado); a barra é presa numa peça que gira. O pivô efetivo ≈ 24 mm além do ponto
  medido (forma modal do vídeo, `issues.md`) indica que o eixo de giro dessa peça fica atrás do ponto usado como
  "centro do mancal". Falta medir a distância **eixo de giro → ponta**.
- **Geometria × calibração do vídeo.** O segmento de calibração da sessão k1_cm_acc (p1 → p2 = 1403,5 px)
  vai da face da junta à ponta. Ajustando as posições da ponta, do parafuso e do acelerômetro na imagem às
  medidas de trena (735/655/305 mm), a escala sai 0,513 mm/px e o eixo do mancal fica ≈ 15–17 mm antes de
  p1, com resíduos ≤ 3 mm. A escala de 720 mm entre p1 e p2 continua correta, e a sessão registra
  `calibration.x0_mm = 15`.
- **Não pesado:** acelerômetro (5 g nominal) e cabo. "Porcas" inclui as arruelas; não há gancho (confirmado).
  O efeito de cada grama em f₁ é ≈ −0,01 Hz no parafuso e desprezível no acelerômetro.
