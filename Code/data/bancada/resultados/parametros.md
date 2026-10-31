# Parâmetros medidos da bancada e previsão do modelo

Gerado por `python -m tools.parametros_bancada` a partir de `data/bancada/*.csv`.
Leituras de comprimento da mola interpretadas em **cm** (ver README).

| Grandeza | k₁ | k₂ |
|---|---|---|
| k de catálogo (N/m) | 1500 | 2500 |
| k medido (N/m) | 857 ± 62 (7.2 %) | 3291 ± 346 (10.5 %) |
| diferença ao catálogo (%) | -42.9 | 31.6 |
| R² do ajuste | 0.9846 | 0.9679 |
| k incremental entre leituras (N/m) | 667, 1429, 1163, 704 | 1176, 4286, 4167, 3571 |
| massa efetiva m_s/3 + m_f (g) | 99.7 | 173.3 |
| f₁ elementos finitos (Hz) | 7.692 | 13.710 |
| u(f₁) modelo (Hz) | 0.279 | 0.716 |
| f₁ 1 GDL rígido (Hz) | 7.705 | 13.775 |
| f₂ (Hz) | 78.6 | 76.6 |
| φ(x_a)/φ(a) | 0.4732 | 0.4903 |
| φ(a)/φ(x_a) | 2.1133 | 2.0396 |
| efeito do acelerômetro em f₁ (%) | -0.152 | -0.134 |
| f₁ sem massa da mola e ferragens (Hz) | 9.004 | 17.474 |
| f₁ com k de catálogo, sem massa da mola (Hz) | 11.882 | 15.279 |
| f₁ se a leitura fosse em mm (Hz) | 23.91 | 40.98 |

## Frequências já medidas × modelo

| Mola | Medida | f (Hz) | erro × modelo (%) | em u(modelo) | k que reproduz (N/m) | ferragens que reproduzem (g) |
|---|---|---|---|---|---|---|
| k1 | PULSE (cursor) | 7.600 | -1.19 | -0.33 | 837 | 54.9 |
| k1 | vídeo (k1_cm_acc) | 7.763 | +0.93 | +0.26 | 873 | 39.2 |

## Orçamento de incerteza do f₁ previsto (k1)

f₁ = 7.692 ± 0.279 Hz (3.6 %); Monte Carlo: 7.687 ± 0.253 Hz

| Parâmetro | valor | u | u_f (Hz) | parcela (%) |
|---|---|---|---|---|
| springs[0].k_n_m | 857 | 61.7742 | 0.2763 | 97.8 |
| L_mm | 735 | 2 | 0.0225 | 0.6 |
| t_mm | 12.7 | 0.1 | 0.0217 | 0.6 |
| springs[0].x_mm | 655 | 2 | 0.0166 | 0.4 |
| rho | 2661.9 | 13.31 | 0.0140 | 0.2 |
| b_mm | 25.4 | 0.1 | 0.0109 | 0.2 |
| springs[0].hardware_g | 46 | 1 | 0.0104 | 0.1 |
| springs[0].mass_g | 161 | 1 | 0.0035 | 0.0 |
| masses[0].mass_g | 5 | 0.5 | 0.0012 | 0.0 |
| E_gpa | 69 | 2 | 0.0004 | 0.0 |
| masses[0].x_mm | 305 | 2 | 0.0002 | 0.0 |

## Orçamento de incerteza do f₁ previsto (k2)

f₁ = 13.710 ± 0.716 Hz (5.2 %); Monte Carlo: 13.691 ± 0.649 Hz

| Parâmetro | valor | u | u_f (Hz) | parcela (%) |
|---|---|---|---|---|
| springs[0].k_n_m | 3291 | 345.785 | 0.7134 | 99.3 |
| L_mm | 735 | 2 | 0.0325 | 0.2 |
| t_mm | 12.7 | 0.1 | 0.0314 | 0.2 |
| springs[0].x_mm | 655 | 2 | 0.0232 | 0.1 |
| rho | 2661.9 | 13.31 | 0.0209 | 0.1 |
| b_mm | 25.4 | 0.1 | 0.0162 | 0.1 |
| springs[0].hardware_g | 46 | 1 | 0.0153 | 0.0 |
| springs[0].mass_g | 382 | 1 | 0.0051 | 0.0 |
| E_gpa | 69 | 2 | 0.0019 | 0.0 |
| masses[0].mass_g | 5 | 0.5 | 0.0018 | 0.0 |
| masses[0].x_mm | 305 | 2 | 0.0002 | 0.0 |
