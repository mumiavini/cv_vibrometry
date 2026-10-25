# Acelerômetro (B&K 4507 001 + LAN-XI 3160-A-4/2, PULSE LabShop)

Dados disponíveis hoje: foto da tela do PULSE (`Book/Images/pulse_curva_acelerometro_foto.jpg`),
com o sinal no tempo (0–20 s) e o espectro (0–10 Hz).

**Leitura direta do software (dado medido):** cursor do espectro `X = 7,600 Hz`, `Y = 1,07 m/s²`;
cursor do tempo `X = 2,188 s`, `Y = −354 mm/s²`; gravação de 15/10/2026 20:48:57.

**Configuração inferida (confirmar no setup do PULSE):** FFT com 200 linhas, banda 10 Hz,
T = 20 s ⇒ Δf = 1/T = 0,05 Hz e fs = 2,56·10 Hz = 25,6 Hz (512 amostras/bloco).
O cursor em 7,600 Hz cai exatamente na linha nº 152 (7,600/0,05).

**Derivado da foto (não é exportação do software)** — `envelope_foto_pulse.csv` e
`Code/tools/pulse_photo/` (calibração por homografia das grades dos gráficos, validada contra os
cursores do próprio PULSE):

| Quantidade | Valor derivado | Referência |
|---|---|---|
| f do pico do espectro | 7,62 Hz (centro simétrico dos flancos, 10–50 % da altura) | cursor 7,600 Hz → +0,02 Hz (+0,26 %) |
| viés de calibração do eixo de frequência | +0,019 Hz (cursor lido como 7,619 Hz) | exato = 7,600 Hz |
| viés de calibração do eixo de tempo | +0,001 s (cursor lido como 2,189 s) | exato = 2,188 s |
| ζ (decaimento exponencial da envolvente, 2,5–9 s, R² = 0,998) | 0,0073 (faixa 0,0072–0,0079 conforme a janela) | — |
| ζ (meia potência do pico) | ≲ 0,0066, limitado pela janela/resolução de 0,05 Hz | — |

Substituir por exportação do PULSE (ASCII/Excel/MAT) assim que disponível; o sinal tem só
≈ 3,4 amostras por ciclo de 7,6 Hz, então forma de onda detalhada não é recuperável da foto.
